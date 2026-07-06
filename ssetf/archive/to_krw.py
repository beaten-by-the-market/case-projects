"""
yahoo_history.py 로 받은 CSV를 '당일 마감 환율' 기준으로 KRW 환산.

- 종목의 거래통화를 자동 감지(CSV의 Currency 열 -> 없으면 야후 meta 조회)
- 통화별로 야후에서 {통화}KRW=X 일별 환율을 받아 날짜별 종가로 곱함
- 환율 없는 날(공휴일 등)은 직전 영업일 환율로 보정(merge_asof, 과거방향)

사용 예:
    python to_krw.py data/7747_HK.csv
    python to_krw.py data/all_symbols.csv
    python to_krw.py data/9747_HK.csv --from USD          # 통화 강제 지정
    python to_krw.py data/all_symbols.csv --outdir krw    # 저장 폴더 지정

출력: 원본 + FX_Pair, FX_Rate, Open_KRW..Close_KRW, Adj Close_KRW 열 추가한 *_krw.csv
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
PRICE_COLS = ["Open", "High", "Low", "Close", "Adj Close"]


def to_epoch(date_str: str) -> int:
    dt = datetime.strptime(str(date_str), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def get_currency(symbol: str) -> str:
    """야후 meta에서 거래통화 조회."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, params={"range": "1d", "interval": "1d"},
                     headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()["chart"]["result"][0]["meta"].get("currency")


def fetch_fx(pair: str, start: str, end: str) -> pd.DataFrame:
    """{통화}KRW=X 일별 환율. columns: Date(datetime), FX_Rate"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}"
    params = {
        "interval": "1d",
        "period1": to_epoch(start),
        "period2": to_epoch(end) + 86400,  # 종료일 포함
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res.get("timestamp") or []
    close = res["indicators"]["quote"][0].get("close", [])
    fx = pd.DataFrame({
        "Date": pd.to_datetime(ts, unit="s", utc=True).tz_convert("UTC").normalize().tz_localize(None),
        "FX_Rate": close,
    }).dropna(subset=["FX_Rate"])
    return fx.drop_duplicates(subset="Date").sort_values("Date").reset_index(drop=True)


def convert_symbol(df: pd.DataFrame, currency: str, fx_cache: dict) -> pd.DataFrame:
    """단일 종목 df를 KRW 환산."""
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    if currency == "KRW":
        df["FX_Pair"], df["FX_Rate"] = "-", 1.0
    else:
        pair = f"{currency}KRW=X"
        if pair not in fx_cache:
            s, e = df["Date"].min().strftime("%Y-%m-%d"), df["Date"].max().strftime("%Y-%m-%d")
            fx_cache[pair] = fetch_fx(pair, s, e)
            time.sleep(0.3)
        fx = fx_cache[pair]
        # 각 거래일에 '그날 또는 직전 영업일' 환율을 매칭
        df = pd.merge_asof(
            df.sort_values("Date"), fx, on="Date", direction="backward"
        )
        df["FX_Pair"] = pair

    for c in PRICE_COLS:
        if c in df.columns:
            df[f"{c}_KRW"] = (df[c] * df["FX_Rate"]).round(2)
    return df


def process_file(path: str, force_cur: str, outdir: str, fx_cache: dict):
    df = pd.read_csv(path)
    if "Symbol" not in df.columns or "Date" not in df.columns:
        print(f"[건너뜀] {path}: Symbol/Date 열이 없습니다.", file=sys.stderr)
        return

    out_frames = []
    for sym, g in df.groupby("Symbol", sort=False):
        cur = force_cur or (g["Currency"].iloc[0] if "Currency" in g.columns
                            and pd.notna(g["Currency"].iloc[0]) else get_currency(sym))
        conv = convert_symbol(g, cur, fx_cache)
        out_frames.append(conv)
        last = conv.iloc[-1]
        print(f"  {sym} [{cur}]: {len(conv)}행, "
              f"최근 {last['Date'].date()} Close {last['Close']} × "
              f"{last['FX_Rate']:.4f} = {last.get('Close_KRW')} KRW")

    result = pd.concat(out_frames, ignore_index=True)
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{base}_krw.csv")
    result.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[완료] {path} -> {out}\n")


def main():
    ap = argparse.ArgumentParser(description="야후 CSV를 당일 마감환율로 KRW 환산")
    ap.add_argument("files", nargs="+", help="yahoo_history.py로 받은 CSV 경로들")
    ap.add_argument("--from", dest="force_cur", default=None,
                    help="원본 통화 강제 지정(예: USD). 미지정 시 자동 감지")
    ap.add_argument("--outdir", default=".", help="저장 폴더 (기본 현재 폴더)")
    args = ap.parse_args()

    fx_cache: dict = {}
    for f in args.files:
        if not os.path.exists(f):
            print(f"[없음] {f}", file=sys.stderr)
            continue
        print(f"# {f}")
        process_file(f, args.force_cur, args.outdir, fx_cache)


if __name__ == "__main__":
    main()
