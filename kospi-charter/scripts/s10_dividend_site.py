"""s10 배당기준일 탭 데이터 → site/dividend.js  (window.DATA_DIV — app.js 가 data.js 와 함께 읽는다)

사용자 지시(2026-11-16): 웹페이지에 탭을 더한다.
  배당기준일 탭 — 상장 코스피 회사마다 ① 종목코드·회사명·결산월 ② 분류 결과 ③ 분류 근거 문구(조항 단위: 텍스트는 글, 스캔은
                  그 쪽의 해당 부분 그림, 주주총회소집공고면 그 공고의 '정관의 변경' 대비표) ④ 해당 문구 URL ⑤ 분류 근거의 종류
                  (사업보고서 / 주주총회소집공고 — 소집공고면 KIND 결과공시 URL 도) 와 근거 문서 URL
  특이사항 탭 — 확인필요였던 회사(대체 자료로 판별), 제출 뒤 안건으로 바뀐 회사, 결산일이 아닌 고정일 … 과 상장됐지만 대상 밖인 회사
  전체 취합 탭 — 태그 분포, 분기·중간배당 교차표 등 기술통계 (분기배당 미정비는 여기)

s08_site.py(옆 세션 담당, data.js)는 건드리지 않는다. 이 스크립트는 dividend.js 만 쓴다.

입력  data/final/charter_dividend_record_date.json (s09c) · data/interim/s09g_evidence.json · s09f_prev.json · s09e_agm_results.json
      data/final/kospi_charter.json (charter_viewer_url) · data/final/kospi_absent.json (상장됐지만 사업보고서가 없는 회사)
      .claude/skills/charter-dividend-record-date/references/regulation-history.md 는 링크만
출력  site/dividend.js

    python -X utf8 scripts/s10_dividend_site.py
"""
from __future__ import annotations

import calendar
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, INTERIM, ROOT, read_json  # noqa: E402
from s09a_dividend_excerpt import interim_of, paths  # noqa: E402

OUT = ROOT / "site" / "dividend.js"
TAGS = ["정관no", "정관yesorno", "정관yes", "확인필요"]
DART_MAIN = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")     # 원문 낱말 사이 제어문자(\x01 등) → 공백

# 웹페이지 글에는 em dash(—)를 쓰지 않는다 (사용자 지시 2026-11-16). 판단·메모 글만 고치고, 원문 인용(정관·공고·사업보고서 글)은 그대로 둔다.
# '…다 — …' 는 문장을 끊고(. ), 그 밖은 쉼표로 잇는다.
_DASH = re.compile(r"\s*—\s*")
ROW_TEXT = ("basis_article", "basis_note", "note", "attached_note", "amend_note", "reviewed_why", "agm_note", "ev_label", "fixed_point")


def nodash(s):
    if not isinstance(s, str) or "—" not in s:
        return s
    return _DASH.sub(lambda m: ". " if m.string[:m.start()].rstrip().endswith("다") else ", ", s).strip(" ,")


def ocr_word(s):
    """화면 글에서 '전사'(Opus 가 스캔을 읽어 옮긴 글)를 'OCR' 로 부른다 (사용자 지시 2026-11-16)."""
    if not isinstance(s, str) or "전사" not in s:
        return s
    return re.sub(r"(?:직접\s*)?전사본", "OCR 글", re.sub(r"Opus\s*전사", "Opus OCR", s))


# 첨부 정관을 읽을 수 없던 회사의 이유 (특이사항 탭 '분류') — 사용자 지시: '확인필요 → 대체 자료로 판별' 대신 직관적인 이유
UNREAD_ENC = "보안정책상 암호화된 PDF 가 그대로 첨부돼 읽을 수 없음"
UNREAD_NOSVC = "DART 가 첨부 정관 PDF 를 서비스하지 않음"
UNREAD_CUT = "첨부 정관 이미지가 중간에서 끊겨 배당 조가 없음"


def unread_cause(folder: str | None) -> tuple[str, str]:
    """코스닥: 정관 meta.json 의 pdfs[].error 로 이유를 고른다 (s04c·s04ck R7-5 — text/html = DART 안내 화면, 그 밖의 'PDF 아님' = DRM 암호화 파일)."""
    p = ROOT / folder / "meta.json" if folder else None
    errs = [str(x.get("error") or "") for x in ((read_json(p) if p and p.exists() else {}).get("pdfs") or [])]
    if any("text/html" in e for e in errs):
        return UNREAD_NOSVC, "DART 가 첨부 정관 PDF 대신 '이 파일은 서비스 하지 않습니다' 안내 화면을 돌려준다"
    if any("PDF 아님" in e for e in errs):
        return UNREAD_ENC, "첨부 정관이 보안정책으로 암호화된(DRM) 파일이라 내용을 읽을 수 없다"
    return "첨부 정관을 읽을 수 없음", "사업보고서 첨부 정관을 읽을 수 없다"


def pdf_meta(folder: str | None) -> dict:
    if not folder:
        return {}
    p = ROOT / folder / "meta.json"
    m = read_json(p) if p.exists() else {}
    return {x["file"]: x.get("src_url") for x in m.get("pdfs") or []}


def src_pages(folder: str | None) -> dict:
    """잘라 낸 정관(분할계획서 쪽 등)의 그림 파일 → 원문 쪽 번호 (meta images[].src_page)."""
    if not folder:
        return {}
    p = ROOT / folder / "meta.json"
    m = read_json(p) if p.exists() else {}
    return {x["file"]: x["src_page"] for x in m.get("images") or [] if x.get("src_page")}


