"""s09e 정관변경 안건이 실제로 가결됐나 — KIND 주주총회결과 공시 (krx-kind-data-api)

왜: 사용자 지시(2026-11-16) — 사업보고서 제출 뒤 '정관의 변경' 안건으로 결산배당 기준일이 바뀌는 회사는 주총결과를
    kind-api-data 로 받아 확인하고, 웹페이지 '분류근거의 종류'에 소집공고 URL 옆에 결과공시 URL 을 단다.

대상 소집공고
  · s09d 가 '결산배당 기준일 조항을 고친다'(changes_record_date)고 본 공고
  · s09f(확인필요 회사의 대체 자료)의 소집공고 중 '정관의 변경' 절이 있는 것
방법 (KIND, 분당 40요청 이하 — 요청 사이 1.6초)
  ① fetch("disclosure_details", repIsuSrtCd='A'+종목코드, fromDate=공고 접수일, toDate=+80일) 에서 공시제목에 '주주총회결과'가
     든 공시. KIND 는 정정 공시를 최신본으로 보여 준다.
     · 종목코드 앞 'A' 는 직접 붙인다 — krx-kind-data-api 는 숫자 6자리일 때만 붙여, 알파벳이 든 코드(0120G0 등)는 0건이 됐다
       (삼양바이오팜 '결과 공시 없음', 2026-11-17 확인. 라이브러리도 고침 — krx-kind-data-api 1c7f5fc).
     · 어느 결과가 그 공고의 주총인지: 소집공고 원문의 주총 '일시'와 결과 공시의 '주주총회일자'(없으면 공시일)가 같은 결과.
       같은 날 정기 + 임시주총이면 그중 정관 안건이 든 것(아센디오). 예전에는 공고 뒤 첫 결과만 봤고(아센디오 오판), 잠깐
       결과 공시 '※ 관련공시'의 소집공고 날짜로 짝지었으나 관련공시에 소집공고가 꼭 실리지 않아 주총일로 바꿨다(사용자 지적 2026-11-17).
       공고의 주총일과 같은 날 결과가 없으면 결과 없음(남의 주총 결과를 붙이지 않는다 — s09c 가 '못 찾음'으로 다룬다).
       공고 원문이 없어 주총일을 모르면 관련공시 → 시간 순. 같은 주총일에 정관 안건이 든 결과가 둘 이상(정정 재공시 등)이면 ambiguous=True.
  ② disclosure_content_html(접수번호) → 【주주총회 안건 세부내역】 표의 행 {번호, 결의구분, 회의목적사항, 가결여부}
     중 회의목적사항에 '정관'이 든 행. 주주총회일자·의결권행사기준일도 읽는다.
  ③ 판정 passed: 배당·기준일이 든 세부 안건(없으면 정관 안건 전체)이 모두 가결 → True, 아니면 None(사람이 본다)
     · 결과 공시 없음 → None
  ④ 제목으로 정관 안건을 정할 수 없거나(세부 안건 제목에 '정관'이 없음 · 표가 없는 서식) 정관 안건 일부만 가결이면 세션 안
     서브에이전트가 소집공고 안건 · 대비표와 결과를 함께 읽어 판별한다(`pack` → 서브에이전트 → `ingest`, 사용자 지시 2026-11-17
     "넘버링 체계가 다르면 문제가 생긴다 — LLM 에이전트가 판별"). 판별은 data/interim/s09e_llm{_kosdaq}.json 에 두고 판정에 쓴다.
출력  data/interim/s09e_agm_results.json  소집공고 접수번호 → {stock_code, corp_name, notice_dt, result_acptno, result_title,
                                          result_url, agm_date, record_date_vote, rows, charter_rows, passed, note}

사용법
  python -X utf8 scripts/s09e_agm_result_kind.py            # 결과가 없는 공고만
  python -X utf8 scripts/s09e_agm_result_kind.py --force    # 다시
  python -X utf8 scripts/s09e_agm_result_kind.py --redo     # 결과를 못 고른 공고만 다시 받기
  python -X utf8 scripts/s09e_agm_result_kind.py pack [--sfx kosdaq]     # 서브에이전트 입력 (data/interim/s09e_agent{_kosdaq}/in, 지시.md)
  python -X utf8 scripts/s09e_agm_result_kind.py ingest [--sfx kosdaq]   # out/*.json → s09e_llm{_kosdaq}.json → 다시 판정
  python -X utf8 scripts/s09e_agm_result_kind.py --sfx kosdaq   # 코스닥 (s09d·s09f 의 _kosdaq 파일)
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import INTERIM, RAW, now_iso, read_json, write_json  # noqa: E402
from s09a_dividend_excerpt import interim_of  # noqa: E402
from s09b_dividend_tag_llm import read_results  # noqa: E402

OUT_F = INTERIM / "s09e_agm_results.json"           # main() 의 --sfx 로 바뀐다 (코스닥: s09e_agm_results_kosdaq.json)
CACHE = RAW / "kind_agm_result"
GAP = 1.6
KIND_VIEW = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={}"
# 소집공고 접수번호 → (판정할 안건 번호, 까닭) — 결과 공시 안건 표에 '정관'이 든 제목이 없을 때 원문 대조로 지정
MANUAL_ROWS = {
    "20260916000468": (["5-1", "5-2"], "베노티앤알 — 정관 변경이 '5-1 1주의 금액 변경의 건'·'5-2 사업목적추가 및 상법개정안 반영의 건'으로 나뉨"),
}


# 판정할 행: 배당·기준일이 든 세부 안건(제목에 '정관'이 없을 때가 많다 — '배당제도 개선의 건') → 없으면 '정관' 안건 전체.
# 배당금 결의·지급 안건('제15기 현금 배당 결의의 건' — 삼성FN리츠)은 정관 안건이 아니므로 뺀다(정관·기준일·제도·절차가 든 제목은 남김).
DIV_DECL = re.compile(r"배\s*당\s*(?:금\s*)?(?:액\s*)?(?:결\s*의|지\s*급|승\s*인|결\s*정)|(?:현\s*금|주\s*식|현\s*물|결\s*산)\s*배\s*당\s*(?:의\s*)?건")
KEEP = re.compile(r"정\s*관|기\s*준\s*일|제\s*도|절\s*차")
# 사람 이름의 '정관' — '사내이사 신정관 해임의 건'·'이사보수 한도 승인의 건(신정관)' ('이사 및 감사의 선임·해임 등' 같은 정관 안건 제목은 남김)
PERSON = re.compile(r"(?:사내이사|사외이사|기타비상무이사|이사|감사|위원)\s+[가-힣]{0,2}정관(?:\s|\)|의|$)|\([가-힣]{1,2}정관\)")


# 소집공고 원문: s09i = data/raw/opendart_doc_pre/{접수번호}.zip · s09f = data/raw/opendart_doc_prev/{접수번호}.zip · s09d = data/agm*/…/{날짜}_{접수번호}/{접수번호}.xml
def notice_text(rc: str) -> str | None:
    import html as _html
    import zipfile
    from _common import ROOT
    raw = None
    for d in ("opendart_doc_pre", "opendart_doc_prev"):
        z = RAW / d / f"{rc}.zip"
        if z.exists():
            try:
                with zipfile.ZipFile(z) as zf:
                    raw = zf.read(zf.namelist()[0])
                break
            except (zipfile.BadZipFile, IndexError):
                pass
    if raw is None:
        xs = sorted((ROOT / "data").glob(f"agm*/*/*_{rc}/{rc}.xml"))
        raw = xs[0].read_bytes() if xs else None
    if raw is None:
        return None
    for enc in ("utf-8", "cp949"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            t = None
    if t is None:
        return None
    t = re.sub(r"<(?:P|TR|BR|TD|TH|TITLE|SECTION-\d)[^>]*>", "\n", t, flags=re.I)
    return _html.unescape(re.sub(r"<[^>]+>", " ", t))


def judge_rows(rows: list[dict], rc: str) -> tuple[list[dict], list[dict]]:
    drow = [r for r in rows if re.search(r"배당|기준일", r["item"]) and not re.search(r"재무제표|이익잉여금|결손금", r["item"])
            and (KEEP.search(r["item"]) or not DIV_DECL.search(r["item"]))]
    # '정관 (일부) 변경·개정' 안건만 — '사내이사 신정관 해임의 건'처럼 사람 이름의 '정관'을 잡지 않게 (코스닥 아틀라스링크)
    # 제목에 '정관'이 든 안건 — 단 이사 선임·해임·보수 안건의 사람 이름('사내이사 신정관 해임의 건')은 빼고.
    # '정관 (일부) 변경의 건'·'개정상법 및 표준정관 반영'·'기타 정관 정비'·'정관 내용 변경의 건' 처럼 제목이 제각각이다.
    crow = drow or [r for r in rows if re.search(r"정\s*관", r["item"]) and not PERSON.search(r["item"])]
    if not crow and rc in MANUAL_ROWS:      # 정관 변경이 제목에 '정관' 없는 세부 안건으로만 나뉜 경우 (원문 대조로 지정)
        crow = [r for r in rows if r["no"] in MANUAL_ROWS[rc][0]]
    return crow, drow


def verdict(crow: list[dict], drow: list[dict]) -> tuple[bool | None, str]:
    passed = True if crow and {r["result"] for r in crow} <= {"가결"} else None
    note = ((f"배당 관련 세부 안건 {', '.join(r['no'] for r in drow)} 가결" if drow else "정관 안건 모두 가결") if passed
            else "판정 안건 중 가결 아닌 것 있음 — 세부 안건 확인 필요" if crow else "안건 표에서 정관 안건을 찾지 못함")
    return passed, note


def old_form_rows(txt: str) -> list[dict]:
    """안건 표가 없는 옛·임시주총 서식: '제2호 의안:정관 일부 변경의 건 ☞ 원안대로 승인' 또는
    '제1-1호 의안 : 제17조(주주명부의 폐쇄) (부결)'(루트K) 줄. 결과가 없는 상위 안건 줄은 뺀다."""
    rows = []
    for m in re.finditer(r"(제\s*[\d\-]+\s*호)\s*의안\s*[:：]\s*([^\n]+)\n\s*[☞→]\s*([^\n]+)", txt):     # '→ 원안대로 승인'(한스바이오메드)도
        res_t = m.group(3).strip()
        rows.append({"no": m.group(1), "kind": "", "item": m.group(2).strip(),
                     "result": "가결" if re.search(r"승인|가결", res_t) and "부결" not in res_t else res_t})
    if not rows:
        for m in re.finditer(r"(제\s*[\d\-]+\s*호)\s*의안\s*[:：]?\s*([^\n]+?)\s*\((가결|부결|철회|폐기|미결)\)\s*$", txt, flags=re.M):
            rows.append({"no": m.group(1), "kind": "", "item": m.group(2).strip(), "result": m.group(3)})
    return rows


def notice_meeting_days(rc: str) -> list[str]:
    """소집공고 원문의 주총 '일시' 날짜들(나온 순서, 겹침 없이) → [YYYY-MM-DD]. [기재정정] 공고는 정정표에 '정정 전' 날짜가
    먼저 나오고 정정 후 · 본문 날짜가 뒤에 온다(씨아이테크 3/24 → 3/31, 비츠로시스 3/26 → 3/27) — 그래서 뒤의 것을 앞세운다."""
    t = notice_text(rc) or ""
    out = []
    for m in re.finditer(r"일\s*시\s*[:：]?\s*(\d{4})\s*[년.\-]\s*(\d{1,2})\s*[월.\-]\s*(\d{1,2})", t):
        d = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        if d in out:
            out.remove(d)
        out.append(d)
    return out


def notice_meeting_day(rc: str) -> str | None:
    """소집공고의 주총일 — '일시' 날짜 중 마지막(정정 후 · 본문)."""
    ds = notice_meeting_days(rc)
    return ds[-1] if ds else None


def result_meeting_day(txt: str) -> str | None:
    """결과 공시의 '주주총회일자'(임시주총 서식은 '주주총회 일자') → YYYY-MM-DD."""
    m = re.search(r"주주총회\s*일\s*자\s*\n?\s*(\d{4})\s*[-.년]\s*(\d{1,2})\s*[-.월]\s*(\d{1,2})", txt)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def choose(rc: str, metas: list[dict]) -> dict:
    """공고 뒤 결과 공시들(metas: acptno · title · time) 중 그 공고의 주총 결과를 골라 판정까지 → rec 에 넣을 값."""
    reads = [(m, *read_result(m["acptno"], rc)) for m in metas]
    days = notice_meeting_days(rc)
    nd = days[-1] if days else None
    day = lambda r: result_meeting_day(r[1]) or str(r[0]["time"])[:10]  # noqa: E731
    if nd:
        cand, how = [], "주총일"
        for d in reversed(days):                 # 정정 후 날짜부터
            cand = [r for r in reads if day(r) == d]
            if cand:
                nd = d
                break
    else:
        ndt = f"{rc[:4]}-{rc[4:6]}-{rc[6:8]}"
        rel = [r for r in reads if ndt in related_notice_dates(r[1])]
        cand, how = (rel, "관련공시") if rel else (reads, "순서")
    win = [{"acptno": r[0]["acptno"], "title": r[0]["title"], "time": r[0]["time"], "meeting_day": day(r),
            "charter_rows": len(r[3])} for r in reads]
    base = {"meeting_day": nd, "n_results_in_window": len(reads), "results_in_window": win, "match_by": how if cand else None}
    if not cand:
        return {**base, "result_acptno": None, "result_title": None, "result_time": None, "result_url": None, "agm_date": None,
                "rows": [], "charter_rows": [], "by_dividend_row": False, "passed": None, "ambiguous": False, "basis_box": None,
                "note": f"공고의 주총일({nd})과 같은 날 KIND 주주총회결과 공시 없음 (공고 뒤 80일 안 결과 {len(reads)}건: "
                        f"{', '.join(w['meeting_day'] or '?' for w in win)})"}
    with_c = [r for r in cand if r[3]]
    lj = LLM.get(rc) or {}
    pick = next((r for r in cand if r[0]["acptno"] == lj.get("result_acptno")), None) if lj else None
    first, txt, rows, crow, drow = pick or (with_c or cand)[0]
    m_rec = re.search(r"의결권행사기준일\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt)
    i = txt.find("정관상 기준일 설정 및 변경 세부내역")
    passed, note = verdict(crow, drow)
    if pick:                                  # 서브에이전트 판별 (제목으로 못 정하던 결과 · 일부만 가결)
        by_no = {r["no"]: r for r in rows}
        crow = [by_no.get(n) or {"no": n, "kind": "", "item": "(결과 글에서 읽음)", "result": ""} for n in lj["charter_rows"]]
        drow = [by_no.get(n) or {"no": n, "kind": "", "item": "(결과 글에서 읽음)", "result": ""} for n in lj["dividend_rows"]]
        if lj["passed"] is True:
            passed, note = True, f"서브에이전트 판별: 배당기준일 안건 {', '.join(lj['dividend_rows'])} 가결 — {lj['why']}"
        elif lj["passed"] is False:
            passed, note = None, f"판정 안건 중 가결 아닌 것 있음 — 서브에이전트 판별: {lj['why']}"
        else:
            passed, note = None, f"안건 표에서 정관 안건을 찾지 못함 — 서브에이전트 판별: {lj['why']}"
    return {**base, "result_acptno": first["acptno"], "result_title": first["title"], "result_time": first["time"],
            "result_url": KIND_VIEW.format(first["acptno"]), "agm_date": result_meeting_day(txt) or nd,
            "vote_record_date": m_rec.group(1) if m_rec else None,
            "rows": rows, "charter_rows": crow, "dividend_rows": drow, "by_dividend_row": bool(drow), "passed": passed, "note": note,
            "ambiguous": len(with_c) > 1, "basis_box": txt[i:i + 400].split("\n※")[0] if i >= 0 else None,
            "judged_by": "서브에이전트" if pick else "제목"}


def read_result(acpt: str, rc: str):
    """결과 공시 원문(캐시, 없으면 KIND 에서 받음) → (글, 안건 행, 판정 행, 배당 행)."""
    f = CACHE / f"{acpt}.html"
    if not f.exists():
        from krx_kind_data_api import disclosure_content_html
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(disclosure_content_html(acpt), encoding="utf-8")
        time.sleep(GAP)
    h = f.read_text(encoding="utf-8")
    txt = html_text(h)
    rows = agenda_rows(h) or old_form_rows(txt)
    crow, drow = judge_rows(rows, rc)
    return txt, rows, crow, drow


def recompute(out: dict) -> int:
    """판정을 다시 계산한다 — 결과 공시 캐시가 있으면 원문을 다시 읽고(표 읽기 규칙을 고친 뒤), 없으면 저장된 안건 표로.
    네트워크 없이 맞춘다. 바뀐 건수를 돌려준다."""
    n = 0
    for rc, rec in out.items():
        metas = rec.get("results_in_window") or ([{"acptno": rec["result_acptno"], "title": rec.get("result_title") or "",
                                                   "time": rec.get("result_time") or ""}] if rec.get("result_acptno") else [])
        metas = [m for m in metas if (CACHE / f"{m['acptno']}.html").exists()]
        if not metas:
            continue
        before = (rec.get("result_acptno"), rec.get("passed"), rec.get("note"))
        rec.update(choose(rc, [{k: m[k] for k in ("acptno", "title", "time")} for m in metas]))
        if (rec.get("result_acptno"), rec.get("passed"), rec.get("note")) != before:
            print(f"  다시 판정 {rec['stock_code']} {rec['corp_name']} {rc}: {before[0]} {before[2]} → {rec.get('result_acptno')} {rec.get('note')}")
            n += 1
        for k in ("matched_by_related",):
            rec.pop(k, None)
    return n


def targets(sfx: str = "") -> list[dict]:
    out = {}
    names = {r["stock_code"]: r["corp_name"] for r in read_json(interim_of(sfx, "s09_targets.json"))}
    for r in read_results(interim_of(sfx, "s09d_after_agm.jsonl")).values():
        o = r.get("output") or {}
        if o.get("changes_record_date"):
            for rc in r["rcept_nos"]:
                out[rc] = {"stock_code": r["stock_code"], "corp_name": r["corp_name"], "notice_rcept_no": rc,
                           "notice_dt": rc[:8], "from": "s09d"}
    # s09i 공고 중 기준일 판별 문구(DIVAMEND)가 걸린 것은 판별 전에 미리 받아 둔다(수집 세션과 판별 세션이 다르다 — 2026-11-17)
    tf = interim_of(sfx, "s09i_targets.json")
    if tf.exists():
        from s09c_dividend_build import DIVAMEND
        from _common import ROOT
        for t in read_json(tf):
            for n in t["notices"]:
                if n.get("txt") and DIVAMEND.search((ROOT / n["txt"]).read_text(encoding="utf-8")):
                    out.setdefault(n["rcept_no"], {"stock_code": t["stock_code"], "corp_name": t["corp_name"],
                                                   "notice_rcept_no": n["rcept_no"], "notice_dt": n["rcept_dt"], "from": "s09i"})
    for r in read_results(interim_of(sfx, "s09i_pre_agm.jsonl")).values():      # 사업보고서보다 먼저 접수된 소집공고 (s09i)
        o = r.get("output") or {}
        if o.get("changes_record_date"):
            for rc in r["rcept_nos"]:
                out.setdefault(rc, {"stock_code": r["stock_code"], "corp_name": r["corp_name"], "notice_rcept_no": rc,
                                    "notice_dt": rc[:8], "from": "s09i"})
    pf = interim_of(sfx, "s09f_prev.json")
    prev = read_json(pf) if pf.exists() else {}
    for code, rec in prev.items():
        for n in rec.get("notices") or []:
            if n.get("txt"):
                out.setdefault(n["rcept_no"], {"stock_code": code, "corp_name": names.get(code, ""),
                                               "notice_rcept_no": n["rcept_no"], "notice_dt": n["rcept_dt"], "from": "s09f"})
    return list(out.values())


def html_text(h: str) -> str:
    t = re.sub(r"<(?:tr|p|br|div)[^>]*>", "\n", h, flags=re.I)
    t = re.sub(r"<t[dh][^>]*>", " | ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t).replace("&nbsp;", " ")
    return "\n".join(re.sub(r"\s+", " ", ln).strip(" |") for ln in t.splitlines() if ln.strip(" |\t"))


def related_notice_dates(txt: str) -> set[str]:
    """결과 공시 '※ 관련공시' 목록의 소집공고 날짜 (YYYY-MM-DD) — 그 결과가 어느 소집공고의 주총인지."""
    i = txt.find("관련공시")
    seg = txt[i:i + 600] if i >= 0 else ""
    return set(re.findall(r"(\d{4}-\d{2}-\d{2})\s*(?:\[[^\]]*\])?\s*주주총회\s*소집\s*공고", seg))


def agenda_rows(h: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(h, "lxml")
    rows = []
    for tb in soup.find_all("table"):
        cells = [[re.sub(r"\s+", " ", td.get_text(" ")).strip() for td in tr.find_all(["td", "th"])] for tr in tb.find_all("tr")]
        head_i = next((i for i, c in enumerate(cells) if any("회의목적사항" in x for x in c) and any("가결" in x for x in c)), None)
        if head_i is None:
            continue
        hdr = cells[head_i]
        ix = {k: next((j for j, x in enumerate(hdr) if k in x), None) for k in ("번호", "결의구분", "회의목적사항", "가결여부")}
        for c in cells[head_i + 1:]:
            if len(c) < len(hdr) - 2 or ix["회의목적사항"] is None or ix["회의목적사항"] >= len(c):
                continue
            g = lambda k: c[ix[k]] if ix[k] is not None and ix[k] < len(c) else ""  # noqa: E731
            if g("회의목적사항"):
                rows.append({"no": g("번호"), "kind": g("결의구분"), "item": g("회의목적사항"), "result": g("가결여부")})
    return rows


LLM: dict = {}          # 소집공고 접수번호 → 서브에이전트 판별 (load_llm)
LLM_KEYS = {"charter_rows": list, "dividend_rows": list, "passed": (bool, type(None)), "confidence": str, "why": str}


def llm_file(sfx: str) -> Path:
    return interim_of(sfx, "s09e_llm.json")


def agent_dir(sfx: str) -> Path:
    return interim_of(sfx, "s09e_agent.json").with_suffix("")


def load_llm(sfx: str) -> dict:
    global LLM
    f = llm_file(sfx)
    LLM = read_json(f) if f.exists() else {}
    return LLM


def needs_agent(rec: dict) -> bool:
    """결과는 골랐는데 제목으로 정관 안건을 못 정했거나(세부 안건에 '정관' 없음 · 표 없는 서식), 정관 안건 일부만 가결."""
    return bool(rec.get("result_acptno")) and (not rec.get("charter_rows") or "가결 아닌 것" in (rec.get("note") or ""))


def notice_amend_lines(rc: str, n: int = 8) -> list[str]:
    from _common import ROOT
    fs = sorted((ROOT / "data").glob(f"agm*/*/*_{rc}/정관의변경.txt"))
    if not fs:
        return []
    lines = [ln for ln in fs[0].read_text(encoding="utf-8").splitlines() if re.search(r"배\s*당|기\s*준\s*일|주주명부", ln)]
    return [ln[:900] for ln in lines[:n]]


def notice_agenda(t: str, n: int = 2500) -> str:
    i = next((m.start() for m in re.finditer(r"회\s*의\s*목\s*적\s*사\s*항|부\s*의\s*안\s*건", t)), 0)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t[i:i + n]))


def pack(sfx: str) -> None:
    out = read_json(interim_of(sfx, "s09e_agm_results.json"))
    llm = load_llm(sfx)
    d = agent_dir(sfx)
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    items = []
    for rc, rec in out.items():
        if not needs_agent(rec) or (llm.get(rc) or {}).get("result_acptno") == rec["result_acptno"]:
            continue
        rtxt = html_text((CACHE / f"{rec['result_acptno']}.html").read_text(encoding="utf-8"))
        k = next((m.start() for m in re.finditer(r"기타\s*(?:결의|투자)|결의\s*사항|안건\s*세부내역", rtxt)), 0)
        body = [f"회사: {rec['corp_name']} ({rec['stock_code']})",
                f"소집공고 접수번호: {rc} · 공고의 주총일: {rec.get('meeting_day') or '모름'}",
                f"KIND 결과 공시: {rec['result_title']} {rec['result_acptno']} · 주총일 {rec.get('agm_date')}",
                "", "<소집공고 회의목적사항 (원문 발췌)>", notice_agenda(notice_text(rc) or ""), "</소집공고 회의목적사항>", "",
                "<소집공고 '정관의 변경' 대비표 중 배당·기준일·주주명부가 든 행 (변경 전 | 변경 후 | 목적, 칸 구분이 없으면 ' / ')>",
                *(notice_amend_lines(rc) or ["(대비표 파일 없음)"]), "</대비표>", "",
                "<KIND 결과 공시의 안건 표 (번호 | 결의구분 | 회의목적사항 | 가결여부)>",
                *([f"{r['no']} | {r['kind']} | {r['item']} | {r['result']}" for r in rec.get("rows") or []] or ["(표 없음 — 아래 결과 글을 읽는다)"]),
                "</KIND 안건 표>", "", "<KIND 결과 공시 글 (발췌)>", rtxt[k:k + 2500], "</KIND 결과 공시 글>"]
        (d / "in" / f"{rc}.txt").write_text("\n".join(body), encoding="utf-8")
        items.append({"rc": rc, "code": rec["stock_code"], "name": rec["corp_name"], "result_acptno": rec["result_acptno"]})
    write_json(d / "packets.json", {"built_at": now_iso(), "items": items})
    print(f"서브에이전트 입력 {len(items)}건 → {d}")


def ingest(sfx: str) -> None:
    d = agent_dir(sfx)
    man = read_json(d / "packets.json")
    llm = load_llm(sfx)
    n, bad, missing = 0, [], []
    for it in man["items"]:
        f = d / "out" / f"{it['rc']}.json"
        if not f.exists():
            missing.append(it["rc"])
            continue
        try:
            import json as _json
            o = _json.loads(f.read_text(encoding="utf-8"))
        except ValueError as er:
            bad.append(f"{it['rc']} json {er}")
            continue
        err = [k for k, ty in LLM_KEYS.items() if k not in o or not isinstance(o[k], ty)] + [k for k in o if k not in LLM_KEYS]
        if err or not all(isinstance(x, str) for x in o["charter_rows"] + o["dividend_rows"]):
            bad.append(f"{it['rc']} 키 {err}")
            continue
        llm[it["rc"]] = {**o, "result_acptno": it["result_acptno"], "stock_code": it["code"], "corp_name": it["name"],
                         "runner": "claude-code-subagent", "model": "claude-opus-5-5", "at": now_iso()}
        n += 1
    write_json(llm_file(sfx), dict(sorted(llm.items())))
    out_f = interim_of(sfx, "s09e_agm_results.json")
    out = read_json(out_f)
    k = recompute(out)
    write_json(out_f, out)
    print(f"넣음 {n}건 · 형식 오류 {len(bad)} {bad[:10]} · 아직 없음 {len(missing)} {missing[:20]} · 다시 판정 {k}건")


def main():
    from krx_kind_data_api import fetch
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="fetch", choices=["fetch", "pack", "ingest"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--redo", action="store_true", help="결과를 못 고른 공고만 다시 받기 (고르기·판정은 끝에 캐시로 늘 다시 한다)")
    ap.add_argument("--sfx", default="", help="코스닥 등 다른 표 (s09a 와 같은 접미어)")
    a = ap.parse_args()
    if a.cmd == "pack":
        return pack(a.sfx)
    if a.cmd == "ingest":
        return ingest(a.sfx)
    load_llm(a.sfx)
    global OUT_F
    OUT_F = interim_of(a.sfx, "s09e_agm_results.json")
    out = read_json(OUT_F) if OUT_F.exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)

    for t in targets(a.sfx):
        rc = t["notice_rcept_no"]
        old = out.get(rc) or {}
        redo = a.redo and not old.get("result_acptno")
        if rc in out and old.get("result_acptno") and not a.force and not redo:
            continue
        if a.redo and rc in out and not redo:
            continue
        d0 = datetime.strptime(t["notice_dt"], "%Y%m%d")
        df = fetch("disclosure_details", repIsuSrtCd="A" + t["stock_code"], fromDate=d0.strftime("%Y-%m-%d"),
                   toDate=(d0 + timedelta(days=80)).strftime("%Y-%m-%d"))
        time.sleep(GAP)
        res = df[df["공시제목"].astype(str).str.contains("주주총회결과|주주총회 결과")].sort_values("시간") if len(df) else df
        rec = {**t, "fetched_at": now_iso()}
        if not len(res):
            rec.update(result_acptno=None, passed=None, note="공고 뒤 80일 안에 KIND 주주총회결과 공시 없음")
            out[rc] = rec
            write_json(OUT_F, out)
            print(f"{t['stock_code']} {t['corp_name']} {rc}: 결과 공시 없음")
            continue
        rec.update(choose(rc, [{"acptno": str(x["접수번호"]), "title": str(x["공시제목"]), "time": str(x["시간"])}
                               for _, x in res.iterrows()]))
        out[rc] = rec
        write_json(OUT_F, out)
        print(f"{t['stock_code']} {t['corp_name']} {rc} (주총 {rec['meeting_day']}) → {rec['result_title']} {rec['result_acptno']} · "
              f"정관 안건 {[(r['no'], r['item'][:30], r['result']) for r in rec['charter_rows']]} → {rec['note']}")
    k = recompute(out)
    write_json(OUT_F, out)
    print(f"{now_iso()} {len(out)}건 (저장된 안건 표로 다시 판정해 바뀐 것 {k}건) → {OUT_F}")


if __name__ == "__main__":
    main()
