"""s00 보도자료 → 대조 정답지 CSV.

PDF 텍스트 레이어 주의(docs/00-보도자료-정리.md §7): 7쪽에서 '□ 코스닥시장' 제목이 유가 84~96번보다
먼저 추출된다. 그래서 시장은 제목이 아니라 행의 '시장구분' 열(코스피/코스닥)로 가른다.

출력
  data/final/press_list151.csv     붙임2 — no, name, gics, market, pbr
  data/final/press_sector.csv      붙임1 — market, gics, cut_pbr, n_univ, n_sel, n_exempt, n_pub
  data/final/press_totals.csv      본문 총계
"""
import csv
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "source" / "2026-10-30_KRX_보도자료_저PBR기업_최초선정.pdf"
OUT = ROOT / "data" / "final"

GICS = ["에너지", "소재", "산업재", "자유소비재", "필수소비재", "헬스케어", "금융",
        "정보기술", "커뮤니케이션", "유틸리티", "부동산"]

# 붙임1 (4쪽) — 표가 텍스트 레이어에서 셀 순서가 섞여 손으로 옮기고, 아래 assert 로 합계를 검산한다.
# (market, gics, cut_pbr, n_univ, n_sel, n_exempt, n_pub)
SECTOR = [
    ("KOSPI", "에너지", 0.28, 10, 1, 0, 1), ("KOSPI", "소재", 0.27, 166, 31, 8, 23),
    ("KOSPI", "산업재", 0.40, 173, 24, 2, 22), ("KOSPI", "자유소비재", 0.27, 149, 20, 2, 18),
    ("KOSPI", "필수소비재", 0.38, 72, 13, 1, 12), ("KOSPI", "헬스케어", 0.51, 60, 12, 4, 8),
    ("KOSPI", "금융", 0.42, 48, 5, 1, 4), ("KOSPI", "정보기술", 0.63, 56, 6, 0, 6),
    ("KOSPI", "커뮤니케이션", 0.42, 27, 3, 1, 2), ("KOSPI", "유틸리티", 0.25, 14, 0, 0, 0),
    ("KOSPI", "부동산", 0.11, 4, 0, 0, 0), ("KOSPI", "업종미분류", None, 0, 0, 0, 0),
    ("KOSDAQ", "에너지", 0.17, 6, 1, 1, 0), ("KOSDAQ", "소재", 0.28, 132, 7, 1, 6),
    ("KOSDAQ", "산업재", 0.31, 261, 11, 1, 10), ("KOSDAQ", "자유소비재", 0.25, 171, 6, 2, 4),
    ("KOSDAQ", "필수소비재", 0.31, 80, 4, 1, 3), ("KOSDAQ", "헬스케어", 0.51, 272, 12, 2, 10),
    ("KOSDAQ", "금융", 0.31, 42, 2, 1, 1), ("KOSDAQ", "정보기술", 0.39, 559, 22, 5, 17),
    ("KOSDAQ", "커뮤니케이션", 0.31, 106, 3, 1, 2), ("KOSDAQ", "유틸리티", 0.40, 4, 1, 0, 1),
    ("KOSDAQ", "부동산", 0.17, 3, 1, 0, 1), ("KOSDAQ", "업종미분류", None, 16, 0, 0, 0),
]
TOTALS = {  # 본문 1~2쪽
    ("KOSPI", "n_univ"): 779, ("KOSDAQ", "n_univ"): 1652,
    ("KOSPI", "n_sel"): 115, ("KOSDAQ", "n_sel"): 70,
    ("KOSPI", "n_exempt"): 19, ("KOSDAQ", "n_exempt"): 15,
    ("KOSPI", "n_pub"): 96, ("KOSDAQ", "n_pub"): 55,
    ("KOSPI", "plan_exempt"): 19, ("KOSDAQ", "plan_exempt"): 15,
    ("KOSPI", "plan_not_exempt"): 10, ("KOSDAQ", "plan_not_exempt"): 5,
    ("KOSPI", "plan_not_lowpbr"): 5, ("KOSDAQ", "plan_not_lowpbr"): 8,
}

# pypdf 는 표 한 쪽을 한 줄로 붙여 낸다: "...0.162 BGF산업재코스피0.193 CS홀딩스..."
# → 행 = 번호 · 종목명 · 업종 · 시장 · PBR(소수 2자리). PBR 뒤에 바로 다음 행 번호가 붙는다.
ROW = re.compile(r"(\d{1,2}) ?(\S.*?)(" + "|".join(GICS) + r")(코스피|코스닥)(\d\.\d{2})")


def list151() -> list[dict]:
    reader = PdfReader(PDF)
    out = []
    for page in reader.pages[4:8]:
        text = page.extract_text().replace("\n", "")
        # 표 머리말 "최근반기('26.10.22) PBR" 뒤만 본다 (7쪽은 머리말이 두 번)
        parts = re.split(r"\d{2}\.\d{2}\.\d{2}\)\s*PBR", text)[1:]
        for m in (m for p in parts for m in ROW.finditer(p)):
            out.append({"no": int(m[1]), "name": m[2].strip(), "gics": m[3],
                        "market": "KOSPI" if m[4] == "코스피" else "KOSDAQ", "pbr": m[5]})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list151()
    for mk, n in (("KOSPI", 96), ("KOSDAQ", 55)):
        got = [r for r in rows if r["market"] == mk]
        assert len(got) == n, (mk, len(got))
        assert sorted(r["no"] for r in got) == list(range(1, n + 1)), mk
    # 붙임2 업종별 사수 = 붙임1 공표 사수
    for mk, g, *_rest, n_pub in SECTOR:
        assert sum(1 for r in rows if r["market"] == mk and r["gics"] == g) == n_pub, (mk, g)
    # 붙임2 PBR ≤ 붙임1 업종 기준 PBR
    cut = {(s[0], s[1]): s[2] for s in SECTOR}
    assert all(float(r["pbr"]) <= cut[(r["market"], r["gics"])] for r in rows)
    # 붙임1 합계 = 본문 총계
    for mk in ("KOSPI", "KOSDAQ"):
        for j, col in enumerate(("n_univ", "n_sel", "n_exempt", "n_pub"), start=3):
            assert sum(s[j] for s in SECTOR if s[0] == mk) == TOTALS[(mk, col)], (mk, col)
        assert sum(s[4] - s[5] for s in SECTOR if s[0] == mk) == TOTALS[(mk, "n_pub")]

    with open(OUT / "press_list151.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["market", "no", "name", "gics", "pbr"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["market"] != "KOSPI", r["no"])))
    with open(OUT / "press_sector.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["market", "gics", "cut_pbr", "n_univ", "n_sel", "n_exempt", "n_pub"])
        w.writerows(SECTOR)
    with open(OUT / "press_totals.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["market", "item", "value"])
        w.writerows([(mk, k, v) for (mk, k), v in TOTALS.items()])
    print(f"151사 추출·검산 OK — KOSPI 96, KOSDAQ 55, 업종 사수·기준 PBR·총계 모두 일치")


if __name__ == "__main__":
    main()
