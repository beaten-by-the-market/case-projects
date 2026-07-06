"""
본주(삼성전자 005930 · SK하이닉스 000660)의 일별 거래대금·시가총액 수집.

레버리지 상품이 아니라 **기초자산(본주)** 데이터다. 차트(make_charts/make_bloomberg/
make_aum_chart)가 비교 기준선으로 쓰는 두 파일을 생성한다. 이전엔 생성 스크립트가
없는 수동 입력이었던 것을 스크립트화한 것.

소스: 로컬 레포 krx-data-api 의 individual_price_trend (MDCSTAT01701 개별종목시세추이).
      이 한 화면이 일자별 거래대금 + 시가총액을 함께 준다. KRX 로그인 필요(.env).

산출(형식은 기존 파일·차트 소비방식에 맞춤):
  data/underlying_krx_turnover.csv   시계열  : Date(YYYY-MM-DD), Turnover, Underlying
  data/underlying_krx_mktcap.csv     스냅샷  : Underlying, Date(YYYY/MM/DD), MktCap_KRW
                                              (차트가 set_index("Underlying") → 본주당 1행=최신)
  data/underlying_krx_mktcap_series.csv  (덤) 시가총액 전체 시계열(재현·검증용)

단위 KRW. 거래대금·시가총액은 원주가 기준(splits 없는 구간이라 수정주가와 동일).

사용:
    python underlying_krx.py                          # 2025-05-01~오늘
    python underlying_krx.py --start 20250101 --end 20260703
"""

import argparse
import os
import sys
from datetime import date

import pandas as pd

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KRX_REPO = r"C:\Users\Peter\github\krx-data-api"
if KRX_REPO not in sys.path:
    sys.path.insert(0, KRX_REPO)

# (표기명, 단축코드, 표준코드ISIN). 차트가 쓰는 영문 표기명을 그대로 사용.
UNDERLYINGS = [
    ("Samsung Electronics", "005930", "KR7005930003"),
    ("SK Hynix",            "000660", "KR7000660001"),
]


def _find(cols, key):
    for c in cols:
        if key in c:
            return c
    return None


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def fetch_underlying(isin: str, start: str, end: str) -> pd.DataFrame:
    """individual_price_trend → DataFrame[Date, Turnover, MktCap]."""
    from krx_data_api import fetch
    df = fetch("individual_price_trend", isuCd=isin, strtDd=start, endDd=end,
               adjusted_price=False, auth=True)
    c_date = _find(df.columns, "일자")
    c_turn = _find(df.columns, "거래대금")
    c_cap = _find(df.columns, "시가총액")
    if not (c_date and c_turn and c_cap):
        raise RuntimeError(f"컬럼 탐색 실패: {list(df.columns)}")
    out = pd.DataFrame({
        "Date": pd.to_datetime(df[c_date].astype(str).str.replace("/", "-")),
        "Turnover": _num(df[c_turn]),
        "MktCap": _num(df[c_cap]),
    })
    return out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description="본주(삼성·하이닉스) 거래대금·시가총액 수집")
    ap.add_argument("--start", default="20250501", help="YYYYMMDD")
    ap.add_argument("--end", default=date.today().strftime("%Y%m%d"), help="YYYYMMDD")
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    turn_rows, cap_series, cap_snap = [], [], []
    for name, code, isin in UNDERLYINGS:
        try:
            df = fetch_underlying(isin, args.start, args.end)
        except Exception as e:
            print(f"[실패] {name}({code}): {e}", file=sys.stderr)
            continue
        df["Underlying"] = name
        # 거래대금 시계열 (최신일 먼저 — 기존 파일 정렬과 동일)
        t = df.sort_values("Date", ascending=False)
        turn_rows.append(t[["Date", "Turnover", "Underlying"]])
        # 시가총액 전체 시계열(덤)
        cap_series.append(df[["Underlying", "Date", "MktCap"]])
        # 시가총액 스냅샷 (최신일 1행)
        last = df.iloc[-1]
        cap_snap.append({"Underlying": name, "Date": last["Date"],
                         "MktCap_KRW": int(last["MktCap"])})
        print(f"[완료] {name}({code}): {len(df)}행 "
              f"({df['Date'].min().date()}~{df['Date'].max().date()})  "
              f"최신 시총 {int(last['MktCap']):,} / 거래대금 {int(last['Turnover']):,}")

    if not turn_rows:
        sys.exit("수집 실패 — KRX 로그인(.env)·레포 설치 확인")

    # 1) 거래대금 시계열
    turn = pd.concat(turn_rows, ignore_index=True)
    turn["Date"] = turn["Date"].dt.strftime("%Y-%m-%d")
    p1 = os.path.join(args.outdir, "underlying_krx_turnover.csv")
    turn.to_csv(p1, index=False, encoding="utf-8-sig")

    # 2) 시가총액 스냅샷 (차트 소비형식: Date=YYYY/MM/DD)
    snap = pd.DataFrame(cap_snap)
    snap["Date"] = pd.to_datetime(snap["Date"]).dt.strftime("%Y/%m/%d")
    p2 = os.path.join(args.outdir, "underlying_krx_mktcap.csv")
    snap.to_csv(p2, index=False, encoding="utf-8-sig")

    # 3) 시가총액 전체 시계열 (덤, 검증·재현용)
    cs = pd.concat(cap_series, ignore_index=True).rename(columns={"MktCap": "MktCap_KRW"})
    cs["Date"] = cs["Date"].dt.strftime("%Y-%m-%d")
    cs["MktCap_KRW"] = cs["MktCap_KRW"].astype("Int64")
    p3 = os.path.join(args.outdir, "underlying_krx_mktcap_series.csv")
    cs.to_csv(p3, index=False, encoding="utf-8-sig")

    print(f"[저장] {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
