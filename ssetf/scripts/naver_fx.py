"""
Naver 금융 일별 환율(매매기준율) 수집.

https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd=FX_USDKRW&page=N
iframe 표를 페이지네이션하며 긁는다. 종가 환산에 쓰는 값은 '매매기준율'.

사용 예:
    python naver_fx.py USD HKD --start 2025-05-01
    python naver_fx.py FX_JPYKRW --start 2026-01-01 --outdir data

다른 모듈에서:
    from naver_fx import fetch_fx
    df = fetch_fx("USD", start="2025-05-01")   # columns: Date, Rate
"""

import argparse
import io
import os
import time
from datetime import date, datetime

import pandas as pd
import requests

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

URL = "https://finance.naver.com/marketindex/exchangeDailyQuote.naver"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"}
# 통화 별칭 -> Naver marketindexCd
CD = {
    "USD": "FX_USDKRW", "HKD": "FX_HKDKRW", "JPY": "FX_JPYKRW",
    "EUR": "FX_EURKRW", "CNY": "FX_CNYKRW", "GBP": "FX_GBPKRW",
}


def _to_date(v):
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) and not isinstance(v, datetime) else v.date()
    return datetime.strptime(str(v).replace(".", "-").replace("/", "-").strip(), "%Y-%m-%d").date()


def fetch_fx(currency: str, start=None, end=None, max_pages: int = 300) -> pd.DataFrame:
    """일별 매매기준율. 반환 columns: Date(date), Rate(float). 최신순 아닌 오름차순 정렬."""
    cd = CD.get(str(currency).upper(), str(currency))  # 'USD' 또는 raw 'FX_USDKRW'
    start_d, end_d = _to_date(start), _to_date(end)
    recs = []
    for page in range(1, max_pages + 1):
        r = requests.get(URL, params={"marketindexCd": cd, "page": page},
                         headers=HEADERS, timeout=15)
        r.encoding = "euc-kr"
        try:
            t = pd.read_html(io.StringIO(r.text))[0]
        except (ValueError, IndexError):
            break
        t = t.dropna(how="all")
        if t.empty:
            break
        # 컬럼: [날짜, 매매기준율, 전일대비, 현찰 사실때, 현찰 파실때, 송금 보낼때, 송금 받을때]
        dates = t.iloc[:, 0].astype(str)
        rates = pd.to_numeric(t.iloc[:, 1].astype(str).str.replace(",", ""), errors="coerce")
        page_rows = [(_to_date(d), rt) for d, rt in zip(dates, rates)
                     if d and d[0].isdigit() and pd.notna(rt)]
        if not page_rows:
            break
        recs.extend(page_rows)
        # 이 페이지 최소 날짜가 start보다 과거면 더 볼 필요 없음
        if start_d and min(d for d, _ in page_rows) <= start_d:
            break
        time.sleep(0.2)

    df = pd.DataFrame(recs, columns=["Date", "Rate"]).drop_duplicates("Date")
    df = df.sort_values("Date").reset_index(drop=True)
    if start_d:
        df = df[df["Date"] >= start_d]
    if end_d:
        df = df[df["Date"] <= end_d]
    return df.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description="Naver 일별 환율(매매기준율) 수집")
    ap.add_argument("currencies", nargs="+", help="USD HKD ... 또는 FX_USDKRW")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    for cur in args.currencies:
        df = fetch_fx(cur, start=args.start, end=args.end)
        if df.empty:
            print(f"[실패] {cur}: 데이터 없음")
            continue
        code = CD.get(cur.upper(), cur).replace("FX_", "")
        out = os.path.join(args.outdir, f"fx_{code}_naver.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[완료] {cur}: {len(df)}행 ({df['Date'].min()}~{df['Date'].max()}) -> {out}")
        print(df.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