def articles_out(arts: list[dict], folder: str | None) -> list[dict]:
    pm = pdf_meta(folder)
    sp = src_pages(folder)
    out = []
    for a in arts or []:
        out.append({
            "title": a.get("title"), "text": CTRL.sub(" ", a.get("text") or ""), "marks": a.get("marks") or [], "how": a.get("how"),
            "imgs": [{"page": i["page"], "crop": i.get("crop"), "src": i.get("src_url"), "file": i.get("file"),
                      "how": i.get("how"), "src_page": sp.get(i.get("file"))} for i in a.get("images") or []],
            "pdf": [{"file": p["pdf"], "page": p["page"], "scanned": p.get("scanned"), "src": pm.get(p["pdf"])}
                    for p in a.get("pdf_pages") or []],
        })
    return out


def notice_out(nv: dict | None, keep: str | None = None) -> list[dict]:
    out = []
    for t in (nv or {}).get("tables") or []:
        if keep and t["rcept_no"] != keep:
            continue
        out.append({"rcept_no": t["rcept_no"], "rcept_dt": t["rcept_dt"], "txt": t["txt"],
                    "rows": [{"h": r.get("header"), "l": r["line"]} for r in t["rows"]]})
    return out


def first_url(ev_arts: list[dict], viewer: str | None, charter_url: str | None) -> tuple[str | None, str]:
    """해당 문구 URL — 스캔이면 그 쪽 DART 원본 그림, PDF 면 DART PDF(#page), 텍스트면 정관 원문 viewer."""
    for a in ev_arts:
        for im in a["imgs"]:
            if im.get("src"):
                if im.get("src_page"):                       # 분할계획서에서 잘라 낸 신설회사 정관(안): 계획서 원문 쪽
                    return im["src"], f"분할계획서 {im['src_page']}쪽 그림 (DART)"
                return im["src"], f"정관 {im['page']}쪽 그림 (DART)"
        for p in a["pdf"]:
            if p.get("src"):
                return f"{p['src']}#page={p['page']}", f"정관 PDF {p['page']}쪽 (DART)"
    if viewer:
        return viewer, "정관 원문 (DART viewer)"
    return charter_url, "정관 첨부 (DART)"


def _opt(p: Path, default):
    return read_json(p) if p.exists() else default


# 결산배당 기준일 (웹페이지 배당기준일 탭 '결산' 칸, 사용자 지시 2026-11-16) — 태그와 정관의 고정 시점으로 적는다.
#   정관no → 이사회결정 · 정관yes → 날짜 · 정관yesorno → 날짜 또는 이사회결정
#   날짜: 고정 시점에 'N월 N일'이 있으면 그 날, 결산일이 아닌 고정일 4사는 그 날(FIXED_DAY), 그 밖(결산기말·참조형·빈 값)은 결산월 말일.
#   결산월은 사업보고서 기준, 제출 뒤 결산월을 바꾼 회사는 지금(KIND 상장법인목록, s02d) 결산월. 결산기가 여럿인 리츠는 그 달들의 말일.
FIXED_DAY = {"042700": "3월 7일", "071970": "1월 31일", "011810": "1월 31일", "005870": "1월 1일"}
_MD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
SETTLE_NOW = INTERIM / "s02d_settle_month.json"


def month_end(m: int) -> str:
    return "2월 말일" if m == 2 else f"{m}월 {calendar.monthrange(2025, m)[1]}일"


