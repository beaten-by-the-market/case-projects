"""s02b 보충 표본 → data/interim/sample_extra.csv

s02 층화 표본(95건)에서 안건유형 코드 L0-0-2-N 이 7·8·14~18 번이 비었다(드문 안건).
드문 안건은 임시주총에 몰리므로 비성수기(2·3월 외) 원본 공고를 150건 더 뽑고,
신서식 6.1(2026-07-23) 확인용으로 2026-08~10월 접수분 25건을 더한다. s02 표본과 겹치지 않게, 시드 고정.
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402

SEED = 20261113


def main():
    rows = list(csv.DictReader((ROOT / "data/interim/filings_e006.csv").open(encoding="utf-8-sig")))
    done = {r["rcept_no"] for r in csv.DictReader((ROOT / "data/interim/sample.csv").open(encoding="utf-8-sig"))}
    orig = [r for r in rows if not r["report_nm"].startswith("[") and r["rcept_no"] not in done]
    off = [r for r in orig if int(r["rcept_dt"][4:6]) not in (2, 3)]
    new = [r for r in orig if r["rcept_dt"] >= "20260801"]
    rnd = random.Random(SEED)
    a = rnd.sample(off, 150)
    b = rnd.sample([r for r in new if r not in a], 25)
    out = [{**r, "stratum": "extra|off"} for r in a] + [{**r, "stratum": "extra|form6.1"} for r in b]
    with (ROOT / "data/interim/sample_extra.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"보충 표본 {len(out)}건")


if __name__ == "__main__":
    main()
