"""
Yahoo Finance 일별 거래정보 수집 스크립트
- CSV 다운로드 대신 chart API(v8/finance/chart) 사용 (crumb/쿠키 불필요)
- 여러 종목에 재사용 가능

사용 예:
    python yahoo_history.py 7747.HK
    python yahoo_history.py 7747.HK --range 1y
    python yahoo_history.py 005930.KS --start 2024-01-01 --end 2024-12-31
    python yahoo_history.py AAPL 7747.HK 005930.KS --range 6mo --outdir data
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {
    # UA 없으면 종종 429/403이 나므로 넣어줌
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def to_epoch(date_str: str) -> int:
    """'YYYY-MM-DD' -> UTC epoch(초)"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def fetch_history(symbol: str, *, rng=None, start=None, end=None, interval="1d") -> pd.DataFrame:
    """단일 종목의 일별(또는 지정 interval) 거래정보를 DataFrame으로 반환."""
    params = {
        "interval": interval,
        "events": "div,split",       # 배당/액면분할 이벤트 포함
        "includeAdjustedClose": "true",
    }
    if start:
        params["period1"] = to_epoch(start)
        params["period2"] = to_epoch(end) if end else int(time.time())
    else:
        params["range"] = rng or "1y"  # 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max

    url = BASE.format(symbol=symbol)
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    chart = data.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"{symbol}: {chart['error']}")
    results = chart.get("result")
    if not results:
        raise RuntimeError(f"{symbol}: 결과 없음(잘못된 심볼?)")

    res = results[0]

    # range=max 등에서 야후가 interval을 무시하고 더 잘게(1h 등) 내려주는 경우를 감지
    granularity = res["meta"].get("dataGranularity")
    if granularity and granularity != interval:
        print(
            f"[경고] {symbol}: 요청 interval={interval} 이지만 야후가 "
            f"{granularity} 로 내려줌. --start/--end 로 기간을 지정하면 일봉이 정상 반환됩니다.",
            file=sys.stderr,
        )

    ts = res.get("timestamp")
    if not ts:
        raise RuntimeError(f"{symbol}: 거래 데이터 없음")

    quote = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")

    currency = res["meta"].get("currency")         # 예: HKD, USD
    tz = res["meta"].get("exchangeTimezoneName")   # 예: Asia/Hong_Kong
    idx = pd.to_datetime(ts, unit="s", utc=True)
    if tz:
        idx = idx.tz_convert(tz)

    df = pd.DataFrame(
        {
            "Date": idx.date,
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Adj Close": adj if adj is not None else quote.get("close"),
            "Volume": quote.get("volume"),
        }
    )
    # 거래 없는 날(전부 None) 제거
    df = df.dropna(subset=["Open", "High", "Low", "Close"], how="all").reset_index(drop=True)
    df.insert(0, "Symbol", symbol)
    df.insert(1, "Currency", currency)
    return df


# --- 선택적 라벨 연동 (tickers.csv 있으면 기초종목/상품명/레버리지 붙임) ---
LABEL_COLS = ["Underlying", "ProductName", "Leverage"]


def load_label_map(path: str) -> dict:
    """tickers.csv -> {심볼: {Underlying, ProductName, Leverage}}. 없으면 빈 dict."""
    if not path or not os.path.exists(path):
        return {}
    m = pd.read_csv(path)
    if "Ticker" not in m.columns:
        return {}
    m = m.set_index("Ticker")
    return {
        sym: {c: row.get(c) for c in LABEL_COLS if c in m.columns}
        for sym, row in m.iterrows()
    }


def attach_labels(df: pd.DataFrame, symbol: str, label_map: dict) -> pd.DataFrame:
    """Currency 열 뒤에 라벨 열 삽입. 매핑에 없으면 빈 값."""
    info = label_map.get(symbol, {})
    pos = df.columns.get_loc("Currency") + 1
    for i, c in enumerate(LABEL_COLS):
        df.insert(pos + i, c, info.get(c))
    return df, bool(info)


def main():
    ap = argparse.ArgumentParser(description="Yahoo Finance 일별 거래정보 수집")
    ap.add_argument("symbols", nargs="+", help="종목 심볼 (예: 7747.HK 005930.KS AAPL)")
    ap.add_argument("--range", dest="rng", default="1y",
                    help="기간: 1mo,3mo,6mo,1y,2y,5y,10y,ytd,max (기본 1y)")
    ap.add_argument("--start", help="시작일 YYYY-MM-DD (지정 시 --range 무시)")
    ap.add_argument("--end", help="종료일 YYYY-MM-DD (미지정 시 오늘)")
    ap.add_argument("--interval", default="1d", help="1d,1wk,1mo (기본 1d)")
    ap.add_argument("--outdir", default=".", help="CSV 저장 폴더 (기본 현재 폴더)")
    ap.add_argument("--map", default="tickers.csv",
                    help="라벨 매핑 파일 (있으면 기초종목/상품명 자동 부착, 기본 tickers.csv)")
    ap.add_argument("--no-labels", action="store_true", help="라벨 부착 안 함")
    args = ap.parse_args()

    label_map = {} if args.no_labels else load_label_map(args.map)
    if label_map:
        print(f"[라벨] {args.map} 적용 ({len(label_map)}개 매핑)")

    frames = []
    for sym in args.symbols:
        try:
            df = fetch_history(sym, rng=args.rng, start=args.start,
                               end=args.end, interval=args.interval)
        except Exception as e:
            print(f"[실패] {sym}: {e}", file=sys.stderr)
            continue

        df, matched = attach_labels(df, sym, label_map)
        if label_map and not matched:
            print(f"[주의] {sym}: tickers.csv 에 없음 → 라벨 비어 있음", file=sys.stderr)

        out = f"{args.outdir.rstrip('/')}/{sym.replace('.', '_')}.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[완료] {sym}: {len(df)}행 -> {out}")
        print(df.tail(5).to_string(index=False))
        print()
        frames.append(df)
        time.sleep(0.5)  # 예의상 딜레이

    if len(frames) > 1:
        allout = f"{args.outdir.rstrip('/')}/all_symbols.csv"
        pd.concat(frames, ignore_index=True).to_csv(allout, index=False, encoding="utf-8-sig")
        print(f"[통합] {allout}")


if __name__ == "__main__":
    main()
