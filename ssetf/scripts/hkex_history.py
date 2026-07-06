"""
HKEX(홍콩거래소) 일별 거래데이터 + 종목정보(ISIN 포함) 수집.

홍콩거래소 ETP 시세페이지의 위젯 API(www1.hkex.com.hk/hkexwidget)를 호출한다.
야후와 달리 **거래량+거래대금(turnover)** 까지 오고, **상장 첫날부터** 데이터가 있다.

두 엔드포인트(둘 다 JSONP, 같은 token 사용):
  getchartdata2 : 일별 [ts, Open, High, Low, Close, Volume, Turnover]
  getequityquote: ISIN/종목명/통화/NAV 등 정적정보

token은 페이지 JS(LabCI.getToken())가 생성해 넘기며 정적 스크래핑으론 못 얻는다.
DevTools Network에서 getchartdata2/getequityquote 요청의 token 파라미터를 복사해 전달한다.
(HKEX 토큰은 한동안 유효하나 만료되면 다시 캡처해야 함.)

사용 예:
    python hkex_history.py 7747 9747 7709 --token "<TOKEN>"
    HKEX_TOKEN="<TOKEN>" python hkex_history.py 7747
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote

import pandas as pd
import requests

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WIDGET = "https://www1.hkex.com.hk/hkexwidget/data"
HKT = timezone(timedelta(hours=8))  # HKEX 타임스탬프는 HK 자정(UTC+8) 기준
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
    "Referer": "https://www.hkex.com.hk/",
}
_JSONP = re.compile(r"^[^(]*\((.*)\)\s*;?\s*$", re.S)


def _jsonp(text: str) -> dict:
    m = _JSONP.match(text.strip())
    return json.loads(m.group(1) if m else text)


def _get(endpoint: str, params: dict) -> dict:
    params = {**params, "callback": "cb", "qid": "1", "_": "1"}
    r = requests.get(f"{WIDGET}/{endpoint}", params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = _jsonp(r.text)
    d = j.get("data", {})
    if d.get("responsecode") not in ("000", None):
        raise RuntimeError(f"{endpoint} 응답오류: {d.get('responsecode')} {d.get('responsemsg')}")
    return d


def get_quote(sym: str, token: str) -> dict:
    """정적정보(ISIN/종목명/통화/NAV 등)."""
    d = _get("getequityquote", {"sym": str(sym).lstrip("0") or "0", "token": token, "lang": "eng"})
    q = d.get("quote", {})
    return {
        "ISIN": q.get("isin"), "Name": q.get("nm"), "ShortName": q.get("nm_s"),
        "Currency": q.get("ccy"), "NAV": q.get("nav"), "MgmtFee": q.get("management_fee"),
        "SharesOut": q.get("amt_os"), "PrimaryExch": q.get("primaryexch"),
    }


def get_chart(sym: str, token: str, span: int = 6, interval: int = 6) -> pd.DataFrame:
    """일별 OHLCV+turnover. span/int=6,6 이면 상장일부터 전체 일봉."""
    ric = f"{str(sym).zfill(4)}.HK"
    d = _get("getchartdata2", {"hchart": "1", "span": span, "int": interval, "ric": ric, "token": token})
    rows = d.get("datalist", [])
    recs = []
    for r in rows:
        # [ts_ms, open, high, low, close, volume, turnover]; 자리표시자/결측 스킵
        if len(r) < 7 or r[1] is None or r[4] is None or r[1] < 0:
            continue
        recs.append({
            "Date": datetime.fromtimestamp(r[0] / 1000, tz=HKT).date(),
            "Open": r[1], "High": r[2], "Low": r[3], "Close": r[4],
            "Volume": r[5], "Turnover": r[6],
        })
    df = pd.DataFrame(recs).sort_values("Date").reset_index(drop=True)
    return df


def main():
    ap = argparse.ArgumentParser(description="HKEX 일별 데이터+ISIN 수집(hkexwidget)")
    ap.add_argument("syms", nargs="+", help="종목코드 (예: 7747 9747 7709)")
    ap.add_argument("--token", default=os.environ.get("HKEX_TOKEN"),
                    help="위젯 token (DevTools 캡처). 환경변수 HKEX_TOKEN 가능")
    ap.add_argument("--outdir", default="data", help="저장 폴더")
    args = ap.parse_args()

    if not args.token:
        sys.exit("오류: --token 필요 (DevTools의 getchartdata2/getequityquote token 파라미터)")
    token = unquote(args.token)  # %2b -> +

    os.makedirs(args.outdir, exist_ok=True)
    frames = []
    for sym in args.syms:
        try:
            info = get_quote(sym, token)
            df = get_chart(sym, token)
        except Exception as e:
            print(f"[실패] {sym}: {e}", file=sys.stderr)
            continue
        df.insert(0, "Symbol", f"{str(sym).zfill(4)}.HK")
        for k in ["ISIN", "Name", "Currency"]:
            df.insert(1, k, info.get(k))
        out = os.path.join(args.outdir, f"{str(sym).zfill(4)}_HK_hkex.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[완료] {sym} [{info.get('ISIN')} / {info.get('Currency')}]: "
              f"{len(df)}행 ({df['Date'].min()}~{df['Date'].max()}) -> {out}")
        print(df.tail(3)[["Date", "Open", "High", "Low", "Close", "Volume", "Turnover"]].to_string(index=False))
        frames.append(df)

    if len(frames) > 1:
        allout = os.path.join(args.outdir, "hkex_all.csv")
        pd.concat(frames, ignore_index=True).to_csv(allout, index=False, encoding="utf-8-sig")
        print(f"[통합] {allout}")


if __name__ == "__main__":
    main()
