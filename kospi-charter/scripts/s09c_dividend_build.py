"""s09c 배당기준일 태그 검증·결과표 — s09b 결과 + 독립 규칙 판별 + 인용 대조 + 제출 뒤 정관변경 표시

검증
  1. 인용 대조 (quote_ok): LLM 이 낸 quotes 가 보낸 글(발췌 또는 전문)에 그대로 있는가. 공백을 모두 지우고 비교한다
     (스캔 전사문의 띄어쓰기 차이 때문). 하나라도 없으면 review.
  2. 규칙 판별 (rule_tag): LLM 과 따로, 정규식으로 결산배당 조의 '이사회가 기준일을 정함'(B)과 '결산기말 현재 고정'(F)을 찾는다.
     중간배당·분기배당 조(조 머리 제목에 중간·분기배당만 있는 조)는 뺀다. B·F → 정관yesorno, B → 정관no, F → 정관yes,
     둘 다 없으면 '?'. LLM 태그와 다르면 review (규칙이 틀리는 줄 아는 경우도 사람이 본다).
  3. 제출 뒤 정관변경 (later_amend_dividend): 사업보고서 원본 제출 뒤 소집공고의 '정관의 변경' 절(s06 의 정관의변경.txt)에
     배당·기준일 낱말이 있으면 표시. 태그는 사업보고서 첨부 정관 기준이라, 그 뒤 주총에서 바뀌었을 수 있다는 뜻이다.
  4. review: 확인필요 · 확신도 낮음 · 인용 불일치 · 규칙 불일치 · LLM 실패. 사람이 본 결과는 data/interim/s09_review.json 에
     {stock_code: {tag, by, at, why}} 로 적으면 최종 태그(tag)가 그것으로 바뀌고 llm_tag 는 그대로 남는다.

입력  data/interim/s09_targets.json · s09a_excerpts.jsonl · s09b_results.jsonl · (있으면) s09_review.json
출력  data/final/charter_dividend_record_date.json · .csv   회사 1행
      data/interim/s09c_summary.json                          건수·검증 집계
      (--sfx kosdaq 이면 모든 이름 끝에 _kosdaq — 경로는 s09a.paths)

사용법
  python -X utf8 scripts/s09c_dividend_build.py              # 결과표·요약
  python -X utf8 scripts/s09c_dividend_build.py --queue      # 사람이 볼 목록(review=True)을 화면에
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, now_iso, read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402
from s09b_dividend_tag_llm import TAGS as L_TAGS, read_results  # noqa: E402

# ── 규칙 판별 ───────────────────────────────────────────────────────────────
# B: 결산배당 기준일을 이사회가 정한다
B = re.compile("|".join([
    # "배당을 받을 주주(또는 등록질권자)를 확정하기 위한 기준일"
    X.배당 + r"\s*(?:을|를)?\s*받\s*을\s*주\s*주[^\n]{0,15}?를\s*확\s*정\s*하\s*기\s*위\s*한\s*" + X.기준일,
    X.배당 + r"\s*(?:을|를)?\s*받\s*기\s*위한\s*" + X.기준일 + r"\s*(?:은|는)\s*" + X.이사회,
    X.기준일 + r"\s*(?:은|는)\s*" + X.이사회 + r"\s*(?:의\s*)?결\s*의",
    X.이사회 + r"[^\n。]{0,30}?정\s*(?:한|하는)\s*(?:" + X.배당 + r"\s*)?" + X.기준일 + r"\s*" + X.현재,
    X.이사회 + r"[^\n。]{0,40}?" + X.배당 + r"\s*" + X.기준일 + r"\s*(?:을|를)\s*정",
]))
# B_DIV: 조 머리에 '배당'이 있는 조 안에서만 보는 넓은 표현 (기준일 조의 '임시주총 … 이사회 결의로 기준일' 을 피한다)
B_DIV = re.compile(X.이사회 + r"[^\n。]{0,60}?" + X.기준일 + r"\s*(?:을|를)?\s*(?:따로\s*)?정\s*(?:할|하)")
결산 = r"(?:결\s*산\s*(?:기|일)?|決\s*算\s*(?:期|日)?|" + X.사업연도 + ")"
# F: 결산기말 고정 (결산말 · 결산기 말일 · 사업년도 말일에 · 영업연도 종료일 최종의 … 주주명부/주주)
F = re.compile("|".join([
    결산 + r"\s*" + X.말 + r"[^\n]{0,25}?(?:" + X.주주명부 + r"|주\s*주\s*(?:또는|에게|로|를)|株\s*主)",
    r"12\s*(?:월|月)\s*31\s*(?:일|日)[^\n]{0,90}?" + X.배당 + r"\s*" + X.받을,
    X.기준일 + r"\s*(?:은|는)\s*\d{1,2}\s*월\s*\d{1,2}\s*일\s*로",
]))
# R: 다른 조의 날을 참조 — 규칙으로는 그 조를 따라가지 않으므로 판정 보류
R = re.compile(r"제\s*\d+\s*조\s*(?:제?\s*\d+\s*항)?\s*(?:에서|에|에\s*따라)\s*정\s*한\s*(?:날|기준일)?\s*현\s*재")
# '… 현재 주주명부에 기재되어 있는 주주를 그 결산기에 관한 정기주주총회에서 권리를 행사할 주주로 한다' 는 의결권 기준일이다
VOTE_ONLY = re.compile(r"주\s*주\s*총\s*회|株\s*主\s*總\s*會")


def f_hit(seg: str) -> bool:
    for m in F.finditer(seg):
        tail = seg[m.end():m.end() + 80]
        if VOTE_ONLY.search(tail) and not re.search(X.배당, seg[m.start():m.end() + 80]):
            continue
        return True
    return False
FY_END = re.compile(r"결산|決算|사업\s*[연년]\s*도|事業年度|영업\s*[연년]\s*도|회계\s*[연년]\s*도|12\s*월\s*31\s*일|"
                    r"제\s*\d+\s*조|기준일|종료일|말일|末日|최종일")
SUBART = re.compile(r"(?:중\s*간|中\s*間|분\s*기|分\s*期)\s*" + X.배당)


def segments(t: str) -> list[tuple[str, str]]:
    """조 머리로 잘라 (머리 뒤 30자, 본문) — 머리를 못 찾는 원문은 통째로 하나."""
    pos = [m.start() for m in X.HEAD.finditer(t)]
    if len(pos) < 3:
        return [("", t)]
    pos = [0] + pos + [len(t)]
    return [(t[a:a + 30], t[a:b]) for a, b in zip(pos, pos[1:])]


def rule_tag(t: str) -> tuple[str, str]:
    t = re.sub(r"^\[발췌 \d+ · [^\]\n]*\]$", "", t, flags=re.M)      # s09a 머리말 줄
    b = f = r = False
    for head, seg in segments(t):
        h = head.split("\n")[0]
        only_sub = SUBART.search(h) and not re.search(r"(?:이\s*익|利\s*益)\s*" + X.배당 + r"\s*(?:및|과|,)", h)
        if only_sub:
            continue
        b = b or bool(B.search(seg)) or bool(re.search(X.배당, h) and B_DIV.search(seg))
        f = f or f_hit(seg)
        r = r or bool(R.search(seg))
    tag = {(True, True): "정관yesorno", (True, False): "정관no", (False, True): "정관yes"}.get((b, f))
    if tag is None:
        tag = "참조" if r else "?"
    return tag, ("B" if b else "") + ("F" if f else "") + ("R" if r else "")


# ── 인용 대조 ───────────────────────────────────────────────────────────────
def squash(s: str) -> str:
    # 공백과 제어문자(코스닥 셀레스트라 원문은 낱말 사이가 \x01)를 지우고 비교
    return re.sub(r"[\s\x00-\x1f]+", "", s)


def quotes_ok(quotes: list[str], src: str) -> bool:
    s = squash(src)
    return all(squash(q.strip("「」\"' ").rstrip("…").strip()) in s for q in quotes if q.strip())


# ── 제출 뒤 정관변경 ─────────────────────────────────────────────────────────
# '배당' 한 낱말은 너무 넓다(정관의변경.txt 에 재무제표 표·주식 소각 조문이 섞인다) — 기준일 판별에 닿는 문구만
DIVAMEND = re.compile("|".join([X.CORE.pattern, X.배당조머리, r"(?:중\s*간|분\s*기)\s*" + X.배당, X.기준일]))


def later_amend(t: dict) -> list[str]:
    hits = []
    for p in t.get("agm_charter_amend_txt") or []:
        f = ROOT / p
        if f.exists() and DIVAMEND.search(f.read_text(encoding="utf-8")):
            hits.append(Path(p).parent.name.split("_", 1)[-1])     # {접수일}_{rcept_no} → rcept_no
    return hits


DART_MAIN = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"


def INTERIM_OF(P: dict, name: str) -> Path:                       # noqa: N802 — s09a.paths 와 같은 접미어
    sfx = P["results"].stem.replace("s09b_results", "")
    stem, ext = name.rsplit(".", 1)
    return P["results"].parent / f"{stem}{sfx}.{ext}"


def current_basis(t: dict, tag: str, o: dict, ag: dict, agm_res: dict, pv: dict | None, pre: dict | None = None) -> dict:
    """지금 유효한 태그와 그 근거 (사용자 지시 2026-11-16 — 웹페이지 '분류근거의 종류').

    · 기본: 사업보고서 첨부 정관 (`tag`)
    · 제출 뒤 '정관의 변경' 안건이 결산배당 기준일을 바꾸고(s09d) KIND 주주총회결과에서 가결(s09e) → 소집공고 + 결과공시
    · 확인필요 회사(s09f): 전년도 사업보고서 첨부 정관 → 그 뒤 소집공고 안건이 바꾸고 가결되면 소집공고
      정관이 어느 해에도 없으면(OCI) 소집공고 안건 + 사업보고서 본문 '배당관련 예측가능성' 표
    """
    out = {"tag_current": tag, "basis_kind": "사업보고서", "basis_rcept_no": t["rcept_no"],
           "basis_doc_url": DART_MAIN.format(t["rcept_no"]), "basis_charter_url": t["charter_url"],
           "basis_notice_rcept_no": None, "basis_notice_url": None, "basis_result_acptno": None, "basis_result_url": None,
           "basis_result_title": None, "basis_agm_date": None, "basis_prev_report_nm": None, "basis_note": None}
    if t.get("charter_source_doc"):         # 사업보고서가 없는 회사(absent_charter) — 정관을 찾은 문서가 근거
        out.update(basis_kind=t["charter_source_doc"], basis_rcept_no=t.get("charter_source_rcept_no") or None,
                   basis_doc_url=t.get("charter_source_url"),
                   basis_note=f"사업보고서 없음({t.get('reason') or ''}) → {t['charter_source_doc']} 정관")

    def use_notice(rc: str, new_tag: str, why: str) -> bool:
        res = agm_res.get(rc) or {}
        if not res.get("passed"):
            out["basis_note"] = f"소집공고 {rc} 안건은 기준일을 바꾸지만 KIND 결과로 가결을 확인하지 못해 반영하지 않음 ({res.get('note')})"
            return False
        out.update(tag_current=new_tag, basis_kind="주총소집공고", basis_notice_rcept_no=rc,
                   basis_notice_url=DART_MAIN.format(rc), basis_result_acptno=res["result_acptno"],
                   basis_result_url=res["result_url"], basis_result_title=res.get("result_title"),
                   basis_agm_date=res.get("agm_date") or (res.get("result_time") or "")[:10],
                   basis_note=f"{why} · KIND {res.get('result_title')} {res.get('note')}")
        return True

    if pv and pv.get("output"):
        po = pv["output"]
        if pv.get("charter_fulltext_txt"):
            out.update(tag_current=po.get("tag"), basis_kind="전년도 사업보고서", basis_rcept_no=pv["prev_rcept_no"],
                       basis_doc_url=DART_MAIN.format(pv["prev_rcept_no"]), basis_charter_url=pv.get("charter_url"),
                       basis_prev_report_nm=pv.get("prev_report_nm"),
                       basis_note=f"지금 사업보고서 첨부 정관을 읽을 수 없어 전년도 {pv.get('prev_report_nm')} 첨부 정관으로 판별")
            for n in sorted(pv.get("notices") or [], key=lambda x: x["rcept_dt"]):
                no = n.get("output") or {}
                if no.get("changes_record_date") and no.get("tag_after") != out["tag_current"]:
                    use_notice(n["rcept_no"], no["tag_after"], f"전년도 정관({po.get('tag')}) 뒤 소집공고 안건")
        else:                                            # OCI — 정관 원문 없음
            src = {n["rcept_no"]: (ROOT / n["txt"]).read_text(encoding="utf-8") for n in pv.get("notices") or [] if n.get("txt")}
            rc = next((k for k, s in sorted(src.items()) if quotes_ok(po.get("quotes") or [], s) and po.get("quotes")), None)
            if rc is None:                               # 인용 하나라도 든 공고
                rc = next((k for k, s in sorted(src.items()) for q in po.get("quotes") or [] if quotes_ok([q], s)), None)
            if rc and use_notice(rc, po.get("tag"), "정관 원문을 어느 해에도 읽을 수 없어 안건 '변경 후' 문구로 판별"):
                out["basis_kind"] = "주총소집공고+사업보고서 본문"
            else:
                out.update(tag_current=po.get("tag"), basis_kind="사업보고서 본문",
                           basis_note="사업보고서 본문 '배당관련 예측가능성' 표로 판별")
        return out
    # 사업보고서보다 먼저 접수된 소집공고(s09i — 그해 정기주총) 안건: 첨부 정관은 주총 전 판이라 가결되면 그 뒤 태그
    po = (pre or {}).get("output") or {}
    if po.get("changes_record_date") and po.get("tag_after") and po.get("tag_after") != tag:
        for rc in sorted((pre or {}).get("rcept_nos") or []):
            if use_notice(rc, po["tag_after"], "사업보고서보다 먼저 접수된 소집공고 안건(첨부 정관은 주총 전 판)"):
                break
    if ag and ag.get("changes_record_date") and ag.get("tag_after") and ag.get("tag_after") != out["tag_current"]:
        rcs = later_amend(t)
        for rc in sorted(rcs):
            if use_notice(rc, ag["tag_after"], "사업보고서 제출 뒤 소집공고 안건"):
                break
    return out


def amend_year(note: str) -> int | None:
    ys = [int(y) for y in re.findall(r"((?:19|20)\d\d)", note or "")]
    return max(ys) if ys else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx", default="")
    ap.add_argument("--queue", action="store_true", help="review=True 행을 화면에")
    a = ap.parse_args()
    P = X.paths(a.sfx)
    targets = read_json(P["targets"])
    ex = {e["stock_code"]: e for e in map(json.loads, P["excerpts"].read_text(encoding="utf-8").splitlines())}
    res = read_results(P["results"])
    review = read_json(P["review"]) if P["review"].exists() else {}
    after_f = P["results"].with_name(P["results"].name.replace("s09b_results", "s09d_after_agm"))
    after = {r["stock_code"]: r for r in read_results(after_f).values() if r.get("output")}
    pre_m = {r["stock_code"]: r for r in read_results(INTERIM_OF(P, "s09i_pre_agm.jsonl")).values() if r.get("output")}
    agm_f, prev_f = INTERIM_OF(P, "s09e_agm_results.json"), INTERIM_OF(P, "s09f_prev.json")
    agm_res = read_json(agm_f) if agm_f.exists() else {}
    prev = read_json(prev_f) if prev_f.exists() else {}
    rows = []
    for t in targets:
        code = t["stock_code"]
        e = ex[code]
        r = res.get(f"f_{code}") if res.get(f"f_{code}", {}).get("output") else res.get(f"d_{code}")
        o = (r or {}).get("output") or {}
        mode = (r or {}).get("mode")
        full = (ROOT / e["src"]).read_text(encoding="utf-8") if e["src"] and (ROOT / e["src"]).exists() else ""
        sent = full if mode == "full" else e["excerpt"]
        qok = quotes_ok(o.get("quotes") or [], sent) if o else None
        rt, rbits = rule_tag(e["excerpt"]) if not e["no_text"] else ("?", "")
        llm_tag = o.get("tag")
        why = []
        if r is None or not o:
            why.append("LLM 결과 없음" + (f"({r.get('error')})" if r else ""))
        if llm_tag == "확인필요":
            why.append("확인필요")
        if o.get("confidence") in ("낮음", "보통"):
            why.append(f"확신도 {o.get('confidence')}")
        if o and o.get("quotes") and not qok:
            why.append("인용 불일치")
        # 규칙이 태그를 냈는데 LLM 과 다를 때만 (규칙 '?'·'참조' 는 판정 보류라 불일치로 세지 않는다 — 집계에는 남는다)
        if llm_tag and llm_tag != "확인필요" and rt in L_TAGS and rt != llm_tag:
            why.append(f"규칙 {rt}")
        # 표준정관 주석이 허용한 '결산일이 아닌 고정일'(예: 4월 10일) — 태그는 정관yes 지만 뜻이 다르니 사람이 본다
        fp = o.get("fixed_point") or ""
        if llm_tag in ("정관yes", "정관yesorno") and fp and not FY_END.search(fp):
            why.append(f"고정일이 결산일 아님?({fp})")
        rv = review.get(code)
        la = later_amend(t)
        # s09d — 제출 뒤 '정관의 변경' 안건이 원안대로 가결되면 (가결 여부는 확인하지 않음)
        ag = (after.get(code) or {}).get("output") or {}
        ag_qok = None
        if ag:
            amend_src = "\n".join((ROOT / p).read_text(encoding="utf-8") for p in t.get("agm_charter_amend_txt") or []
                                  if (ROOT / p).exists())
            ag_qok = quotes_ok(ag.get("quotes_after") or [], amend_src)
            if not ag_qok:
                why.append("안건 인용 불일치")
        final_tag = (rv or {}).get("tag") or llm_tag
        pre = pre_m.get(code)
        cur = current_basis(t, final_tag, o, ag, agm_res, prev.get(code), pre)
        rows.append({
            "stock_code": code, "corp_name": t["corp_name"], "corp_code": t["corp_code"], "market": t["market"],
            "sec_group": t["sec_group"], "settle_month": t["settle_month"], "fiscal_year": t["fiscal_year"],
            "rcept_no": t["rcept_no"], "charter_att_date": t["charter_att_date"], "charter_url": t["charter_url"],
            "charter_content_type": t["charter_content_type"], "charter_fulltext_txt": t["charter_fulltext_txt"],
            "tag": final_tag,
            "llm_tag": llm_tag, "route": o.get("route"), "basis_article": o.get("basis_article"),
            "quotes": o.get("quotes") or [], "fixed_point": o.get("fixed_point"),
            "board_may_set": o.get("board_may_set"), "amend_note": o.get("amend_note"),
            "amend_year": amend_year(o.get("amend_note")), "interim": o.get("interim"), "quarterly": o.get("quarterly"),
            "confidence": o.get("confidence"), "note": o.get("note"),
            "quote_ok": qok, "rule_tag": rt, "rule_bits": rbits, "llm_mode": mode,
            "review": bool(why), "review_reason": "; ".join(why),
            "reviewed_tag": (rv or {}).get("tag"), "reviewed_why": (rv or {}).get("why"),
            "later_amend_dividend": bool(la), "later_amend_rcept_nos": la,
            "agm_amends_record_date": ag.get("changes_record_date") if ag else None,
            "agm_tag_after": ag.get("tag_after") if ag else None,
            "agm_interim_after": ag.get("interim_after") if ag else None,
            "agm_quarterly_after": ag.get("quarterly_after") if ag else None,
            "agm_quotes_after": ag.get("quotes_after") or [] if ag else [],
            "agm_note": ag.get("note") if ag else None, "agm_quote_ok": ag_qok,
            # 첨부 정관 태그 → 안건 가결 가정 태그 (안건이 없거나 기준일을 건드리지 않으면 tag 그대로)
            "tag_after_agm": (ag.get("tag_after") if ag and ag.get("changes_record_date") else None) or final_tag,
            # s09i — 사업보고서보다 먼저 접수된 소집공고(그해 정기주총)의 '정관의 변경' 안건
            "pre_agm_rcept_nos": (pre or {}).get("rcept_nos") or [],
            "pre_agm_amends_record_date": ((pre or {}).get("output") or {}).get("changes_record_date") if pre else None,
            "pre_agm_tag_after": ((pre or {}).get("output") or {}).get("tag_after") if pre else None,
            "pre_agm_quotes_after": ((pre or {}).get("output") or {}).get("quotes_after") or [] if pre else [],
            "pre_agm_note": ((pre or {}).get("output") or {}).get("note") if pre else None,
            **cur,
            "excerpt_chars": e["excerpt_chars"], "full_chars": e["full_chars"],
            "llm_model": (r or {}).get("model"), "prompt_sha256": (r or {}).get("prompt_sha256"),
        })
    write_json(P["out_json"], rows)
    cols = list(rows[0].keys())
    with P["out_csv"].open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items()})
    sm = {
        "built_at": now_iso(), "n": len(rows),
        "tag": Counter(r["tag"] for r in rows), "llm_tag": Counter(r["llm_tag"] for r in rows),
        "route": Counter(r["route"] for r in rows), "interim": Counter(r["interim"] for r in rows),
        "quarterly": Counter(r["quarterly"] for r in rows), "confidence": Counter(r["confidence"] for r in rows),
        "llm_mode": Counter(r["llm_mode"] for r in rows),
        "quote_ok": Counter(str(r["quote_ok"]) for r in rows),
        "rule_vs_llm": Counter(f"{r['llm_tag']}|{r['rule_tag']}" for r in rows),
        "review": sum(r["review"] for r in rows), "reviewed": sum(bool(r["reviewed_tag"]) for r in rows),
        "later_amend_dividend": sum(r["later_amend_dividend"] for r in rows),
        "agm_checked": sum(r["agm_tag_after"] is not None for r in rows),
        "agm_amends_record_date": sum(bool(r["agm_amends_record_date"]) for r in rows),
        "tag_after_agm": Counter(r["tag_after_agm"] for r in rows),
        "tag_to_after_agm": Counter(f"{r['tag']}→{r['tag_after_agm']}" for r in rows if r["tag"] != r["tag_after_agm"]),
        "tag_by_amend_year": Counter(f"{r['tag']}|{r['amend_year']}" for r in rows if r["tag"] == "정관no"),
        "prompt_sha256": Counter(r["prompt_sha256"] for r in rows),
    }
    write_json(P["summary"], sm)
    print(json.dumps({k: v for k, v in sm.items() if k not in ("tag_by_amend_year",)}, ensure_ascii=False, indent=1,
                     default=dict))
    print(f"→ {P['out_json'].relative_to(ROOT)} · {P['out_csv'].relative_to(ROOT)}")
    if a.queue:
        for r in rows:
            if r["review"] and not r["reviewed_tag"]:
                print(f"\n■ {r['stock_code']} {r['corp_name']} — LLM {r['llm_tag']} · 규칙 {r['rule_tag']}({r['rule_bits']})"
                      f" · {r['confidence']} · {r['review_reason']}\n  {r['basis_article']} · {r['note']}")
                for q in r["quotes"]:
                    print(f"  「{q[:300]}」")


if __name__ == "__main__":
    main()
