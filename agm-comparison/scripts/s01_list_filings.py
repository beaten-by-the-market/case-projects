"""s01 주주총회소집공고(E006) 목록 → data/interim/filings_e006.csv

OpenDART list.json, pblntf_detail_ty='E006', last_reprt_at='N'(정정본·원본 모두).
corp_code 없이 부르면 조회기간이 3개월까지라 월 단위로 돈다. 이미 받은 월은 건너뛴다(data/raw/list/YYYYMM.json).

사용법
    python scripts/s01_list_filings.py                    # 2016-01 ~ 2026-10
    python scripts/s01_list_filings.py --from 202601 --to 202603
"""
import argparse
import calendar
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT, Keys, Net  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
RAW = ROOT / "data/raw/list"
OUT = ROOT / "data/interim/filings_e006.csv"


def months(a: str, b: str):
    y, m = int(a[:4]), int(a[4:])
    while (y, m) <= (int(b[:4]), int(b[4:])):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch_month(keys: Keys, y: int, m: int) -> list[dict]:
    p = RAW / f"{y}{m:02d}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    rows, page = [], 1
    while True:
        params = {"crtfc_key": keys.cur, "bgn_de": f"{y}{m:02d}01",
                  "end_de": f"{y}{m:02d}{calendar.monthrange(y, m)[1]}",
                  "pblntf_detail_ty": "E006", "last_reprt_at": "N", "page_no": page, "page_count": 100}
        j = Net.get(LIST_URL, params=params, timeout=60).json()
        if j["status"] == "020":
            keys.rotate()
            continue
        if j["status"] == "013":
            break
        if j["status"] != "000":
            raise SystemExit(f"{y}{m:02d} p{page}: {j}")
        rows += j["list"]
        if page >= j["total_page"]:
            break
        page += 1
    RAW.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default="201601")
    ap.add_argument("--to", dest="b", default="202610")
    a = ap.parse_args()
    keys, allrows = Keys(), []
    for y, m in months(a.a, a.b):
        rows = fetch_month(keys, y, m)
        print(f"{y}-{m:02d} {len(rows)}", flush=True)
        allrows += rows
    cols = ["rcept_no", "rcept_dt", "corp_code", "corp_name", "stock_code", "corp_cls", "report_nm", "flr_nm", "rm"]
    seen = set()
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(allrows, key=lambda r: r["rcept_no"]):
            if r["rcept_no"] not in seen:
                seen.add(r["rcept_no"])
                w.writerow(r)
    print(f"→ {OUT.relative_to(ROOT)} {len(seen)}건")


if __name__ == "__main__":
    main()