def settle_of(code: str, sec_group: str | None, sm, now: dict) -> dict:
    """사업보고서 결산월(sm)과 지금 결산월(KIND) — 다르면 결산월 변경, 단 리츠가 3·6개월 간격이면 결산기가 여럿인 것."""
    cur = now.get(code)
    sm = int(sm) if sm else None
    multi = bool(cur and sm and cur != sm and sec_group == "부동산투자회사" and (cur - sm) % 3 == 0)
    months = None
    if multi:
        step = 6 if (cur - sm) % 6 == 0 else 3
        months = sorted({(sm - 1 + step * i) % 12 + 1 for i in range(12 // step)})
    return {"settle_month_now": cur, "settle_changed": bool(cur and sm and cur != sm and not multi), "settle_months": months}


def record_date(code: str, tag: str | None, fixed_point: str | None, month: int | None, months: list | None) -> str | None:
    if tag == "정관no":
        return "이사회결정"
    if tag not in ("정관yes", "정관yesorno"):
        return tag
    m = _MD.search(fixed_point or "")
    day = (FIXED_DAY.get(code) or (f"{int(m.group(1))}월 {int(m.group(2))}일" if m else None)
           or (" · ".join(month_end(x) for x in months) if months else month_end(month) if month else "결산기말"))
    return day if tag == "정관yes" else f"{day} 또는 이사회결정"


# 상장공시시스템 배당기준일 신고 대조 (사용자 지시 2026-11-17, s02e): 화면 표기 정관 태그 → 신고 값
#   일치  = 태그가 같고, Y 면 신고 배당기준일이 '결산' 날짜(final_record) 중 하나와 같다('말일'은 그 달 마지막 날).
#           결산기가 여럿인지 모르는 리츠(settle_months 없음)는 결산기말 고정이면 결산월과 3개월 간격 달의 말일도 같은 것으로 본다.
#   불일치 = 태그가 다르거나(정관 YorN 은 상장공시시스템에 YorN 이 없어 Y·N 어느 쪽이든 불일치) Y 인데 날짜가 다르다.
#   미입력 = 신고가 없다. 코스피 밖(엑셀에 없음)은 빈 값.
TAG_YN = {"정관no": "N", "정관yes": "Y", "정관yesorno": "YorN"}
FILED_SRC = INTERIM / "s02e_check_group.json"
_RD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2}\s*일|말일)")


def filed_cmp(x: dict, f: dict | None) -> dict:
    if not f:
        return {"filed": None, "filed_date": None, "filed_cmp": None, "filed_why": None}
    t, v, d = TAG_YN.get(x["tag_current"]), f["filed"], f.get("filed_date") or ""
    out = {"filed": v, "filed_date": d or None}
    if v == "미입력":
        return {**out, "filed_cmp": "미입력", "filed_why": "상장공시시스템에 배당기준일 신고가 없다"}
    if t != v:
        why = f"정관 {t or x['tag_current']} · 신고 {v}"
        if t == "YorN":
            why += " (상장공시시스템에 YorN 이 없어 Y·N 중 하나로 신고)"
        return {**out, "filed_cmp": "불일치", "filed_why": why}
    if v != "Y" or not d:
        return {**out, "filed_cmp": "일치", "filed_why": None}
    y, m, dd = (int(s) for s in d.split("-"))
    last = calendar.monthrange(y, m)[1]
    fixed = [(int(a), "말일" if b == "말일" else int(b.replace("일", "").strip())) for a, b in _RD.findall(x.get("final_record") or "")]
    ends = [(a, b) for a, b in fixed if b == "말일" or b == calendar.monthrange(2025, a)[1] or (a == 2 and b in (28, 29))]
    if any(a == m and (b == dd or (b == "말일" and dd == last)) for a, b in fixed):
        return {**out, "filed_cmp": "일치", "filed_why": None}
    if not fixed:
        return {**out, "filed_cmp": "일치", "filed_why": f"정관 날짜를 못 읽어 기준일은 대조하지 않음 ({x.get('final_record') or ''})"}
    if (x.get("sec_group") == "부동산투자회사" and not x.get("settle_months") and ends and len(ends) == len(fixed) and dd == last
            and any((m - a) % 3 == 0 for a, _ in ends)):
        return {**out, "filed_cmp": "일치", "filed_why": f"리츠: 결산기가 여럿인 것으로 봄 (신고 {d} · 정관 {x['final_record']})"}
    return {**out, "filed_cmp": "불일치", "filed_why": f"신고 기준일 {d} · 정관 {x['final_record']}"}


SRC_KINDS = ("증권신고서", "분할계획서", "기타신고사항", "홈페이지")     # 사업보고서가 없어 정관을 찾은 문서 (absent_charter)
CHARTER_OF = {"": "kospi_charter.json", "kosdaq": "kosdaq_charter.json", "absent": "absent_charter.json"}
ABSENT_OF = {"": "kospi_absent.json", "kosdaq": "kosdaq_absent.json"}


def market_rows(sfx: str, market: str | None) -> dict:
    """한 묶음의 결과표(s09c) + 근거(s09g) + 대체 자료(s09f) + KIND 결과(s09e) → 웹페이지 행.
    market 이 None 이면(absent — 사업보고서 없는 회사) 행마다 그 회사의 시장을 쓴다."""
    rows = read_json(paths(sfx)["out_json"])
    ev = _opt(interim_of(sfx, "s09g_evidence.json"), {})
    prev = _opt(interim_of(sfx, "s09f_prev.json"), {})
    agm = _opt(interim_of(sfx, "s09e_agm_results.json"), {})
    kc = {r["stock_code"]: r for r in read_json(FINAL / CHARTER_OF[sfx])}
    absent = _opt(FINAL / ABSENT_OF[sfx], []) if sfx in ABSENT_OF else []
    tg = {t["stock_code"]: t for t in _opt(paths(sfx)["targets"], [])}
    # s09i — 사업보고서보다 먼저 접수된 소집공고(그해 정기주총) 안건 판별
    pre = {}
    pf = interim_of(sfx, "s09i_pre_agm.jsonl")
    if pf.exists():
        for line in pf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                j = json.loads(line)
                if j.get("output"):
                    pre[j["stock_code"]] = j
    review = _opt(paths(sfx)["review"], {})
    now = (_opt(SETTLE_NOW, {}) or {}).get("settle_month") or {}

    out_rows = []
    for r in rows:
        code = r["stock_code"]
        k = kc.get(code, {})
        e = ev.get(code, {})
        basis = r["basis_kind"]
        pv = prev.get(code) or {}
        # 근거 글 — 지금 태그를 정한 자료
        if basis in ("전년도 사업보고서",) or (pv and basis == "주총소집공고" and pv.get("charter_fulltext_txt")):
            arts = articles_out((e.get("prev") or {}).get("articles"), pv.get("charter_folder"))
            viewer = None
            charter_url = pv.get("charter_url")
        else:
            arts = articles_out((e.get("charter") or {}).get("articles"),
                                Path(r["charter_fulltext_txt"]).parent.as_posix() if r["charter_fulltext_txt"] else None)
            viewer, charter_url = k.get("charter_viewer_url"), r["charter_url"]
        notices = []
        if r["basis_notice_rcept_no"]:
            src = (e.get("prev") or {}).get("notice") if pv else e.get("notice")
            notices = notice_out(src, r["basis_notice_rcept_no"])
        report = ((e.get("prev") or {}).get("report_section") or {}).get("text") if pv else None
        if r["basis_notice_rcept_no"]:
            ev_url, ev_label = r["basis_notice_url"], "정관의 변경 안건 (DART 소집공고)"
        elif not arts and report:
            ev_url, ev_label = r["basis_doc_url"], "사업보고서 본문 (DART)"
        else:
            ev_url, ev_label = first_url(arts, viewer, charter_url)
        res = agm.get(r["basis_notice_rcept_no"] or "", {})
        # 지금 태그를 정한 자료의 판단 — 소집공고·대체 자료가 근거면 그쪽 판단과 중간·분기배당을 쓴다
        note, article, interim, quarterly = r["note"], r["basis_article"], r["interim"], r["quarterly"]
        if pv and pv.get("output"):
            po = pv["output"]
            note, article, interim, quarterly = po.get("note"), po.get("basis_article"), po.get("interim"), po.get("quarterly")
            for n in pv.get("notices") or []:
                no = n.get("output") or {}
                if n["rcept_no"] == r["basis_notice_rcept_no"] and no:
                    note = no.get("note") or note
                    interim, quarterly = no.get("interim_after") or interim, no.get("quarterly_after") or quarterly
        elif r["basis_notice_rcept_no"] and r["basis_notice_rcept_no"] in ((pre.get(code) or {}).get("rcept_nos") or []):
            po2 = pre[code]["output"]
            note = po2.get("note") or note
            interim, quarterly = po2.get("interim_after") or interim, po2.get("quarterly_after") or quarterly
        elif r["basis_notice_rcept_no"]:
            note = r["agm_note"] or note
            interim, quarterly = r["agm_interim_after"] or interim, r["agm_quarterly_after"] or quarterly
        if r["basis_notice_rcept_no"] and notices and notices[0]["rows"]:
            cells = notices[0]["rows"][0]["l"].split(" | ")
            heads = [m.group(1) for c in ([cells[0]] if len(cells) >= 4 else cells[:2])
                     for m in [re.match(r"\s*((?:제\s*\d+\s*조|第\s*\d+\s*條)(?:\s*의\s*\d+)?\s*[(（【\[]?[^)）】\]\n|/]{0,25}[)）】\]]?)", c)] if m]
            if heads:
                article = f"{re.sub(r'\s+', ' ', heads[0]).strip()} (정관의 변경 안건)"
        st = settle_of(code, r["sec_group"], r["settle_month"], now)
        fp = (pv["output"].get("fixed_point") if pv and pv.get("output") else r["fixed_point"] if r["tag_current"] == r["tag"] else None)
        base_m = st["settle_month_now"] if st["settle_changed"] else (int(r["settle_month"]) if r["settle_month"] else None)
        when = (None if not r["basis_notice_rcept_no"] else
                "pre" if r["basis_notice_rcept_no"] in ((pre.get(code) or {}).get("rcept_nos") or []) else "post")
        out_rows.append({
            "market": market or r.get("market"),
            "stock_code": code, "corp_name": r["corp_name"], "settle_month": r["settle_month"], "sec_group": r["sec_group"],
            "tag_current": r["tag_current"], "tag": r["tag"], "changed": r["tag"] != r["tag_current"],
            "basis_kind": basis, "basis_rcept_no": r["basis_rcept_no"], "basis_doc_url": r["basis_doc_url"],
            "basis_charter_url": r["basis_charter_url"], "basis_prev_report_nm": r["basis_prev_report_nm"],
            "basis_notice_rcept_no": r["basis_notice_rcept_no"], "basis_notice_url": r["basis_notice_url"],
            "basis_result_acptno": r["basis_result_acptno"], "basis_result_url": r["basis_result_url"],
            "basis_result_title": r["basis_result_title"], "basis_agm_date": r["basis_agm_date"],
            "basis_result_rows": [[x["no"], x["item"], x["result"]] for x in res.get("charter_rows") or []],
            "basis_note": r["basis_note"],
            "basis_unconfirmed": bool(r.get("basis_unconfirmed")),   # 소집공고 안건대로 바뀐 것으로 보되 KIND 결과로 가결은 확인 못함 (s09c)
            "basis_notice_when": when,       # pre = 사업보고서보다 먼저 접수된 소집공고(그해 정기주총) · post = 제출 뒤
            "ev_url": ev_url, "ev_label": ev_label,
            "basis_article": article, "quotes": r["quotes"] if not (pv and pv.get("output")) else (pv["output"].get("quotes") or []),
            "route": r["route"], "fixed_point": fp,
            "final_record": record_date(code, r["tag_current"], fp, base_m, st["settle_months"]), **st,
            "interim": interim, "quarterly": quarterly,
            "confidence": r["confidence"], "note": note, "attached_note": r["note"] if note != r["note"] else None,
            "amend_note": r["amend_note"],
            "charter_content_type": r["charter_content_type"], "charter_att_date": r["charter_att_date"],
            "rcept_no": r["rcept_no"],
            "report_url": r["basis_doc_url"] if basis in SRC_KINDS or (tg.get(code) or {}).get("charter_source_doc") else DART_MAIN.format(r["rcept_no"]),
            "reviewed_why": r["reviewed_why"], "llm_tag": r["llm_tag"], "rule_tag": r["rule_tag"],
            "agm_tag_after": r["agm_tag_after"], "agm_note": r["agm_note"],
            "prev_tag": (pv.get("output") or {}).get("tag") if pv else None,
            "ev": {"arts": arts, "notices": notices, "report": report},
        })

    for x in out_rows:
        for c in ROW_TEXT:
            x[c] = nodash(x[c])
    return {"market": market, "sfx": sfx, "rows": rows, "out": out_rows, "absent": absent, "review": review, "agm": agm, "prev": prev,
            "kc": kc, "tg": tg, "skip": set(), "pre": pre}


def agm_changed_note(add, x: dict) -> None:
    """소집공고 안건으로 지금 태그가 바뀐 회사 — 사업보고서보다 먼저 접수된 공고(그해 정기주총)인지 제출 뒤인지 나눈다."""
    res = f"KIND {x['basis_result_title']}({x['basis_agm_date'] or '날짜 없음'})에서 가결됐다 → {x['tag_current']}."
    if x.get("basis_notice_when") == "pre":
        add("정기주총에서 바뀜 (사업보고서보다 먼저 접수된 소집공고)", x["stock_code"],
            f"사업보고서 첨부 정관은 주총 전 판이라 {x['tag']}. 사업보고서보다 먼저 접수된 소집공고 {x['basis_notice_rcept_no']} 의 '정관의 변경' 안건이 "
            f"결산배당 기준일을 바꿨고 {res}", 2)
    else:
        add("사업보고서 제출 뒤 주총에서 바뀜", x["stock_code"],
            f"사업보고서 첨부 정관은 {x['tag']}. 그 뒤 소집공고 {x['basis_notice_rcept_no']} 의 '정관의 변경' 안건이 결산배당 기준일을 바꿨고 {res}", 2)


def unconfirmed_notes(M: dict, add) -> None:
    """결산배당 기준일을 바꾸는 안건(s09d · s09i)인데 KIND 주주총회결과로 가결을 확인하지 못한 공고 — 지금 태그는 바꾸지 않았다."""
    by = {x["stock_code"]: x for x in M["out"]}
    for rc, a in sorted(M["agm"].items()):
        if a.get("passed") is True:
            continue
        pj = M["pre"].get(a["stock_code"]) or {}
        changes = (a.get("from") == "s09d" or
                   (a.get("from") == "s09i" and (pj.get("output") or {}).get("changes_record_date") and rc in (pj.get("rcept_nos") or [])))
        if not changes:
            continue
        when = "사업보고서보다 먼저 접수된" if a.get("from") == "s09i" else "사업보고서 제출 뒤"
        why = (f"KIND {a.get('result_title') or ''}: {a.get('note') or ''}" if a.get("result_acptno")
               else "공고 뒤 80일 안에 KIND 주주총회결과 공시가 없다")
        add("주총 안건 가결 확인 못 함", a["stock_code"], f"{when} 소집공고 {rc} 의 '정관의 변경' 안건이 결산배당 기준일을 바꾸지만 {why}. "
            f"그래서 지금 태그는 첨부 정관 기준({(by.get(a['stock_code']) or {}).get('tag_current')})으로 둔다.", 3)


def absent_notes(M: dict, add) -> None:
    """사업보고서가 없는 상장회사(absent_charter) — 빠진 이유와 정관을 찾은 문서."""
    for x in M["out"]:
        t = M["tg"].get(x["stock_code"]) or {}
        doc = t.get("charter_source_doc") or x["basis_kind"]
        src = " ".join(v for v in (t.get("charter_source_nm"), t.get("charter_source_dt")) if v)
        add(f"사업보고서 없음 → {doc} 정관", x["stock_code"], f"{t.get('reason') or '사업보고서 없음'}. 정관은 {doc}{f'({src})' if src else ''}에서 찾았다 → {x['tag_current']}.", 1)
        if x.get("basis_notice_rcept_no"):
            agm_changed_note(add, x)


def kosdaq_notes(M: dict, add) -> None:
    """코스닥 특이사항 — 고정 목록 대신 검토 기록(s09h)·대체 자료(s09f)·KIND 결과(s09e)에서 뽑는다."""
    out_rows, review, agm, prev = M["out"], M["review"], M["agm"], M["prev"]
    by = {x["stock_code"]: x for x in out_rows}
    for code, rec in sorted(prev.items()):                      # 1 정관 원문 없음 → 대체 자료
        x, o = by.get(code) or {}, rec.get("output") or {}
        src = (f"전년도 사업보고서({rec['prev_report_nm']}) 첨부 정관" if rec.get("charter_fulltext_txt")
               else "사업보고서 본문 '배당관련 예측가능성' 표(정관상 배당기준일을 배당액 결정 이후로 정할 수 있는지 여부)")
        kind, why = unread_cause((M["kc"].get(code) or {}).get("charter_dir"))
        add(kind, code, f"{why}. 그래서 {src}로 판별했다 → {o.get('tag')}. {o.get('note') or ''}".strip(), 1)
    for x in out_rows:                                          # 2 제출 뒤 주총에서 바뀜
        if x["basis_kind"] == "주총소집공고" and x["stock_code"] not in prev:
            agm_changed_note(add, x)
    unconfirmed_notes(M, add)                                   # 3 안건은 있는데 가결을 확인하지 못함
    for x in out_rows:                                          # 4 결산일이 아닌 고정일
        m = re.search(r"(\d{1,2})\s*월", x.get("fixed_point") or "")
        if x["tag_current"] == "정관yes" and m and x["settle_month"] and int(m.group(1)) != int(x["settle_month"]):
            add("결산일이 아닌 고정일", x["stock_code"], f"정관이 결산배당 기준일을 '{x['fixed_point']}'로 박아 두었다(결산월 {x['settle_month']}월). "
                "날짜를 정관이 고정했으므로 정관yes.", 4)
    kind_txt = {"소멸시효조 잔존문구": "서식 판정: 스팩 소멸시효 조 잔존 문구", "기준일조 354단서": "서식 판정: 기준일 조의 상법 제354조식 단서",
                "택일형": "서식 판정: 택일형", "임시주총 조항 참조": "임시주총 조항 참조", "기준일조 기본값": "기준일 조의 기본값",
                "부칙·본문 불일치": "부칙·본문 불일치"}
    for code, v in sorted(review.items()):                      # 5 서식 판정으로 태그를 바꾼 회사 · 개별 판정
        if v.get("kind") in kind_txt and (v["tag"] != v.get("llm_tag") or v["kind"] in ("부칙·본문 불일치",)):
            add(kind_txt[v["kind"]], code, f"{v['why']} (서브에이전트 {v.get('llm_tag')} → {v['tag']})" if v["tag"] != v.get("llm_tag")
                else v["why"], 5)
    mode = {r["stock_code"]: r.get("llm_mode") for r in M["rows"]}
    for x in out_rows:                                          # 6 정관 서식이 남다른 곳
        n = x.get("note") or ""
        x = dict(x, llm_mode=mode.get(x["stock_code"]))
        if x["stock_code"] in prev:
            continue
        if x["stock_code"] == "950250":
            add("영문 정관 전문으로 판별", x["stock_code"], f"발췌 키워드(한글)가 걸리지 않는 영국 PLC 영문 정관이라 전문으로 판별 → {x['tag']}. {n}", 6)
        elif x.get("llm_mode") == "full":
            add("정관에 결산배당 조가 없음", x["stock_code"], f"발췌에 이익배당 조가 없어 정관 전문으로 다시 봤으나 이익배당(지급 대상) 조가 없고 이익금 처분 조만 있다. "
                f"그래서 기준일 조(정기주총 권리행사 주주)로 판별 → {x['tag']}. {n}", 6)


def notes_of(M: dict) -> list[dict]:
    out_rows, absent, market = M["out"], M["absent"], M["market"]
    by = {x["stock_code"]: x for x in out_rows}
    notes = []

    def add(kind, code, text, order):
        x = by.get(code, {})
        notes.append({"market": market or x.get("market"), "kind": kind, "order": order, "stock_code": code, "corp_name": x.get("corp_name"),
                      "tag": x.get("tag"), "tag_current": x.get("tag_current"), "basis_kind": x.get("basis_kind"),
                      "text": text})

    if M["sfx"] == "absent":
        absent_notes(M, add)
        return notes
    if M["sfx"] == "kosdaq":
        kosdaq_notes(M, add)
        for a in absent:
            if a.get("stock_code") in M["skip"]:          # 증권신고서 등에서 정관을 찾은 회사는 '사업보고서 없음 → …' 로
                continue
            notes.append({"market": market, "kind": "상장됐지만 대상 밖", "order": 10, "stock_code": a.get("stock_code"),
                          "corp_name": a.get("corp_name"), "tag": None, "tag_current": None, "basis_kind": None,
                          "text": f"KIND {market} 상장회사지만 조회기간에 사업보고서가 없어 정관을 받지 않았다. {a.get('reason') or a.get('reason_code')}"})
        return notes

    cause = {"456040": "사업보고서마다 첨부 정관 PDF 가 Azure Information Protection 으로 잠겨 본문이 없다(2023·2024·2025 결산 모두). "
                       "그래서 2024.03 정기주총 소집공고의 '정관의 변경' 대비표(제59조 ③ 변경 후 문구)와 2026.03 사업보고서 본문 "
                       "'배당관련 예측가능성' 표(결산배당 기준일을 배당액 결정 이후로 정할 수 있는지 O)로 판별했고, KIND 주주총회결과로 가결을 확인했다.",
             "272550": "2026.03 사업보고서 첨부 정관 PDF 가 Azure Information Protection 으로 잠겨 본문이 없다. 전년도 사업보고서(2024.12) 첨부 정관"
                       "(제57조 ② '매결산기 말일 현재' → 정관yes)을 받고, 그 뒤 2026.02.20 소집공고의 '정관의 변경' 안건(이사회 기준일)과 "
                       "KIND 주주총회결과(2026.03.23 가결)로 지금 태그를 정했다.",
             "475150": "2026.03 사업보고서 첨부 정관(DART 이미지 12장)이 제36조(감사의 직무)에서 끝나 이익배당 조가 없다. 전년도 사업보고서(2024.12) "
                       "첨부 정관(이미지 19장, Opus OCR)의 제44조 ③(이사회 기준일)로 판별했다. 그 뒤 2026.03.09 소집공고 '정관의 변경'은 배당 조항을 건드리지 않는다."}
    cause_kind = {"456040": UNREAD_ENC, "272550": UNREAD_ENC, "475150": UNREAD_CUT}   # OCI·삼양패키징 = Azure Information Protection 보호 PDF
    for code, txt in cause.items():
        add(cause_kind[code], code, txt, 1)
    for x in out_rows:
        if x["basis_kind"] == "주총소집공고" and x["stock_code"] not in cause:
            agm_changed_note(add, x)
    add("첨부 정관이 이미 안건 반영본", "000890", "사업보고서(2026.03.18)에 붙은 정관에 '2026.03.26 개정' 표시가 있다 — 3월 26일 주총 안건대로 고친 판을 미리 첨부했다. "
        "KIND 주주총회결과로 가결 확인. 태그(정관no)는 같다.", 3)
    fixed = {"042700": "3월 7일 24시 현재", "071970": "매년 1월 31일 (제16조 ① 참조)", "011810": "매년 1월 31일 (제15조 ① 참조)",
             "005870": "매년 1월 1일 (제12조 ② 참조)"}
    for code, d in fixed.items():
        add("결산일이 아닌 고정일", code, f"정관이 결산배당 기준일을 '{d}'로 박아 두었다 — 날짜를 정관이 고정했으므로 정관yes. 2023.2.8 표준정관 주석이 "
            "허용한 '특정일' 방식이다(결산일 12월 31일 아님).", 4)
    rev = {"012330": "제46조 ⑥이 두 개 — 이사회 기준일 문구 '개정(23.3.22)'과 참조 고정 문구 '신설(22.3.23)'. 같은 항을 2023년에 개정했으므로 옛 문구가 "
                     "지워지지 않고 남은 것으로 보고 정관no (LLM 은 정관yesorno).",
           "403550": "제49조 ③이 '제13조 제2항'(임시주총 등 이사회 결정일)을 가리키지만 제17조 ②도 정기주총 기준일을 같은 번호로 적는다 — 항 번호 오기로 보고 "
                     "결산기 최종일 고정, 정관yes (LLM 은 정관no).",
           "010820": "제43조 ③이 가리키는 제13조 ①은 삭제되고 ②가 매년 12월 31일 — 참조 오기로 보고 정관yes (LLM 은 확인필요)."}
    rev_kind = {"012330": "정관의 오기재 (개정 전 문구 잔존)", "403550": "정관의 오기재 (조항 참조 오류)", "010820": "정관의 오기재 (조항 참조 오류)"}
    for code, d in rev.items():                      # 사람 검토로 LLM 과 다르게 정한 회사 — 사용자 지시: 정관 문구의 잘못을 분류 이름으로
        add(rev_kind[code], code, d, 5)
    # GS피앤엘(499790)·CJ씨푸드(011150)의 '조문 간 충돌 가능 (혼합형)'은 뺐다 (사용자 지시 2026-11-17): 처음부터 정관yesorno 이고,
    # 결산기말 고정 항과 이사회 기준일 항이 따로 있는 yesorno 정관은 그 밖에도 많아(209사 중 약 141사) 두 회사만 특이사항으로 둘 근거가 약하다.
    add("금전·주식배당 분리", "030610", "금전배당은 이사회가 기준일을 정하고, 주식배당만 '매 결산기말 현재'로 둔다 — 금전배당 기준으로 정관no. 주식배당은 신주가 주총 종결 때 "
        "생기므로 기준일이 주총 전이어야 해 분리형이 정당하다(2023.1.31 개선방안 Q&A).", 7)
    add("배당 조항 없이 주주명부 조가 겸함", "015760", "이익배당 조에 지급 대상이 없고, 제15조(주주명부의 폐쇄) ②가 '매년 12월 31일 … 의결권을 행사하고 배당을 수령할 "
        "권리를 가진 주주로 본다'고 정한다 → 정관yes.", 8)
    for code in ("003000", "011090"):
        add("의결권 기준일과 같은 날", code, "배당 조가 기준일 조를 참조하고, 그 조가 정기주총 의결권 기준일 자체를 '이사회 결의로 정한 날'로 둔다 — 정관에 날짜가 없어 "
            "정관no 지만, 배당기준일이 의결권 기준일과 같은 날이라 주총 뒤로 잡기는 어렵다.", 9)
    unconfirmed_notes(M, add)
    for a in absent:
        if a.get("stock_code") in M["skip"]:
            continue
        notes.append({"market": market, "kind": "상장됐지만 대상 밖", "order": 10, "stock_code": a.get("stock_code"), "corp_name": a.get("corp_name"),
                      "tag": None, "tag_current": None, "basis_kind": None,
                      "text": f"KIND 코스피 상장회사지만 조회기간에 사업보고서가 없어 정관을 받지 않았다. {a.get('reason') or a.get('reason_code')}"})

    return notes


def stats_of(out_rows: list[dict], rows: list[dict], klca: bool) -> dict:
    def ct(key_a, key_b, src=out_rows):
        c = Counter((x[key_a], x[key_b]) for x in src)
        return [[a, b, n] for (a, b), n in sorted(c.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))]

    amend_year = Counter()
    for r in rows:
        if r["tag"] == "정관no":
            amend_year[str(r["amend_year"]) if r["amend_year"] else "표시 없음"] += 1
    stats = {
        "n": len(out_rows),
        "tag_current": Counter(x["tag_current"] for x in out_rows),
        "tag_attached": Counter(x["tag"] for x in out_rows),
        "basis_kind": Counter(x["basis_kind"] for x in out_rows),
        "changed": sum(x["changed"] for x in out_rows),
        "x_quarterly": ct("tag_current", "quarterly"),
        "x_interim": ct("tag_current", "interim"),
        "x_sec_group": ct("tag_current", "sec_group"),
        "x_settle": [[t, "12월" if m == 12 else "12월 아님", n] for (t, m), n in
                     Counter((x["tag_current"], 12 if x["settle_month"] == 12 else 0) for x in out_rows).items()],
        "x_route": ct("tag", "route", [dict(x, tag=r["tag"]) for x, r in zip(out_rows, rows)]),
        "x_ctype": ct("tag_current", "charter_content_type"),
        "x_filed": ct("tag_current", "filed", [x for x in out_rows if x.get("filed")]),       # 정관 × 상장공시시스템 신고 (코스피)
        "filed_cmp": Counter(x["filed_cmp"] for x in out_rows if x.get("filed_cmp")),
        "amend_year_no": sorted(amend_year.items()),
        "no_but_q_fixed": [x["stock_code"] for x in out_rows if x["tag_current"] == "정관no" and x["quarterly"] == "고정"],
        "no_but_i_fixed": [x["stock_code"] for x in out_rows if x["tag_current"] == "정관no" and x["interim"] == "고정"],
        "markets": Counter(x["market"] for x in out_rows),
        "klca": [] if not klca else [  # 상장협·코스닥협 집계 (regulation-history) — 모집단이 다르다
            ["2023.3.29", "12월 결산 2,267사(유가 780)", "646사 28.5%", "유가 186 (23.8%)"],
            ["2025.4.7", "'24.12.31 · 2,450사(유가 805)", "1,137사 46.4%", "유가 422 (52.4%)"],
            ["2026.4.14", "'25.12.31 · 2,478사(유가 795)", "1,371사 55.3%", "유가 501 (63.0%)"],
        ],
    }
    return stats


