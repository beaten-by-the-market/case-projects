"""
LSE(London Stock Exchange) 일별 거래데이터 수집.

런던증권거래소 종목페이지의 차트는 refinitiv-widgets.financial.com(구 Refinitiv/
financial.com 위젯)에서 데이터를 받는다. 야후와 달리 **상장 첫날부터** 데이터가 있다.

인증 2단계:
  1) POST {AUTH}/auth/api/v1/tokens  (헤더 X-API-KEY: <키>)  -> JWT
  2) GET  {BASE}/rest/api/timeseries/historical (헤더 jwt: <JWT>) -> 일별 OHLC

API 키는 위젯 초기화 때 주입돼 정적 스크래핑으로는 못 얻는다. DevTools Network에서
'auth/api/v1/tokens' 요청의 X-API-KEY(재사용 가능) 또는 historical 요청의 jwt(5분 만료)를
복사해 전달한다.

사용 예:
    # API 키로 (권장, JWT 자동발급)
    python lse_history.py HNX3.L SMG3.L --api-key <KEY> --start 2026-06-01
    # 또는 캡처한 JWT로 (만료 전까지)
    python lse_history.py HNX3.L --jwt <JWT> --start 2026-06-01
    # 환경변수도 가능: LSE_API_KEY / LSE_JWT
"""

import argparse
import os
import sys
from datetime import date, datetime

import pandas as pd
import requests

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOST = "https://refinitiv-widgets.financial.com"
AUTH_URL = f"{HOST}/auth/api/v1/tokens"
HIST_URL = f"{HOST}/rest/api/timeseries/historical"
# OHLC + 거래대금(on book). 거래량 ACVOL_UNS는 이 피드에서 '-'라 제외, TURNOVER는 유효.
FIDS = "_DATE_END,OPEN_PRC,HIGH_1,LOW_1,CLOSE_PRC,TURNOVER"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
    "Origin": "https://www.londonstockexchange.com",
    "Referer": "https://www.londonstockexchange.com/",
}
_RENAME = {"_DATE_END": "Date", "OPEN_PRC": "Open", "HIGH_1": "High",
           "LOW_1": "Low", "CLOSE_PRC": "Close", "TURNOVER": "Turnover"}


def mint_jwt(api_key: str) -> str:
    """X-API-KEY로 JWT 발급."""
    r = requests.post(AUTH_URL, headers={**HEADERS, "X-API-KEY": api_key}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"토큰 발급 실패 [{r.status_code}]: {r.text[:200]}")
    # 응답이 순수 토큰 문자열이거나 JSON({token:...})일 수 있음
    txt = r.text.strip().strip('"')
    if txt.startswith("{"):
        j = r.json()
        txt = j.get("token") or j.get("jwt") or j.get("access_token") or ""
    if not txt:
        raise RuntimeError(f"토큰 파싱 실패: {r.text[:200]}")
    return txt


def fetch_lse(ric: str, jwt: str, start: str, end: str) -> pd.DataFrame:
    params = {
        "ric": ric,
        "fids": FIDS,
        "samples": "D",
        "appendRecentData": "all",
        "fromDate": f"{start}T00:00:00",
        "toDate": f"{end}T23:59:59",
    }
    r = requests.get(HIST_URL, params=params, headers={**HEADERS, "jwt": jwt}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"{ric}: 조회 실패 [{r.status_code}] {r.text[:200]}")
    rows = r.json().get("data", [])
    if not rows:
        raise RuntimeError(f"{ric}: 데이터 없음")
    df = pd.DataFrame(rows).rename(columns=_RENAME)
    for c in ["Open", "High", "Low", "Close", "Turnover"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")   # '-' -> NaN
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df = df.dropna(subset=["Open", "High", "Low", "Close"], how="all")
    df = df.sort_values("Date").reset_index(drop=True)
    df.insert(0, "Symbol", ric)
    cols = ["Symbol", "Date", "Open", "High", "Low", "Close"]
    if "Turnover" in df.columns:
        cols.append("Turnover")
    return df[cols]


def main():
    ap = argparse.ArgumentParser(description="LSE 일별 거래데이터 수집(refinitiv-widgets)")
    ap.add_argument("rics", nargs="+", help="RIC 코드 (예: HNX3.L SMG3.L)")
    ap.add_argument("--api-key", default=os.environ.get("LSE_API_KEY"),
                    help="X-API-KEY (JWT 자동발급). 환경변수 LSE_API_KEY 가능")
    ap.add_argument("--jwt", default=os.environ.get("LSE_JWT"),
                    help="캡처한 JWT (5분 만료). 환경변수 LSE_JWT 가능")
    ap.add_argument("--start", default="2026-01-01", help="시작일 YYYY-MM-DD")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m-%d"), help="종료일")
    ap.add_argument("--outdir", default="data", help="저장 폴더")
    args = ap.parse_args()

    if args.api_key:
        jwt = mint_jwt(args.api_key)
        print("[인증] API 키로 JWT 발급 완료")
    elif args.jwt:
        jwt = args.jwt.replace(" ", "")
        print("[인증] 전달된 JWT 사용")
    else:
        sys.exit("오류: --api-key 또는 --jwt 필요 (DevTools에서 캡처)")

    os.makedirs(args.outdir, exist_ok=True)
    frames = []
    for ric in args.rics:
        try:
            df = fetch_lse(ric, jwt, args.start, args.end)
        except Exception as e:
            print(f"[실패] {ric}: {e}", file=sys.stderr)
            continue
        out = os.path.join(args.outdir, f"{ric.replace('.', '_')}_lse.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[완료] {ric}: {len(df)}행 ({df['Date'].min()}~{df['Date'].max()}) -> {out}")
        print(df.tail(3).to_string(index=False))
        frames.append(df)

    if len(frames) > 1:
        allout = os.path.join(args.outdir, "lse_all.csv")
        pd.concat(frames, ignore_index=True).to_csv(allout, index=False, encoding="utf-8-sig")
        print(f"[통합] {allout}")


if __name__ == "__main__":
    main()
