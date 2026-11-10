"""공용 규칙 — 회차별 순자산 근거 보고서 고르기 (R4).

R4: 순자산 = PBR 기준일 현재 가장 최근 정기보고서(사업·반기)의 재무상태표 자본총계. 분기보고서는 쓰지 않는다.

고르는 방법
  1) doc_class ∈ {annual, semi}, 접수일 ≤ 기준일 인 보고서 중 작성기준일(period_end)이 가장 늦은 것
  2) 그 작성기준일 안에서 접수일 ≤ 기준일 인 버전 중 가장 늦은 접수 — 기준일 뒤에 낸 정정은 그날 알 수 없었다
결산월이 12월이 아닌 회사(기신정기 3월·세원정공 6월 등)도 같은 규칙으로 자연히 처리된다.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DART_MAIN = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
DART_VIEWER = ("https://dart.fss.or.kr/report/viewer.do?rcpNo={rcp}&dcmNo={dcm}&eleId={ele}"
               "&offset={off}&length={len}&dtd={dtd}")


def load_rounds() -> list[dict]:
    return list(csv.DictReader(open(ROOT / "data/interim/rounds.csv", encoding="utf-8")))


def periodic_filings(conn, stock_codes: list[str] | None = None) -> dict[str, list[tuple]]:
    """stock_code → [(rcept_no, rcept_dt, doc_class, period_end, report_nm, rev_kind)] (접수 순)."""
    cur = conn.cursor()
    sql = ("SELECT stock_code, rcept_no, rcept_dt, doc_class, period_end, report_nm, rev_kind FROM pr_filing "
           "WHERE doc_class IN ('annual','semi') AND period_end IS NOT NULL AND stock_code IS NOT NULL")
    cur.execute(sql)
    out = defaultdict(list)
    want = set(stock_codes) if stock_codes else None
    for sc, *rest in cur.fetchall():
        if want is None or sc in want:
            out[sc].append(tuple(rest))
    for v in out.values():
        v.sort()
    return out


def choose_filing(filings: list[tuple], base_date: str) -> tuple | None:
    seen = [f for f in filings if f[1] <= base_date]
    if not seen:
        return None
    pe = max(f[3] for f in seen)
    return max((f for f in seen if f[3] == pe), key=lambda f: f[0])
