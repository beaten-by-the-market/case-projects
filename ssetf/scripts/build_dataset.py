"""
거래소 네이티브 CSV(HKEX/LSE/KRX)를 하나로 통합하고 Naver 환율로 KRW 환산.

입력 (data/):
    hkex_all.csv, lse_all.csv, krx_all.csv     (각 수집 스크립트 산출물)
    fx_USDKRW_naver.csv, fx_HKDKRW_naver.csv    (naver_fx.py 산출물; 없으면 자동 수집)
    ../tickers.csv                               (Exchange/Underlying/Leverage/통화 보강용)

출력:
    data/all_krw.csv   19종목 통합 + 당일 매매기준율 KRW 환산

환산: 종목 통화(HKD/USD/KRW)별로 Naver 매매기준율을 그날(없으면 직전 영업일, merge_asof)
      환율로 곱함. KRW 종목은 FX_Rate=1로 통과.

사용:
    python build_dataset.py
"""

import os
import sys

import pandas as pd

# 어디서 실행하든 프로젝트 루트 기준으로 data/·tickers.csv 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = "data"
SOURCES = ["hkex_all.csv", "lse_all.csv", "krx_all.csv"]
CORE = ["Symbol", "Date", "Open", "High", "Low", "Close",
        "Volume", "Turnover", "NAV", "ISIN", "Name", "Currency"]
PRICE_COLS = ["Open", "High", "Low", "Close", "NAV"]
FX_FILES = {"USD": "fx_USDKRW_naver.csv", "HKD": "fx_HKDKRW_naver.csv"}


def load_sources() -> pd.DataFrame:
    frames = []
    for f in SOURCES:
        path = os.path.join(DATA, f)
        if not os.path.exists(path):
            print(f"[건너뜀] {path} 없음", file=sys.stderr)
            continue
        df = pd.read_csv(path)
        for c in CORE:              # 없는 컬럼은 NA로 채워 스키마 통일
            if c not in df.columns:
                df[c] = pd.NA
        frames.append(df[CORE])
        print(f"  {f}: {len(df)}행, {df['Symbol'].nunique()}종목")
    if not frames:
        sys.exit("소스 CSV가 하나도 없습니다. 먼저 수집 스크립트를 실행하세요.")
    return pd.concat(frames, ignore_index=True)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """tickers.csv로 Exchange/Underlying/Leverage 보강, 통화 결측 채움."""
    t = pd.read_csv("tickers.csv").rename(columns={"Ticker": "Symbol"})
    meta = t[["Symbol", "Exchange", "Underlying", "Leverage", "Currency"]]
    df = df.merge(meta, on="Symbol", how="left", suffixes=("", "_t"))
    df["Currency"] = df["Currency"].fillna(df["Currency_t"])
    df = df.drop(columns=["Currency_t"])
    return df


def load_fx() -> dict:
    """{통화: DataFrame[Date(datetime), Rate]}. 저장본 우선, 없으면 naver_fx로 수집."""
    fx = {}
    for cur, fname in FX_FILES.items():
        path = os.path.join(DATA, fname)
        if os.path.exists(path):
            d = pd.read_csv(path)
        else:
            print(f"  {cur} 환율 저장본 없음 → Naver에서 수집", file=sys.stderr)
            from naver_fx import fetch_fx
            d = fetch_fx(cur, start="2025-01-01")
        d["Date"] = pd.to_datetime(d["Date"])
        fx[cur] = d[["Date", "Rate"]].sort_values("Date").reset_index(drop=True)
    return fx


def to_krw(df: pd.DataFrame, fx: dict) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    out = []
    for cur, g in df.groupby("Currency", sort=False):
        g = g.sort_values("Date")
        if cur == "KRW":
            g["FX_Pair"], g["FX_Rate"] = "-", 1.0
        elif cur in fx:
            g = pd.merge_asof(g, fx[cur], on="Date", direction="backward")
            g = g.rename(columns={"Rate": "FX_Rate"})
            g["FX_Pair"] = f"{cur}KRW"
        else:
            print(f"[주의] {cur} 환율 없음 → KRW 환산 생략", file=sys.stderr)
            g["FX_Pair"], g["FX_Rate"] = cur, pd.NA
        for c in PRICE_COLS:
            g[f"{c}_KRW"] = (pd.to_numeric(g[c], errors="coerce") * g["FX_Rate"]).round(2)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main():
    print("[1/4] 소스 로딩")
    df = load_sources()
    print("[2/4] 메타 보강 (tickers.csv)")
    df = enrich(df)
    print("[3/4] Naver 환율 로딩")
    fx = load_fx()
    print("[4/4] KRW 환산")
    result = to_krw(df, fx)

    order = ["Symbol", "Exchange", "Underlying", "Leverage", "Currency", "ISIN", "Name",
             "Date", "Open", "High", "Low", "Close", "Volume", "Turnover", "NAV",
             "FX_Pair", "FX_Rate", "Open_KRW", "High_KRW", "Low_KRW", "Close_KRW", "NAV_KRW"]
    result = result[[c for c in order if c in result.columns]]
    result["Date"] = result["Date"].dt.date
    result = result.sort_values(["Symbol", "Date"]).reset_index(drop=True)

    out = os.path.join(DATA, "all_krw.csv")
    result.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[완료] {result['Symbol'].nunique()}종목 {len(result)}행 -> {out}")
    # 요약
    summ = (result.sort_values("Date").groupby(["Symbol", "Exchange", "Currency"])
            .agg(rows=("Date", "size"), last=("Date", "max"),
                 last_close=("Close", "last"), last_krw=("Close_KRW", "last"))
            .reset_index())
    print(summ.to_string(index=False))


if __name__ == "__main__":
    main()
