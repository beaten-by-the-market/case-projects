"""
LSE Leverage Shares 3x ETP(HNX3·SMG3)의 AUM·NAV 수집.

런던 상장 3x 삼성·하이닉스는 ETF가 아니라 **ETP(담보부 채무증권)**라, Bloomberg·
investing·etfdb 같은 3자 벤더엔 AUM이 안 실린다. 이슈어 상품페이지엔 뜨지만 그 값은
자바스크립트가 나중에 불러오는 값이라 정적 크롤링(HTML)으로는 빈칸('-')만 나온다.

값의 진짜 출처는 이슈어 백엔드다:
    POST https://leverageshares.com/Lab_Forty_Scripts/php/etp_data.php
    Content-Type: application/json
    body: {"name":"<상품슬러그>","documentLocaleType":"en-eu"}

응답 JSON 구조(핵심):
  Etp[0] = 최신 스냅샷
    etp_securities_issued  -> 상품페이지가 'AUM'으로 표기하는 값(순 AUM, 발행증권 시가총액)
    value_underlying_assets-> 기초자산 총액(3x 총 익스포저 ≈ AUM x 3)
    liabilities            -> 부채(마진론)
    Outstanding_Shares_Par -> 발행 좌수
    price / navDailyChang   -> NAV 및 전일대비
  Usd[] / Gbp[] = 통화별 일별 시계열
    date, price(NAV), etp_securities_issued(그날 AUM), turnoverBaseCurrency, SoldShares

USD 상장라인(HNX3/SMG3)은 Usd 배열, GBP 라인(3HNX/3SMG)은 Gbp 배열을 쓴다.

사용 예:
    python lse_aum.py                       # HNX3.L SMG3.L 둘 다, USD
    python lse_aum.py HNX3.L --currency Gbp # GBP 라인
    python lse_aum.py --no-history          # 스냅샷만(시계열 CSV 미저장)
"""

import argparse
import os
import sys
from datetime import date

import pandas as pd
import requests

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 콘솔(cp949)에서 한글/CSV 로그가 깨지지 않도록 UTF-8로 재설정
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ENDPOINT = "https://leverageshares.com/Lab_Forty_Scripts/php/etp_data.php"

# 티커 -> 상품페이지 슬러그(URL path segment [3]). 신규 상품은 여기에만 추가하면 된다.
SLUG = {
    "HNX3.L": "leverage-shares-3x-long-sk-hynix-etp",
    "SMG3.L": "leverage-shares-3x-long-samsung-electronics-etp",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://leverageshares.com",
    "Referer": "https://leverageshares.com/en-eu/etps/",
}

# Etp[0] 스냅샷에서 뽑아 표기할 필드(원본키 -> 라벨)
SNAP_FIELDS = {
    "ShareName": "ShareName", "Ticker": "Ticker", "Isin": "Isin",
    "Currency": "Currency", "date": "AsOf", "price": "NAV",
    "etp_securities_issued": "AUM", "value_underlying_assets": "GrossUnderlying",
    "liabilities": "Liabilities", "Outstanding_Shares_Par": "SharesOutstanding",
    "Leverage": "Leverage", "ArrangerFee": "ArrangerFee",
    "pctYTDChange": "YTD%", "Underlying_holding": "Underlying",
}


def _num(x):
    """문자열 숫자를 float으로. 빈값/None -> NaN."""
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return float("nan")


def fetch_etp(slug: str, locale: str = "en-eu") -> dict:
    r = requests.post(ENDPOINT, headers=HEADERS,
                      json={"name": slug, "documentLocaleType": locale}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"조회 실패 [{r.status_code}] {r.text[:200]}")
    txt = r.text.strip()
    if "Etp name is empty" in txt or not txt.startswith("{"):
        raise RuntimeError(f"슬러그 인식 실패(name='{slug}'): {txt[:120]}")
    data = r.json()
    if not data.get("Etp"):
        raise RuntimeError(f"Etp 데이터 없음(name='{slug}')")
    return data


