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
     · 결과가 여럿이면(같은 날 정기주총 + 임시주총 등) 시간 순으로 읽어 안건 표에 정관 안건이 있는 첫 결과를 고른다.
       예전에는 첫 결과만 봐서 아센디오(정관 안건은 같은 날 임시주총)가 '정관 안건을 찾지 못함'이 됐다. 정관 안건이 든 결과가
       둘 이상이면 ambiguous=True (사람이 본다).
  ② disclosure_content_html(접수번호) → 【주주총회 안건 세부내역】 표의 행 {번호, 결의구분, 회의목적사항, 가결여부}
     중 회의목적사항에 '정관'이 든 행. 주주총회일자·의결권행사기준일도 읽는다.
  ③ 판정 passed: 배당·기준일이 든 세부 안건(없으면 정관 안건 전체)이 모두 가결 → True, 아니면 None(사람이 본다)
     · 결과 공시 없음 → None
출력  data/interim/s09e_agm_results.json  소집공고 접수번호 → {stock_code, corp_name, notice_dt, result_acptno, result_title,
                                          result_url, agm_date, record_date_vote, rows, charter_rows, passed, note}

사용법
  python -X utf8 scripts/s09e_agm_result_kind.py            # 결과가 없는 공고만
  python -X utf8 scripts/s09e_agm_result_kind.py --force    # 다시
  python -X utf8 scripts/s09e_agm_result_kind.py --redo     # 결과 없음 · 결과가 여럿이던 공고만 다시 (위 두 문제를 고친 뒤)
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


# 소집공고 원문에서 '정관 (일부) 변경' 안건 번호 — 결과 표가 정관 변경을 '제2-1호 사업목적 추가'·'2-2 상법 개정 반영의 건'처럼
# 제목에 '정관' 없는 세부 안건으로만 적으면(코스닥 폴라리스세원·네오위즈홀딩스 등 9사) 그 번호(2, 2-1, 2-2 …)로 짝짓는다.
# 원문: s09i = data/raw/opendart_doc_pre/{접수번호}.zip · s09f = data/raw/opendart_doc_prev/{접수번호}.zip · s09d = data/agm*/…/{날짜}_{접수번호}/{접수번호}.xml
NOTICE_AG = re.compile(r"제\s*(\d+)\s*호\s*의\s*안\s*[:：]?\s*[\[\(]?[^\n'\"’‘]{0,25}?정\s*관\s*(?:의\s*)?(?:일\s*부\s*)?(?:변\s*경|개\s*정)")
NOT_CHARTER = re.compile(r"(?:이사|감사|위원)\s+[가-힣]{2,4}\s*(?:\(?[가-힣]*\)?\s*)?(?:선임|해임|재선임)|보\s*수\s*한\s*도\s*(?:액\s*)?승\s*인|재\s*무\s*제\s*표.{0,30}승\s*인")   # 사람 선임·보수한도 승인·재무제표 승인 안건 (조문 제목 '감사위원의 분리선임·해임'은 아님)


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


_NOS: dict[str, set] = {}


def notice_charter_nos(rc: str) -> set[str]:
    if rc not in _NOS:
        t = notice_text(rc)
        _NOS[rc] = {m.group(1) for m in NOTICE_AG.finditer(t)} if t else set()
    return _NOS[rc]


def main_no(no: str) -> str | None:
    m = re.search(r"\d+", no or "")
    return m.group(0) if m else None


def judge_rows(rows: list[dict], rc: str) -> tuple[list[dict], list[dict]]:
    drow = [r for r in rows if re.search(r"배당|기준일", r["item"]) and not re.search(r"재무제표|이익잉여금|결손금", r["item"])
            and (KEEP.search(r["item"]) or not DIV_DECL.search(r["item"]))]
    # '정관 (일부) 변경·개정' 안건만 — '사내이사 신정관 해임의 건'처럼 사람 이름의 '정관'을 잡지 않게 (코스닥 아틀라스링크)
    # 제목에 '정관'이 든 안건 — 단 이사 선임·해임·보수 안건의 사람 이름('사내이사 신정관 해임의 건')은 빼고.
    # '정관 (일부) 변경의 건'·'개정상법 및 표준정관 반영'·'기타 정관 정비'·'정관 내용 변경의 건' 처럼 제목이 제각각이다.
    crow = drow or [r for r in rows if re.search(r"정\s*관", r["item"]) and not PERSON.search(r["item"])]
    if not crow and rc in MANUAL_ROWS:      # 정관 변경이 제목에 '정관' 없는 세부 안건으로만 나뉜 경우 (원문 대조로 지정)
        crow = [r for r in rows if r["no"] in MANUAL_ROWS[rc][0]]
    if not crow and rows:                   # 소집공고의 정관 변경 안건 번호로 (번호가 선임·보수·재무제표 안건에 걸리면 번호 체계가 다른 것 → 짝짓지 않음)
        nos = notice_charter_nos(rc)
        hit = [dict(r, via="notice_no") for r in rows if main_no(r["no"]) in nos]
        crow = [] if any(NOT_CHARTER.search(r["item"]) for r in hit) else hit
    return crow, drow


