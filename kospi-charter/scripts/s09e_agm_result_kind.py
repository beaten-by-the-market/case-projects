"""s09e 정관변경 안건이 실제로 가결됐나 — KIND 주주총회결과 공시 (krx-kind-data-api)

왜: 사용자 지시(2026-11-16) — 사업보고서 제출 뒤 '정관의 변경' 안건으로 결산배당 기준일이 바뀌는 회사는 주총결과를
    kind-api-data 로 받아 확인하고, 웹페이지 '분류근거의 종류'에 소집공고 URL 옆에 결과공시 URL 을 단다.

대상 소집공고
  · s09d 가 '결산배당 기준일 조항을 고친다'(changes_record_date)고 본 공고
  · s09f(확인필요 회사의 대체 자료)의 소집공고 중 '정관의 변경' 절이 있는 것
방법 (KIND, 분당 40요청 이하 — 요청 사이 1.6초)
  ① fetch("disclosure_details", repIsuSrtCd=종목코드, fromDate=공고 접수일, toDate=+80일) 에서 공시제목에 '주주총회결과'가
     든 첫 공시(공고 뒤 가장 먼저 나온 결과 = 그 주총). KIND 는 정정 공시를 최신본으로 보여 준다.
  ② disclosure_content_html(접수번호) → 【주주총회 안건 세부내역】 표의 행 {번호, 결의구분, 회의목적사항, 가결여부}
     중 회의목적사항에 '정관'이 든 행. 주주총회일자·의결권행사기준일도 읽는다.
  ③ 판정 passed: 배당·기준일이 든 세부 안건(없으면 정관 안건 전체)이 모두 가결 → True, 아니면 None(사람이 본다)
     · 결과 공시 없음 → None
출력  data/interim/s09e_agm_results.json  소집공고 접수번호 → {stock_code, corp_name, notice_dt, result_acptno, result_title,
                                          result_url, agm_date, record_date_vote, rows, charter_rows, passed, note}

사용법
  python -X utf8 scripts/s09e_agm_result_kind.py            # 결과가 없는 공고만
  python -X utf8 scripts/s09e_agm_result_kind.py --force    # 다시
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


def recompute(out: dict) -> int:
    """저장된 안건 표(rows)로 판정을 다시 계산한다 — 규칙을 고친 뒤 네트워크 없이 맞춘다. 바뀐 건수를 돌려준다."""
    n = 0
    for rc, rec in out.items():
        if not rec.get("result_acptno"):
            continue
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
    from krx_kind_data_api import disclosure_content_html, fetch
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sfx", default="", help="코스닥 등 다른 표 (s09a 와 같은 접미어)")
    a = ap.parse_args()
    global OUT_F
    OUT_F = interim_of(a.sfx, "s09e_agm_results.json")
    out = read_json(OUT_F) if OUT_F.exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for t in targets(a.sfx):
        rc = t["notice_rcept_no"]
        if rc in out and out[rc].get("result_acptno") and not a.force:
            continue
        d0 = datetime.strptime(t["notice_dt"], "%Y%m%d")
        df = fetch("disclosure_details", repIsuSrtCd=t["stock_code"], fromDate=d0.strftime("%Y-%m-%d"),
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
        first = res.iloc[0]
        acpt = str(first["접수번호"])
        f = CACHE / f"{acpt}.html"
        if not f.exists():
            f.write_text(disclosure_content_html(acpt), encoding="utf-8")
            time.sleep(GAP)
        h = f.read_text(encoding="utf-8")
        txt = html_text(h)
        rows = agenda_rows(h)
        if not rows:            # 옛 서식(2024년 등): '4. 기타 결의내용' 아래 '제2호 의안:정관 일부 변경의 건 ☞ 원안대로 승인'
            for m in re.finditer(r"(제\s*[\d\-]+\s*호)\s*의안\s*[:：]\s*([^\n]+)\n\s*☞\s*([^\n]+)", txt):
                res_t = m.group(3).strip()
                rows.append({"no": m.group(1), "kind": "", "item": m.group(2).strip(),
                             "result": "가결" if re.search(r"승인|가결", res_t) and "부결" not in res_t else res_t})
        crow, drow = judge_rows(rows, rc)
        m_date = re.search(r"주주총회일자\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt)
        m_rec = re.search(r"의결권행사기준일\s*\n?\s*(\d{4}-\d{2}-\d{2})", txt)
        i = txt.find("정관상 기준일 설정 및 변경 세부내역")
        basis_box = txt[i:i + 400].split("\n※")[0] if i >= 0 else None     # 결과 공시의 '정관상 기준일' 표 (2025~ 서식)
        passed, note = verdict(crow, drow)
        rec.update(result_acptno=acpt, result_title=str(first["공시제목"]), result_time=str(first["시간"]),
                   result_url=KIND_VIEW.format(acpt), n_results_in_window=int(len(res)),
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