def snapshot_row(data: dict) -> dict:
    e = data["Etp"][0]
    row = {}
    for k, label in SNAP_FIELDS.items():
        v = e.get(k)
        row[label] = _num(v) if label in ("NAV", "AUM", "GrossUnderlying",
                                           "Liabilities", "SharesOutstanding",
                                           "Leverage", "YTD%") else v
    return row


def history_df(data: dict, symbol: str, currency: str) -> pd.DataFrame:
    rows = data.get(currency, [])
    if not rows:
        raise RuntimeError(f"{currency} 시계열 없음")
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "date": "Date", "price": "NAV", "etp_securities_issued": "AUM",
        "turnoverBaseCurrency": "Turnover", "SoldShares": "SoldShares",
    })
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce").dt.date
    for c in ["NAV", "AUM", "Turnover", "SoldShares"]:
        if c in df.columns:
            df[c] = df[c].map(_num)
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df.insert(0, "Symbol", symbol)
    cols = ["Symbol", "Date", "NAV", "AUM", "Turnover", "SoldShares"]
    return df[[c for c in cols if c in df.columns]]


def main():
    ap = argparse.ArgumentParser(description="LSE Leverage Shares ETP AUM·NAV 수집")
    ap.add_argument("tickers", nargs="*", default=list(SLUG),
                    help=f"티커(기본: {' '.join(SLUG)})")
    ap.add_argument("--currency", default="Usd", choices=["Usd", "Gbp", "Eur"],
                    help="시계열 통화 배열(USD 라인=Usd 기본, GBP 라인=Gbp)")
    ap.add_argument("--locale", default="en-eu", help="documentLocaleType")
    ap.add_argument("--no-history", action="store_true", help="시계열 CSV 미저장(스냅샷만)")
    ap.add_argument("--outdir", default="data", help="저장 폴더")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    snaps, frames = [], []
    for tk in args.tickers:
        slug = SLUG.get(tk)
        if not slug:
            print(f"[건너뜀] {tk}: SLUG 매핑 없음 (lse_aum.py의 SLUG에 추가)", file=sys.stderr)
            continue
        try:
            data = fetch_etp(slug, args.locale)
        except Exception as e:
            print(f"[실패] {tk}: {e}", file=sys.stderr)
            continue

        snap = snapshot_row(data)
        snap = {"Symbol": tk, **snap}
        snaps.append(snap)
        print(f"[스냅샷] {tk}  AUM({snap.get('Currency')})={snap.get('AUM'):,.0f}  "
              f"NAV={snap.get('NAV')}  기초총액={snap.get('GrossUnderlying'):,.0f}  "
              f"(as of {snap.get('AsOf')})")

        if not args.no_history:
            try:
                df = history_df(data, tk, args.currency)
            except Exception as e:
                print(f"  [시계열 실패] {tk}/{args.currency}: {e}", file=sys.stderr)
                continue
            out = os.path.join(args.outdir, f"{tk.replace('.', '_')}_aum.csv")
            df.to_csv(out, index=False, encoding="utf-8-sig")
            print(f"  [완료] {len(df)}행 ({df['Date'].min()}~{df['Date'].max()}) -> {out}")
            print(df.tail(3).to_string(index=False))
            frames.append(df)

    if snaps:
        snap_out = os.path.join(args.outdir, "lse_aum_snapshot.csv")
        pd.DataFrame(snaps).to_csv(snap_out, index=False, encoding="utf-8-sig")
        print(f"[스냅샷 통합] {snap_out}")
    if len(frames) > 1:
        allout = os.path.join(args.outdir, "lse_aum_all.csv")
        pd.concat(frames, ignore_index=True).to_csv(allout, index=False, encoding="utf-8-sig")
        print(f"[시계열 통합] {allout}")


if __name__ == "__main__":
    main()