def verdict(crow: list[dict], drow: list[dict]) -> tuple[bool | None, str]:
    passed = True if crow and {r["result"] for r in crow} <= {"가결"} else None
    via = any(r.get("via") == "notice_no" for r in crow)
    note = ((f"배당 관련 세부 안건 {', '.join(r['no'] for r in drow)} 가결" if drow
             else f"정관 안건(소집공고 번호로 짝지은 세부 안건 {', '.join(r['no'] for r in crow)}) 모두 가결" if via else "정관 안건 모두 가결") if passed
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
        if not rec.get("result_acptno"):
            continue
        if (CACHE / f"{rec['result_acptno']}.html").exists():
            _, rows, crow, drow = read_result(rec["result_acptno"], rc)
            rec["rows"] = rows
        else:
            crow, drow = judge_rows(rec.get("rows") or [], rc)
        passed, note = verdict(crow, drow)
        if (passed, note) != (rec.get("passed"), rec.get("note")):
            print(f"  다시 판정 {rec['stock_code']} {rec['corp_name']} {rc}: {rec.get('note')} → {note}")
            n += 1
        rec.update(charter_rows=crow, by_dividend_row=bool(drow), passed=passed, note=note)
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


def main():
    from krx_kind_data_api import fetch
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--redo", action="store_true", help="결과 없음 · 결과가 여럿이던 공고만 다시")
    ap.add_argument("--sfx", default="", help="코스닥 등 다른 표 (s09a 와 같은 접미어)")
    a = ap.parse_args()
    global OUT_F
    OUT_F = interim_of(a.sfx, "s09e_agm_results.json")
    out = read_json(OUT_F) if OUT_F.exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)

    for t in targets(a.sfx):
        rc = t["notice_rcept_no"]
        old = out.get(rc) or {}
        redo = a.redo and (not old.get("result_acptno") or (old.get("n_results_in_window") or 0) > 1)
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
        # 결과가 여럿이면: 결과 공시의 '※ 관련공시'에 이 소집공고 날짜가 든 결과(그 공고의 주총)로 좁히고, 그중 정관 안건이
        # 든 첫 결과. 같은 날 정기 + 임시주총이면 둘 다 그 날 공고를 가리키므로 안건으로 가른다(아센디오).
        # 관련공시로 좁히지 않으면 1월 공고(2/4 임시주총)에 3월 정기주총 결과가 붙는다(코스닥 코맥스).
        reads = []
        for _, x in res.iterrows():
            reads.append((x, *read_result(str(x["접수번호"]), rc)))
            if len(res) == 1:
                break
        nd = f"{rc[:4]}-{rc[4:6]}-{rc[6:8]}"
        rel = [r for r in reads if nd in related_notice_dates(r[1])]
        cand = rel or reads
        with_c = [r for r in cand if r[3]]
        first, txt, rows, crow, drow = (with_c or cand)[0]
        acpt = str(first["접수번호"])
        m_date = re.search(r"주주총회\s*일자\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt)     # 임시주총 서식은 '주주총회 일자'
        m_rec = re.search(r"의결권행사기준일\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt)
        i = txt.find("정관상 기준일 설정 및 변경 세부내역")
        basis_box = txt[i:i + 400].split("\n※")[0] if i >= 0 else None     # 결과 공시의 '정관상 기준일' 표 (2025~ 서식)
        passed, note = verdict(crow, drow)
        rec.update(result_acptno=acpt, result_title=str(first["공시제목"]), result_time=str(first["시간"]),
                   result_url=KIND_VIEW.format(acpt), n_results_in_window=int(len(res)),
                   results_in_window=[{"acptno": str(r[0]["접수번호"]), "title": str(r[0]["공시제목"]), "time": str(r[0]["시간"]),
                                       "charter_rows": len(r[3]), "related_to_notice": nd in related_notice_dates(r[1])}
                                      for r in reads] if len(res) > 1 else None,
                   matched_by_related=bool(rel) if len(res) > 1 else None, ambiguous=len(with_c) > 1,
                   agm_date=m_date.group(1) if m_date else None, vote_record_date=m_rec.group(1) if m_rec else None,
                   rows=rows, charter_rows=crow, by_dividend_row=bool(drow), passed=passed, note=note,
                   basis_box=basis_box)
        out[rc] = rec
        write_json(OUT_F, out)
        print(f"{t['stock_code']} {t['corp_name']} {rc} → {first['공시제목']} {acpt} 주총 {rec['agm_date']} · "
              f"정관 안건 {[(r['no'], r['item'][:30], r['result']) for r in crow]} → {note}")
    k = recompute(out)
    write_json(OUT_F, out)
    print(f"{now_iso()} {len(out)}건 (저장된 안건 표로 다시 판정해 바뀐 것 {k}건) → {OUT_F}")


if __name__ == "__main__":
    main()
