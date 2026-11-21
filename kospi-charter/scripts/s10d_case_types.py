"""s10d 배당기준일 공시 유형 — 회사 공시 실수 · 빈틈 유형별로 해당 회사를 모두 모은다

왜: 사용자 지시(2026-11-21) — 기본(2025 결산 사업보고서 첨부 정관 + 2026 정기주총 이후 안건 · 가결)을 넘어,
    회사 공시 실수와 빈틈을 수습한 유형을 정리하고 유형마다 해당 종목 전체를 웹페이지 탭에 보인다.
    회사 목록은 손으로 적지 않고 판정 데이터 · 점검 기록에서 규칙으로 뽑는다(어느 칸으로 뽑았는지 유형마다 'rule').
    공시 문서의 유형만 담는다(2026-11-22: 부결 · 미결 · 부칙 효력 조건 · 상장 전 주총은 회사 공시 잘못이 아니라 '배당 특이사항' 탭으로 옮기고,
    특이사항에 있던 첨부 정관 읽기 실패 · 정관 문구 오류를 여기로 옮김) — 상장공시시스템 신고가 정관과 다른 것(신고 대조 불일치)은 판정의 결과라 넣지 않는다
    (사용자 지시 2026-11-22, 옛 8번 '신고가 정관과 반대' 뺌. 배당기준일 탭 '신고 대조' 필터로 본다).

입력  site/dividend.js(s10 이 만든 판정)
      data/interim/s09m_other_basis.json · s09k_blank.json · s09k_text_sections.json · s10_doc_notes.json(s10 이 씀)
출력  data/final/dividend_cases.json  {types: [...], rows: [...]} → s10 이 dividend.js 'dividend_cases' 표로 싣는다 ('공시 유형' 탭)

    python -X utf8 scripts/s10_dividend_site.py
    python -X utf8 scripts/s09k_aoi_history.py blank      # 공고 쪽 규칙 (로컬)
    python -X utf8 scripts/s10d_case_types.py
    python -X utf8 scripts/s10_dividend_site.py            # 유형 표를 싣고 다시 만들기
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, INTERIM, ROOT, read_json, write_json  # noqa: E402

OUT = FINAL / "dividend_cases.json"
DART = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="

TYPES = [
    {"id": "stale", "name": "사업보고서 첨부 정관이 옛 판",
     "problem": "1~2년 앞선 주주총회에서 이미 바꾼 기준일 조항이 2025 결산 사업보고서 첨부 정관에는 개정 전 문구로 남아 있다.",
     "fix": "2024-01-01부터의 주주총회 소집공고 '정관의 변경' 대비표를 모두 판별하고, 변경 전 · 변경 후 문구를 첨부 정관과 대조해 옛 판일 때만 KIND 주주총회결과(가결)로 바꿨다.",
     "rule": "판정 데이터 basis_stale_charter (s09j)"},
    {"id": "other_item", "name": "정관 변경을 다른 안건 항목에 기재",
     "problem": "소집공고의 '정관의 변경' 서식 항목이 아니라 '재무제표의 승인' 같은 다른 안건 항목 안이나 본문 끝 별첨에 대비표를 적어, 서식 코드로는 찾을 수 없다.",
     "fix": "서식 코드 · 제목이 없으면 DART 표준 문구('그 외의 정관변경에 관한 건' 등)와 대비표 머리로 글에서 절을 찾는 대체 경로를 넣었다.",
     "rule": "s09k blank 이 모든 공고 원문에서 기록한 글로 찾은 절 (s06 text_fallback)"},
    {"id": "no_table", "name": "대비표를 글로 싣지 않음",
     "problem": "'정관의 변경' 항목에 조문이 없다. '첨부된 대비표 참고'라고 적고 첨부가 없거나, '하단 참조'로 대비표를 그림으로 넣거나, 안건 이름만 적었다.",
     "fix": "그림은 DART 에서 받아 읽었다. 조문이 공시되지 않은 회사는 반기보고서 '정관 변경 이력' · KIND 주주총회결과 · 상장공시시스템 신고로 판정하고 조문 미공시 주의를 붙였다.",
     "rule": "s09k blank (조 머리 없음 + 첨부 · 참조 문구, 대비표 그림) · s09m 회사 공시 오류"},
    {"id": "no_agm_change", "name": "주주총회 없이 바뀐 정관을 첨부",
     "problem": "주주총회에서 고친 적 없는 기준일 조항이 사업보고서 첨부 정관에서 바뀌어 있다.",
     "fix": "전년도 사업보고서 첨부 정관과 정관 변경 이력으로 확인해 전년도 정관을 근거로 했다. 앞으로는 '첨부 정관 N · 신고 Y' 불일치만 확인한다.",
     "rule": "s09m '주주총회 개정 없이'"},
    {"id": "unreadable", "name": "사업보고서 첨부 정관을 읽을 수 없음",
     "problem": "사업보고서에 붙은 정관을 읽을 수 없다. 보안정책상 암호화된 PDF 를 그대로 첨부했거나, DART 가 첨부 PDF 를 서비스하지 않거나, 정관 이미지가 중간에서 끊겨 배당 조가 없다.",
     "fix": "전년도 사업보고서 첨부 정관이나 사업보고서 본문 '배당관련 예측가능성' 표로 판별하고, 그 뒤 주주총회 안건과 KIND 가결로 지금 태그를 정했다.",
     "rule": "s10 특이사항의 첨부 정관 읽기 실패 분류 (s10_doc_notes.json)"},
    {"id": "charter_error", "name": "정관 문구 자체의 오류",
     "problem": "정관 조문에 잘못이 있다. 배당 조가 엉뚱한 항(임시주총 기준일 항 등)을 가리키거나, 개정한 항에 옛 문구가 남았거나, 부칙의 변경 내역이 본문에 반영되지 않았다.",
     "fix": "정관 문맥 · 표준정관 · 같은 유형 선례로 회사가 뜻한 조항을 정해 판정하고, 문구의 잘못을 회사마다 적었다.",
     "rule": "s10 특이사항의 정관 오기재 · 부칙 · 본문 불일치 · 임시주총 조항 참조 (s10_doc_notes.json)"},
]
COLS = ["type", "market", "stock_code", "corp_name", "sub", "tag", "tag_current", "filed", "filed_cmp", "effect", "text", "links"]


def rows_of_site() -> list[dict]:
    js = (ROOT / "site" / "dividend.js").read_text(encoding="utf-8")
    d = json.loads(js[js.index("{"):js.rindex("}") + 1])
    t = d["tables"]["dividend"]
    return [dict(zip(t["cols"], r)) for r in t["rows"]]


def link(label: str, url: str | None, title: str = "") -> dict | None:
    return {"label": label, "url": url, "title": title or label} if url else None


def main() -> None:
    R = rows_of_site()
    by = {r["stock_code"]: r for r in R}
    other = {k: v for k, v in read_json(INTERIM / "s09m_other_basis.json").items() if not k.startswith("_")}
    blank = read_json(INTERIM / "s09k_blank.json") if (INTERIM / "s09k_blank.json").exists() else []
    out: list[dict] = []

    def add(tid: str, code: str, sub: str, effect: str, text: str, links: list, name: str | None = None, market: str | None = None):
        r = by.get(code, {})
        out.append({"type": tid, "market": r.get("market") or market or "", "stock_code": code, "corp_name": r.get("corp_name") or name or "",
                    "sub": sub, "tag": r.get("tag"), "tag_current": r.get("tag_current"), "filed": r.get("filed"), "filed_cmp": r.get("filed_cmp"),
                    "effect": effect, "text": text, "links": [x for x in links if x]})

    def changed(r: dict) -> bool:
        return bool(r.get("changed")) or r.get("tag") != r.get("tag_current")

    # 1. 첨부 정관이 옛 판
    for r in R:
        if r.get("basis_stale_charter"):
            add("stale", r["stock_code"], r.get("basis_agm_date") or "", "판정 바뀜" if changed(r) else "판정 그대로",
                r.get("basis_note") or r.get("note") or "",
                [link(f"소집공고 {r.get('basis_notice_rcept_no', '')[:8]}", r.get("basis_notice_url"), "DART 주주총회소집공고"),
                 link(f"결과공시 {r.get('basis_agm_date') or ''}", r.get("basis_result_url"), "KIND 주주총회결과")])

    # 2. 다른 항목에 기재 (s06 text_fallback — s09k blank 가 모든 공고 원문에서 기록)
    import s09i_pre_agm as I
    nm = {n["rcept_no"]: n for ns in I.notice_list().values() for n in ns}
    for m in read_json(INTERIM / "s09k_text_sections.json"):
        rc, code = m["rcept_no"], m["stock_code"]
        if not code:
            continue
        r = by.get(code, {})
        hit = r.get("basis_notice_rcept_no") == rc
        where = (f"'{m['where_title']}' 항목에 기재" if m["where_code"].startswith("L0-0-2-") and m["where_title"]
                 else "'정관의 변경' 항목 없이 본문 별첨으로만 기재")
        add("other_item", code, f"{rc[:4]}-{rc[4:6]}-{rc[6:8]} 공고", "판정 바뀜" if hit and changed(r) else "판정 그대로", f"정관 변경을 {where}",
            [link(f"소집공고 {rc[:8]}", DART + rc, (nm.get(rc) or {}).get("report_nm") or "DART 주주총회소집공고")],
            name=(nm.get(rc) or {}).get("corp_name"))

    # 3. 대비표를 글로 싣지 않음 (s09m 회사 공시 오류 + s09k blank)
    seen3 = set()
    for code, o in other.items():
        if "대비표" in o["label"] or "'정관의 변경' 항목" in o["label"]:
            add("no_table", code, "첨부 없음" if "첨부" in o["label"] else "항목 없음", "판정 바뀜" if changed(by.get(code, {})) else "판정 그대로",
                o["label"].replace("회사 공시 오류: ", "") + ". " + o["evidence"], o.get("links") or [])
            seen3.add(code)
    for b in blank:
        if b["kind"] not in ("대비표 그림", "첨부·참조만") or not b.get("stock_code") or b["stock_code"] in seen3:
            continue
        if "대비표 아님" in (b.get("reviewed") or "") or "사업목적 추가뿐" in (b.get("reviewed") or ""):
            continue                                       # 그림이 정관 대비표가 아니었거나(임원 규정 등) 조문이 글로 있던 공고
        seen3.add(b["stock_code"])
        rc = b["rcept_no"]
        add("no_table", b["stock_code"], "그림" if b["kind"] == "대비표 그림" or re.search(r"\.jpe?g", b.get("tail") or "") else "첨부 · 참조 문구",
            "판정 그대로", b.get("reviewed") or "확인 전", [link(f"소집공고 {rc[:8]}", DART + rc, "DART 주주총회소집공고")])

    # 4. 주총 없이 바뀐 정관 (s09m)
    for code, o in other.items():
        tid = "no_agm_change" if "주주총회 개정 없이" in o["label"] else None     # 상장 전 주총(소집공고 없음)은 특이사항 탭으로 (2026-11-22)
        if tid:
            add(tid, code, o.get("agm_date") or "", "판정 바뀜" if changed(by.get(code, {})) else "판정 그대로",
                o["evidence"] + " 주의: " + o["caution"], o.get("links") or [])

    # 5 · 6. 첨부 정관을 읽을 수 없음 · 정관 문구 오류 (s10 특이사항에서 옮김, 2026-11-22)
    for n in read_json(INTERIM / "s10_doc_notes.json"):
        r = by.get(n["stock_code"], {})
        tid = "unreadable" if any(w in n["kind"] for w in ("암호화", "서비스하지", "끊겨")) else "charter_error"
        sub = {"보안정책상 암호화된 PDF 가 그대로 첨부돼 읽을 수 없음": "암호화 PDF", "DART 가 첨부 정관 PDF 를 서비스하지 않음": "PDF 미제공",
               "첨부 정관 이미지가 중간에서 끊겨 배당 조가 없음": "이미지 끊김", "임시주총 조항 참조": "조항 참조 오류 (임시주총 항)",
               "정관의 오기재 (조항 참조 오류)": "조항 참조 오류", "정관의 오기재 (개정 전 문구 잔존)": "개정 전 문구 잔존"}.get(n["kind"], n["kind"])
        add(tid, n["stock_code"], sub, "판정 바뀜" if changed(r) else "판정 그대로", n["text"],
            [link(r.get("ev_label") or "근거", r.get("ev_url"))], name=n.get("corp_name"), market=n.get("market"))

    order = {t["id"]: i for i, t in enumerate(TYPES)}
    out.sort(key=lambda e: (order[e["type"]], e["market"] != "코스피", e["stock_code"], e["sub"]))
    for t in TYPES:
        ms = [e for e in out if e["type"] == t["id"]]
        t["n"] = len({(e["market"], e["stock_code"]) for e in ms})
        t["n_changed"] = len({(e["market"], e["stock_code"]) for e in ms if e["effect"] == "판정 바뀜"})
    write_json(OUT, {"types": TYPES, "cols": COLS, "rows": out})
    print(f"공시 유형 {len(TYPES)} · 행 {len(out)} → {OUT.relative_to(ROOT)}")
    for t in TYPES:
        print(f"  {t['name']}: {t['n']}사 (판정 바뀜 {t['n_changed']})")


if __name__ == "__main__":
    main()
