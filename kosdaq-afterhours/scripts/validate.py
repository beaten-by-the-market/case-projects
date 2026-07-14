"""수집 데이터 검증. 통과 못 하면 분석 진행 금지.

1. 거래대금 교차검증: rank_invest_date 의 (매도대금+매수대금)/2  vs  hist_info F15023(거래대금).
   두 값은 서로 다른 endpoint 에서 왔다. 어긋나면 거래대금 정의를 잘못 잡은 것이다.
2. 거래여부 일치: 거래량>0 (rank) vs 거래량>0 (hist).
3. 커버리지: 거래일·종목 수.
4. 공시: dcnt 잘림 여부 · 일별 건수 분포.
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
DATA = Path(__file__).resolve().parent.parent / "data"
csv.field_size_limit(1 << 24)


def i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def main():
    # ── rank_invest_date (KRX 코스닥) ──
    rank = {}          # (code, date) -> (amt, vol)
    days_krx, days_kospi = set(), set()
    codes_krx = set()
    with (DATA / "daily_krx.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["fam"] != "m003":
                days_kospi.add(r["date"])
                continue
            days_krx.add(r["date"])
            codes_krx.add(r["code"])
            amt = (i(r["amt_sell"]) + i(r["amt_buy"])) / 2
            vol = max(i(r["vol_sell"]), i(r["vol_buy"]))
            rank[(r["code"], r["date"])] = (amt, vol)
    print(f"[rank] 코스닥 {len(days_krx)}거래일 · {len(codes_krx):,}종목 · {len(rank):,}행")
    print(f"[rank] 코스피 {len(days_kospi)}거래일")

    # ── hist_info OHLC ──
    hist = {}
    codes_ohlc = set()
    with (DATA / "ohlc_kosdaq.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hist[(r["code"], r["date"])] = (i(r["amt"]), i(r["vol"]))
            codes_ohlc.add(r["code"])
    print(f"[hist] {len(codes_ohlc):,}종목 · {len(hist):,}행\n")

    # ── 1. 거래대금 교차검증 ──
    common = set(rank) & set(hist)
    print(f"--- 1. 거래대금 교차검증 (공통 {len(common):,}행) ---")
    errs, zero_both, mismatch_sign = [], 0, 0
    big = []
    for k in common:
        a_rank, _ = rank[k]
        a_hist, _ = hist[k]
        if a_hist == 0 and a_rank == 0:
            zero_both += 1
            continue
        if a_hist == 0 or a_rank == 0:
            mismatch_sign += 1
            continue
        e = abs(a_rank - a_hist) / a_hist
        errs.append(e)
        if e > 0.01:
            big.append((e, k, a_rank, a_hist))
    if errs:
        errs.sort()
        print(f"  상대오차  중앙값 {statistics.median(errs)*100:.4f}%  "
              f"평균 {statistics.mean(errs)*100:.4f}%  p99 {errs[int(len(errs)*0.99)]*100:.4f}%")
        within = sum(1 for e in errs if e <= 0.01) / len(errs)
        print(f"  오차 1% 이내: {within*100:.2f}%  ({len(errs):,}행 중)")
    print(f"  양쪽 0 (무거래): {zero_both:,}행")
    print(f"  한쪽만 0: {mismatch_sign:,}행", end="")
    print("  ← 0이면 완벽 일치" if mismatch_sign == 0 else "  ← 확인 필요")
    if big:
        big.sort(reverse=True)
        print(f"  오차 1% 초과 {len(big):,}행. 상위 5:")
        for e, k, ar, ah in big[:5]:
            print(f"    {k}  rank={ar:,.0f}  hist={ah:,.0f}  오차 {e*100:.1f}%")

    # ── 2. 거래여부 일치 ──
    fp = sum(1 for k in common if rank[k][1] > 0 and hist[k][1] == 0)
    fn = sum(1 for k in common if rank[k][1] == 0 and hist[k][1] > 0)
    print(f"\n--- 2. 거래여부(거래량>0) 일치 ---")
    print(f"  rank만 거래: {fp:,}  ·  hist만 거래: {fn:,}   ← 둘 다 0이어야 정상")

    # ── 3. 커버리지 ──
    print(f"\n--- 3. 커버리지 ---")
    only_rank = codes_krx - codes_ohlc
    only_ohlc = codes_ohlc - codes_krx
    print(f"  rank에만 있는 종목: {len(only_rank):,}  ← 상폐 종목(code_info에 없음). 정상")
    print(f"  ohlc에만 있는 종목: {len(only_ohlc):,}")
    per_day = Counter(d for _, d in rank)
    vals = sorted(per_day.values())
    print(f"  일별 종목수: 최소 {vals[0]:,} · 중앙 {vals[len(vals)//2]:,} · 최대 {vals[-1]:,}")

    # ── 4. 공시 ──
    print(f"\n--- 4. 공시 ---")
    per_day_g = Counter()
    kosdaq = 0
    no_code = 0
    with (DATA / "gongsi.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per_day_g[r["date"]] += 1
            if r["mtvcd"] == "320":
                kosdaq += 1
                if not r["code"].strip():
                    no_code += 1
    g = sorted(per_day_g.values())
    print(f"  거래일 {len(per_day_g)} · 총 {sum(g):,}건 · 일별 최소 {g[0]} / 중앙 {g[len(g)//2]} / 최대 {g[-1]}")
    print(f"  dcnt(3000) 도달일: {sum(1 for v in g if v >= 3000)}  ← 0이어야 잘림 없음")
    print(f"  코스닥(320) {kosdaq:,}건 · 종목코드 없는 건 {no_code:,}")


if __name__ == "__main__":
    main()
