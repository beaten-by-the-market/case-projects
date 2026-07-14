"""
NYSE 공개 거래정지 이력 API에서 전(全)미국 거래소 거래정지 원자료를 내려받는다.

이 엔드포인트는 NYSE의 공식 문서에 기재돼 있지 않다(undocumented).
랜딩 페이지(https://www.nyse.com/trade-halt)는 "1년치"라고 안내하지만,
실제로는 2019-02-22 이후 전체를 반환한다.

⚠ 이 데이터는 NYSE가 발표한 '통계'가 아니라 원자료다.
   거래소는 연간 거래정지 집계를 공표하지 않는다. 따라서 이 자료로 만든 수치는
   반드시 "우리가 원자료로 직접 집계했다"고 밝혀야 한다.

⚠ Reason 코드의 표기가 흔들린다: "News pending" / "News Pending" 둘 다 나온다.
   그리고 "Corporate Action"은 2024년부터 많아지는데, 이는 실제 행태 변화가 아니라
   코딩 방식 변경일 가능성이 크다. 연도 간 비교는 깨끗하지 않다.

사용:  python fetch_halts.py
출력:  h_YYYY-MM.csv (2025-07 ~ 2026-06),  p_YYYY-MM.csv (2024-07 ~ 2025-06)
"""

import csv
import io
import time
import urllib.request
from datetime import date

URL = (
    "https://www.nyse.com/api/trade-halts/historical/download"
    "?haltDateFrom={f}&haltDateTo={t}"
)

# 월 단위로 나눠 받는다 (한 번에 크게 요청하면 잘린다)
PERIODS = [
    ("p", 2024, 7, 2025, 6),   # 직전 12개월
    ("h", 2025, 7, 2026, 6),   # 최근 12개월
]


def months(y0, m0, y1, m1):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def month_bounds(y, m):
    first = date(y, m, 1)
    last = date(y + (m == 12), (m % 12) + 1, 1)
    return first.isoformat(), (last.toordinal() - 1 and date.fromordinal(last.toordinal() - 1)).isoformat()


def fetch(prefix, y0, m0, y1, m1):
    for y, m in months(y0, m0, y1, m1):
        f, t = month_bounds(y, m)
        url = URL.format(f=f, t=t)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8-sig")
        out = f"{prefix}_{y}-{m:02d}.csv"
        with open(out, "w", newline="", encoding="utf-8") as fh:
            fh.write(body)
        n = len(list(csv.DictReader(io.StringIO(body))))
        print(f"{out}: {n} rows")
        time.sleep(1.0)


if __name__ == "__main__":
    for prefix, y0, m0, y1, m1 in PERIODS:
        fetch(prefix, y0, m0, y1, m1)