def main():
    Ms = [market_rows("", "코스피"), market_rows("kosdaq", "코스닥")]
    if paths("absent")["out_json"].exists():         # 사업보고서 없는 상장회사(absent_charter) — 판별 결과가 있을 때만
        Ma = market_rows("absent", None)
        Ms.append(Ma)
        for M in Ms[:2]:
            M["skip"] = {x["stock_code"] for x in Ma["out"]}
    out_rows = [x for M in Ms for x in M["out"]]
    rows = [r for M in Ms for r in M["rows"]]
    notes = [n for M in Ms for n in notes_of(M)]
    for n in notes:                                   # em dash 빼기 · '전사' 대신 'OCR' (사용자 지시 2026-11-16)
        n["kind"], n["text"] = nodash(n["kind"]), ocr_word(nodash(n["text"]))
    for x in out_rows:
        for c in ("note", "attached_note", "reviewed_why", "agm_note"):
            x[c] = ocr_word(x[c])
    fm = (_opt(FILED_SRC, {}) or {}).get("filed") or {}          # 상장공시시스템 신고 (s02e, 코스피만)
    for x in out_rows:
        x.update(filed_cmp(x, fm.get(x["stock_code"]) if x["market"] == "코스피" else None))
    stats = stats_of(out_rows, rows, klca=True)
    # 시장별 — 묶음이 아니라 행의 시장으로 (absent 묶음은 두 시장에 걸친다)
    mk_names = [m for m in ("코스피", "코스닥") if any(x["market"] == m for x in out_rows)]
    by_market = {"전체": stats, **{m: stats_of([x for x in out_rows if x["market"] == m],
                                             [r for x, r in zip(out_rows, rows) if x["market"] == m], klca=m == "코스피")
                                   for m in mk_names}}

    cols = list(out_rows[0].keys())
    ncols = list(notes[0].keys())
    data = {
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tables": {
            "dividend": {"cols": cols, "rows": [[x[c] for c in cols] for x in out_rows],
                         "file": "charter_dividend_record_date.json", "updated": datetime.now().strftime("%Y-%m-%d %H:%M")},
            "dividend_notes": {"cols": ncols, "rows": [[x[c] for c in ncols] for x in sorted(notes, key=lambda n: (n["market"] != "코스피", n["order"], n["stock_code"] or ""))],
                               "file": "s10 특이사항", "updated": datetime.now().strftime("%Y-%m-%d %H:%M")},
        },
        "stats": stats, "stats_by_market": by_market,
        "links": {"doc": "docs/04-배당기준일태깅.md", "history": ".claude/skills/charter-dividend-record-date/references/regulation-history.md",
                  "guide": ".claude/skills/charter-dividend-record-date/references/tagging-guide.md",
                  "csv": "data/final/charter_dividend_record_date.csv", "csv_kosdaq": "data/final/charter_dividend_record_date_kosdaq.csv",
                  "csv_absent": "data/final/charter_dividend_record_date_absent.csv"},
    }
    js = "window.DATA_DIV = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    from _common import stamp_site_assets
    stamp_site_assets()                 # index.html 의 파일 주소에 ?v=내용해시 (캐시 때문에 옛 파일이 보이지 않게)
    print(f"→ {OUT.relative_to(ROOT)} {len(js) / 1e6:.1f}MB · 행 {len(out_rows)} {dict(stats['markets'])} · 특이사항 {len(notes)} · "
          f"근거 그림 {sum(len(a['imgs']) for x in out_rows for a in x['ev']['arts'])}")


if __name__ == "__main__":
    main()
