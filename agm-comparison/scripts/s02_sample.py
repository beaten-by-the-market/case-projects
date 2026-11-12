"""s02 층화 표본 → data/interim/sample.csv

층: 접수연도(2016~2026) × corp_cls(Y 유가·K 코스닥·N 코넥스·E 기타) × 시기(peak=2~3월 / off=그 외)
    각 층 1건(원본), 연도마다 정정공고 1건 추가. 난수 시드 고정(재현 가능).
"""
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402

SEED = 20261112
IN = ROOT / "data/interim/filings_e006.csv"
OUT = ROOT / "data/interim/sample.csv"


def main():
    rows = list(csv.DictReader(IN.open(encoding="utf-8-sig")))
    strata = defaultdict(list)
    for r in rows:
        yr, mo = r["rcept_dt"][:4], int(r["rcept_dt"][4:6])
        season = "peak" if mo in (2, 3) else "off"
        rev = "revision" if r["report_nm"].startswith("[") else "original"
        key = (yr, r["corp_cls"], season) if rev == "original" else (yr, "*", "revision")
        strata[key].append(r)
    rnd = random.Random(SEED)
    out = []
    for key in sorted(strata):
        pick = rnd.choice(sorted(strata[key], key=lambda r: r["rcept_no"]))
        out.append({**pick, "stratum": "|".join(key)})
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"층 {len(strata)} → 표본 {len(out)}건 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
