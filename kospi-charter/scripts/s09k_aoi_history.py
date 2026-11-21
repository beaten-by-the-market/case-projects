"""s09k 2026 반기보고서 '정관 변경 이력'으로 결산배당 기준일 판정 대조 (전 종목)

왜: 사용자 지시(2026-11-21) — 코스닥시장 담당자 메일로 소집공고로는 잡히지 않는 경우가 드러났다.
    · 삼진: 소집공고 '정관의 변경' 항목에 "첨부된 신·구조문 대비표 참고"라고만 적고 DART 에 첨부서류 없음
    · 아이엠바이오로직스: 상장 전 소집이라 DART 소집공고가 없음 (2026-03-31 정기주총)
    · 메드팩토: 주총 개정 없이 기준일 조항이 다른 정관을 사업보고서에 첨부
    반기 · 분기보고서 'I. 회사의 개요 › 정관에 관한 사항'의 '정관 변경 이력' 표(정관변경일 · 해당주총명 · 주요변경사항 · 변경이유)를
    전 종목에서 읽어, 이익배당 · 기준일 조를 바꾼 주총이 우리 판정에 반영됐는지 대조한다.

단계
  list    OpenDART list.json A002(반기보고서, 최종본) 2026-07-01 ~ 기준일 → data/interim/s09k_reports.json (대상 회사만)
  fetch   document.xml(요청 사이 0.8초) → '정관 변경 이력' 표만 data/interim/s09k_history/{종목코드}.txt (원문 zip 은 저장하지 않음)
  scan    이력 행 중 이익배당 · 배당 · 기준일 · 주주명부가 든 행 → 우리 판정(근거 공고 주총일 · 첨부 정관일)과 대조
          → data/interim/s09k_scan.json · 화면에 요약

    python -X utf8 scripts/s09k_aoi_history.py list
    python -X utf8 scripts/s09k_aoi_history.py fetch      # 네트워크 — 다른 세션 DART · OpenDART 작업과 겹치지 않게
    python -X utf8 scripts/s09k_aoi_history.py scan
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, INTERIM, Http, dart_keys, now_iso, read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
REPORTS = INTERIM / "s09k_reports.json"
HIST = INTERIM / "s09k_history"
SCAN = INTERIM / "s09k_scan.json"
GAP = 0.8
WINDOWS = [(date(2026, 7, 1), date(2026, 9, 30)), (date(2026, 10, 1), AS_OF)]
DIV = re.compile(r"이\s*익\s*배\s*당|배\s*당|기\s*준\s*일|주\s*주\s*명\s*부")


def targets() -> dict[str, dict]:
    out = {}
    for sfx, mk in (("", "코스피"), ("kosdaq", "코스닥"), ("absent", "")):
        for r in read_json(X.paths(sfx)["out_json"]):
            out[r["stock_code"]] = {"stock_code": r["stock_code"], "corp_name": r["corp_name"], "market": r.get("market") or mk}
    return out


def cmd_list() -> None:
    http, key = Http(delay=0.4), dart_keys()[0]
    tg = targets()
    found = {}
    for b, e in WINDOWS:
        page = 1
        while True:
            r = http.get(LIST_URL, params=dict(crtfc_key=key, bgn_de=b.strftime("%Y%m%d"), end_de=e.strftime("%Y%m%d"),
                                               pblntf_detail_ty="A002", last_reprt_at="Y", page_no=page, page_count=100)).json()
            for x in r.get("list") or []:
                c = x.get("stock_code") or ""
                if c in tg and "반기보고서" in x["report_nm"]:
                    found[c] = {**tg[c], "rcept_no": x["rcept_no"], "rcept_dt": x["rcept_dt"], "report_nm": x["report_nm"]}
            if page >= int(r.get("total_page") or 1):
                break
            page += 1
    write_json(REPORTS, found)
    print(f"{now_iso()} 반기보고서 {len(found)}사 / 대상 {len(tg)}사 → {REPORTS.name}")


def history_text(raw_zip: bytes) -> str:
    """원문에서 '정관 변경 이력' 표(다음 '다.' 또는 '사업목적' 전까지) — 표는 행마다 ' | '."""
    import s06_agm_xml as A
    out = []
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        for nm in sorted(z.namelist(), key=len):
            root, _ = A.parse(z.read(nm))
            bl = A._blocks(root)
            tx = [A.el_text(b).replace("\n", " ") for b in bl]
            i = next((k for k, t in enumerate(tx) if re.search(r"정\s*관\s*(?:의\s*)?변\s*경\s*이\s*력", t)), None)
            if i is None:
                continue
            # 끝: 제목 뒤 첫 표와 바로 이어지는 표까지 (표 뒤 다른 블록이 오면 멈춤 · 다음 절 머리에서도 멈춤)
            j, seen = min(len(bl), i + 12), False
            for k in range(i + 1, min(len(bl), i + 12)):
                is_t = bl[k].tag.upper() == "TABLE"
                if (seen and not is_t) or re.match(r"^\s*(?:다|라)\s*\.|사\s*업\s*목\s*적", tx[k]):
                    j = k
                    break
                seen = seen or is_t
            sec = A.etree.Element("S")
            import copy
            for b in bl[i:j]:
                sec.append(copy.deepcopy(b))
            out.append(A.section_text(sec))
            break
    return "\n".join(out)


def cmd_fetch() -> None:
    reps = read_json(REPORTS)
    HIST.mkdir(parents=True, exist_ok=True)
    od, key = Http(delay=GAP), dart_keys()[0]
    n_req = n_ok = n_fail = 0
    for code, r in reps.items():
        f = HIST / f"{code}.txt"
        if f.exists():
            continue
        body = None
        for k in range(10):
            try:
                body = od.get(DOC_URL, params=dict(crtfc_key=key, rcept_no=r["rcept_no"])).content
                break
            except RuntimeError as ex:
                print(f"  {now_iso()} {code} 받기 실패 {k + 1}/10: {type(ex).__name__}", flush=True)
                time.sleep(30)
        n_req += 1
        if not body or not body.startswith(b"PK"):
            n_fail += 1
            continue
        try:
            t = history_text(body)
        except Exception as ex:  # noqa: BLE001
            t = f"#ERROR {type(ex).__name__}: {ex}"
        f.write_text(t or "#NONE", encoding="utf-8")
        n_ok += 1
        if n_req % 100 == 0:
            print(f"  {now_iso()} 요청 {n_req}건", flush=True)
    print(f"{now_iso()} 요청 {n_req}건 · 이력 저장 {n_ok} · 못 받음 {n_fail} → {HIST.relative_to(INTERIM.parent.parent)}")


ROW_DATE = re.compile(r"(20\d\d)\s*[.\-년]\s*(\d{1,2})\s*[.\-월]\s*(\d{1,2})")


def cmd_scan() -> None:
    reps = read_json(REPORTS)
    rows = {}
    for sfx in ("", "kosdaq", "absent"):
        for r in read_json(X.paths(sfx)["out_json"]):
            rows[r["stock_code"]] = r
    out = []
    for code, rep in reps.items():
        f = HIST / f"{code}.txt"
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        r = rows.get(code) or {}
        att = r.get("charter_att_date") or ""
        for ln in t.splitlines():
            m = ROW_DATE.search(ln)
            if not m or not DIV.search(ln):
                continue
            d = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
            out.append({"stock_code": code, "corp_name": rep["corp_name"], "market": rep["market"], "amend_date": d,
                        "after_charter": bool(att) and d > att, "charter_att_date": att, "tag": r.get("tag"),
                        "tag_current": r.get("tag_current"), "basis_kind": r.get("basis_kind"),
                        "basis_agm_date": r.get("basis_agm_date"), "line": ln[:600]})
    write_json(SCAN, out)
    late = [o for o in out if o["after_charter"]]
    print(f"이력 행(배당 · 기준일 · 주주명부) {len(out)} · 그중 첨부 정관일 뒤 주총 {len(late)}행 / {len({o['stock_code'] for o in late})}사 → {SCAN.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "fetch", "scan"])
    a = ap.parse_args()
    {"list": cmd_list, "fetch": cmd_fetch, "scan": cmd_scan}[a.cmd]()
