"""s06 뉴스로 찾은 표적 공고 → data/interim/sample_targets.csv

층화·보충 표본(270건)에 한 번도 안 나온 안건유형(제3-15조③ 7·15~18호)을 찾으려고,
뉴스 검색으로 해당 안건이 있었던 회사·시기를 찾고 그 회사의 소집공고를 목록(s01)에서 고른다.
받기는 s03 (--sample data/interim/sample_targets.csv), 코드 추출은 s04.

TARGETS 의 회사명은 현재 DART 회사명(옛 쌍용자동차 = KG모빌리티). 근거 기사는 docs/03.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402

# (회사명, 접수 시작, 접수 끝, 기대 호, 근거)
TARGETS = [
    ("동양생명", "20260601", "20261031", 15, "우리금융 포괄적 주식교환 임시주총(dealsite 165909)"),
    ("신세계푸드", "20260401", "20261031", 15, "이마트 포괄적 주식교환 임시주총"),
    ("현대홈쇼핑", "20260301", "20261031", 15, "현대지에프홀딩스 완전자회사 편입 임시주총(디지털데일리 2026.4.20)"),
    ("현대지에프홀딩스", "20260301", "20261031", 15, "현대홈쇼핑 주식교환 — 모회사 측 임시주총"),
    ("KG모빌리티", "20181001", "20181031", 18, "쌍용자동차 2018.10.25 임시주총 '주식의 액면가액 미달발행 승인의 건'(뉴스핌·MTN)"),
    ("씨씨에스", "20230101", "20261031", 7, "소액주주 이사·감사 해임 의안상정 가처분(IB토마토) — 경영권 분쟁 회사, 원본 공고 전부"),
]


def main():
    rows = list(csv.DictReader((ROOT / "data/interim/filings_e006.csv").open(encoding="utf-8-sig")))
    out = []
    for name, a, b, no, why in TARGETS:
        hit = [r for r in rows if r["corp_name"] == name and a <= r["rcept_dt"] <= b and not r["report_nm"].startswith("[")]
        for r in hit:
            out.append({**r, "stratum": f"target|{no}호", "target_no": no, "news_basis": why})
        print(f"{name} {a}~{b} 기대 {no}호: {len(hit)}건")
    with (ROOT / "data/interim/sample_targets.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"표적 {len(out)}건")


if __name__ == "__main__":
    main()
