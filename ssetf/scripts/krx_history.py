"""
KRX 상장 ETF 일별 거래데이터 + NAV 수집.

로컬 패키지 krx-data-api(C:\\Users\\Peter\\github\\krx-data-api)의 endpoint 사용:
  etf_all_info   (MDCSTAT04601) : 전종목 ETF 기본정보 → 단축코드↔표준코드(ISIN)·운용사·추적배수
  etf_price_trend(MDCSTAT04501) : 개별 ETF 시세추이 → OHLCV+거래대금+NAV+기초지수

KRX 로그인 필요(레포 .env의 KRX_ID/KRX_PW). auth=True로 호출.

사용 예:
    python krx_history.py                       # 기본 14개 레버리지 ETF
    python krx_history.py 0193W0 0193T0 --start 20250101
    python krx_history.py --start 20250101 --end 20260703 --outdir data
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

# 기본 대상: 삼성/하이닉스 단일종목 2x 레버리지 14개
DEFAULT_CODES = [
    "0193W0", "0195R0", "0194M0", "0192M0", "0193K0", "0194N0", "0198B0",
    "0193T0", "0195S0", "0194T0", "0192L0", "0197W0", "0194R0", "0198D0",
]
# etf_price_trend 한글 컬럼 -> 영문 (부분일치로 탐색)
COLMAP = {
    "일자": "Date", "시가": "Open", "고가": "High", "저가": "Low", "종가": "Close",
    "거래량": "Volume", "거래대금": "Turnover", "NAV": "NAV",
    "순자산총액": "NetAssets", "기초지수_지수명": "IndexName", "기초지수_종가": "IndexClose",
}


def _find(cols, key):
    for c in cols:
        if key in c:
            return c
    return None


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def load_catalog():
    """etf_all_info → {단축코드: {ISIN, Name, Mult, Manager}}"""
    from krx_data_api import fetch
    info = fetch("etf_all_info", auth=True)
    c_sc = _find(info.columns, "단축")
    c_isin = _find(info.columns, "표준")
    c_nm = _find(info.columns, "약명") or _find(info.columns, "한글종목명")
    c_mult = _find(info.columns, "배수")
    c_mgr = _find(info.columns, "운용사")
    cat = {}
    for _, r in info.iterrows():
        cat[r[c_sc]] = {
            "ISIN": r[c_isin], "Name": r[c_nm],
            "Mult": r.get(c_mult) if c_mult else None,
            "Manager": r.get(c_mgr) if c_mgr else None,
        }
    return cat


def fetch_one(isin: str, start: str, end: str) -> pd.DataFrame:
    from krx_data_api import fetch
    df = fetch("etf_price_trend", isuCd=isin, isuCd2=isin,
               strtDd=start, endDd=end, auth=True)
    ren = {src: dst for kw, dst in COLMAP.items() if (src := _find(df.columns, kw))}
    df = df.rename(columns=ren)
    for c in ["Open", "High", "Low", "Close", "Volume", "Turnover", "NAV",
              "NetAssets", "IndexClose"]:
        if c in df.columns:
            df[c] = _num(df[c])
    df["Date"] = pd.to_datetime(df["Date"].astype(str).str.replace("/", "-")).dt.date
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume",
                        "Turnover", "NAV", "NetAssets", "IndexName", "IndexClose"]
            if c in df.columns]
    return df[keep].sort_values("Date").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description="KRX ETF 일별 데이터+NAV 수집")
    ap.add_argument("codes", nargs="*", default=DEFAULT_CODES,
                    help="단축코드들 (기본: 레버리지 14종목)")
    ap.add_argument("--start", default="20250101", help="YYYYMMDD")
    ap.add_argument("--end", default=date.today().strftime("%Y%m%d"), help="YYYYMMDD")
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()
    codes = args.codes or DEFAULT_CODES

    print(f"[KRX] etf_all_info 로딩...")
    cat = load_catalog()
    os.makedirs(args.outdir, exist_ok=True)

    frames = []
    for code in codes:
        meta = cat.get(code)
        if not meta:
            print(f"[주의] {code}: etf_all_info에 없음", file=sys.stderr)
            continue
        try:
            df = fetch_one(meta["ISIN"], args.start, args.end)
        except Exception as e:
            print(f"[실패] {code}: {e}", file=sys.stderr)
            continue
        df.insert(0, "Symbol", f"{code}.KS")
        df.insert(1, "ISIN", meta["ISIN"])
        df.insert(2, "Name", meta["Name"])
        df.insert(3, "Currency", "KRW")
        out = os.path.join(args.outdir, f"{code}_KS_krx.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[완료] {code} [{meta['ISIN']}] {meta['Name']}: "
              f"{len(df)}행 ({df['Date'].min()}~{df['Date'].max()}) -> {out}")
        frames.append(df)

    if len(frames) > 1:
        allout = os.path.join(args.outdir, "krx_all.csv")
        pd.concat(frames, ignore_index=True).to_csv(allout, index=False, encoding="utf-8-sig")
        print(f"[통합] {len(frames)}종목 -> {allout}")


if __name__ == "__main__":
    main()
