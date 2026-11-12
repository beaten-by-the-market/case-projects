"""s05 코드북 → data/final/agm_codebook.csv

s04 의 관찰 집계(code_summary.csv)에 뜻·근거를 붙이고, 조문 1~20호를 모두 행으로 넣는다(7·16·17호는 s10 스캔으로 관찰).
안건유형 코드 L0-0-2-N-0 의 N = 「증권의 발행 및 공시 등에 관한 규정」 제3-15조 ③항 N호 (docs/03 2026-11-12 대조).
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402

# 제3-15조 ③ 1~20호 (U-LEX 2022.3.7 고시본 기준 — 이후 개정분 반영 여부는 docs/03 참고)
AGENDA = {1: "재무제표의 승인", 2: "정관의 변경", 3: "이사의 선임", 4: "감사위원회 위원의 선임", 5: "감사의 선임",
          6: "이사의 해임", 7: "감사위원회 위원의 해임", 8: "감사의 해임", 9: "이사의 보수한도 승인",
          10: "감사의 보수한도 승인", 11: "주식매수선택권의 부여", 12: "회사의 합병", 13: "회사의 분할 또는 분할합병",
          14: "영업양수도(영업의 전부 또는 중요한 일부의 양도·양수)", 15: "주식교환 또는 주식이전",
          16: "준비금의 자본전입 또는 이에 따른 신주 발행", 17: "주주 외의 자에게 신주인수권 부여",
          18: "액면미달 가액 주식 발행(자본시장법 제165조의8)", 19: "자본 감소", 20: "기타 주주총회의 목적사항"}

FIXED = {
    ("ACODE", "00591"): ("문서", "서식(문서) 코드 — 주주총회소집공고", "DOCUMENT-NAME"),
    ("AASSOCNOTE", "COVER"): ("문서", "표지", ""),
    ("AASSOCNOTE", "CORRECTION"): ("문서", "정정신고(보고) — 정정공고 맨 앞 절", ""),
    ("AASSOCNOTE", "D-0-0-0-0"): ("본문 고정 절", "주주총회 소집공고 (일시·장소·회의목적사항 — 의안 목록은 자유 텍스트)", ""),
    ("AASSOCNOTE", "D-0-1-1-1"): ("본문 고정 절", "I.1.가 이사회 출석률 및 이사회 의안에 대한 찬반여부", ""),
    ("AASSOCNOTE", "D-0-1-1-2"): ("본문 고정 절", "I.1.나 이사회내 위원회에서의 사외이사(2026.7~ 독립이사) 등의 활동내역", ""),
    ("AASSOCNOTE", "D-0-1-2-0"): ("본문 고정 절", "I.2 사외이사(2026.7~ 독립이사) 등의 보수현황", ""),
    ("AASSOCNOTE", "D-0-2-1-0"): ("본문 고정 절", "II.1 최대주주등과의 거래 — 단일 거래규모가 일정규모 이상", ""),
    ("AASSOCNOTE", "D-0-2-2-0"): ("본문 고정 절", "II.2 최대주주등과의 거래 — 특정인과의 거래총액이 일정규모 이상", ""),
    ("AASSOCNOTE", "D-0-3-1-1"): ("본문 고정 절", "III.1.가 사업의 개요 — 업계의 현황", ""),
    ("AASSOCNOTE", "D-0-3-1-2"): ("본문 고정 절", "III.1.나 사업의 개요 — 회사의 현황", ""),
    ("AASSOCNOTE", "D-4-0-0-0"): ("본문 고정 절", "IV. 사업보고서 및 감사보고서 첨부 (서식 2.7~2.8 에선 '※ 참고사항' 절에 이 코드)", ""),
    ("AASSOCNOTE", "D-4-1-0-0"): ("본문 고정 절", "IV.1 제출 개요 (서식 2.9~)", ""),
    ("AASSOCNOTE", "D-4-2-0-0"): ("본문 고정 절", "IV.2 사업보고서 및 감사보고서 첨부 (서식 2.9~)", ""),
    ("AASSOCNOTE", "D-5-0-0-0"): ("본문 고정 절", "※ 참고사항 (서식 2.9~)", ""),
    ("ACLASS", "MANDATORY"): ("표·절 성격", "필수 기재 절(SECTION-1~4)", ""),
    ("ACLASS", "RPT_SUB"): ("표·절 성격", "사업보고서 등 제출·통지 표 묶음 (서식 2.9~)", ""),
    ("ACLASS", "NOTED_ITEMS"): ("표·절 성격", "※ 참고사항 표 묶음 (서식 2.7~)", ""),
    ("ACLASS", "EXTRACTION"): ("표·절 성격", "추출 대상 표 (RPT_SUB·NOTED_ITEMS 안)", ""),
    ("ACODE", "NOTE_ITEM"): ("셀", "※ 참고사항 본문 셀 (전자투표·의결권 대리행사 안내 등, 자유 텍스트)", ""),
    ("AUNIT", "SUB_DT"): ("셀", "사업보고서 등 제출(예정)일 — AUNITVALUE=YYYYMMDD 또는 '-'", ""),
    ("AUNIT", "NTC_TYPE"): ("셀", "사업보고서 등 통지 방식 — AUNITVALUE 1=2주전 통지, 2=2주전 공고, 3=1주전 전자문서 발송, "
                                  "4=1주전 회사 홈페이지 게재, '-'=해당없음", ""),
}


def main():
    obs = {}
    for r in csv.DictReader((ROOT / "data/final/code_summary.csv").open(encoding="utf-8-sig")):
        obs[(r["attr"], r["value"])] = r
    n_docs = len(list((ROOT / "data/raw/xml").iterdir()))
    out = []

    def row(attr, tag, value, group, meaning, basis):
        o = obs.get((attr, value), {})
        out.append({"group": group, "attr": attr, "tag": tag or o.get("tag", ""), "code": value, "meaning": meaning,
                    "basis": basis, "n_docs": o.get("n_docs", "0"), "share": f"{int(o.get('n_docs', 0)) / n_docs:.1%}",
                    "yr_range": f"{o['yr_min']}-{o['yr_max']}" if o else "",
                    "observed_title": o.get("top_texts", "").split(" | ")[0].rsplit("(", 1)[0] if o else ""})

    for (attr, value), (group, meaning, tag) in FIXED.items():
        row(attr, tag, value, group, meaning, "서식 관찰")
    for n, name in AGENDA.items():
        row("AASSOCNOTE", "TITLE", f"L0-0-2-{n}-0", "안건유형", name, f"증권발행공시규정 제3-15조③ {n}호")
        if n in (3, 4, 5):
            row("AASSOCNOTE", "TITLE", f"L0-0-2-{n}-1", "안건유형(하위)", f"{name} — 후보자 확인서 (2020~)", "서식 관찰")
    with (ROOT / "data/final/agm_codebook.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    missing = [k for k in obs if k not in {(r["attr"], r["code"]) for r in out}]
    print(f"코드북 {len(out)}행, 표본 문서 {n_docs}, 코드북에 없는 관찰코드 {missing}")


if __name__ == "__main__":
    main()
