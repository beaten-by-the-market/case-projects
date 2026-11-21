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
  compare 첨부 정관일 뒤 주총에서 이익배당 · 배당기준일 조를 바꾼 이력 행마다 그 주총의
          소집공고(공고 안 주총일이 이력 날짜와 같은 최종본, 그런 공고가 없으면 접수일 75일 전 ~ 당일)를 우리가 읽었는지 나눈다 → data/interim/s09k_compare.json
          · 읽음 = 공고 '정관의 변경' 절에 기준일 문구(s09c DIVAMEND)와 조 머리가 있다 (판별이 이미 봄)
          · 공고 없음 (아이엠바이오로직스 형 — 상장 전 소집 등) · 절 없음 (제이엔비 형 — 안건 이름만)
          · 대비표에 기준일 문구 없음 (삼진 형 — '첨부 대비표 참고'만, 또는 그림 대비표)
          '읽음' 이 아닌 행은 원문을 읽어 판정하고, 바뀌면 data/interim/s09m_other_basis.json 에 공시 근거와 함께,
          바꿀 필요 없으면 data/interim/s09k_reviewed.json 에 까닭을 적는다 (다음에 돌리면 '확인함').
  blank   공고 쪽 규칙 — 모든 소집공고 원문에서 '정관의 변경' 절이 대비표를 글로 싣지 않은 경우 → data/interim/s09k_blank.json
          · 첨부·참조만: 절에 조 머리(제N조)가 없고 '첨부 · 하단 · 참조 · 대비표' 문구만 (삼진 · 풍원정밀 '하 단 참 조')
          · 조 머리 없이 기준일 문구: 조 머리 없이 배당 · 기준일 · 주주명부 글만 (사업목적 목록만 바꾼 절은 뺀다)
          · 대비표 그림: 절 안 그림 이름에 정관 · 대비 · 신구 · 비교 · 변경 · 개정 (풍원정밀 정관_20260331_세로_1~8.jpg)
          반기보고서가 나오기 전에도 같은 경우를 잡기 위한 것. 그림은 DART 웹에서 받아 읽고, 결과를 s09k_reviewed.json
          (키 = 접수번호) 또는 s09m_other_basis.json 에 적는다. 사용자 지시(2026-11-21).
          사용자 지시(2026-11-21): 임시 스크립트로 돌린 대조를 저장소 단계로 옮긴다.

    python -X utf8 scripts/s09k_aoi_history.py list
    python -X utf8 scripts/s09k_aoi_history.py fetch      # 네트워크 — 다른 세션 DART · OpenDART 작업과 겹치지 않게
    python -X utf8 scripts/s09k_aoi_history.py scan
    python -X utf8 scripts/s09k_aoi_history.py compare
    python -X utf8 scripts/s09k_aoi_history.py blank      # 로컬 원문만 (네트워크 없음)
    python -X utf8 scripts/s09k_aoi_history.py origin     # 로컬 (네트워크 없음)
    python -X utf8 scripts/s09k_aoi_history.py prev       # 네트워크 — 다른 세션 DART 작업과 겹치지 않게, DART 웹 분당 75건

  prev    origin 후보 중 신고로 가려낼 수 없는 회사(첨부 정관 YorN · 신고 미입력 N)만 전년도(직전) 사업보고서 첨부 정관을 받아
          근거 조항을 지금 첨부 정관과 견준다 (사용자 지시 2026-11-21 "제안대로"). 정관은 data/charter_{시장}_prev/ (s04 폴더 규칙),
          스캔은 Windows OCR(s04b), PDF 는 글자층. 조항 글을 공백 · 기호 없이 비교한 유사도와 두 글을 s09k_prev.json 에 남기고,
          다른 회사만 원문으로 읽어 판정한다(바뀌면 s09m_other_basis.json, 아니면 s09k_reviewed.json 키 prev_{종목코드}).

  origin  메드팩토 형(주주총회 없이 바뀐 정관 첨부) 찾기 — 사용자 지시(2026-11-21) "소집공고 데이터로 잡을 수 있지 않나".
          첨부 정관이 N · YorN 인 회사마다 결산배당 근거 조(basis_article 첫 조 번호)를 그 문구로 만든 주총 근거를 찾는다.
          근거 = ① 첨부 정관일 전 소집공고 대비표에서 같은 조 번호 행이 기준일 · 배당 문구를 바꿈 ② 첨부 정관일 전 반기보고서
          이력 행이 같은 조 번호나 기준일 · 배당 낱말을 적음(동등배당 · 배당기산일 · 우선 · 분기 · 중간배당 낱말은 지우고 봄 —
          리가켐바이오 2023.03 '제17조(기준일) … 배당절차 개선') ③ 근거 조의 개정 표시 연도에 이력 · 공고상
          주총이 있음. 분기배당 조만 바꾼 공고(메드팩토 2025 제61조)는 조 번호가 달라 근거가 아니다.
          근거가 없으면 이력이 2023 전부터 있는지로 '후보'(이력은 긴데 그 조 개정이 없음)와 '이력 짧음'을 나눈다 → s09k_origin.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, INTERIM, ROOT, Http, dart_keys, now_iso, read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
REPORTS = INTERIM / "s09k_reports.json"
HIST = INTERIM / "s09k_history"
SCAN = INTERIM / "s09k_scan.json"
COMPARE = INTERIM / "s09k_compare.json"
BLANK = INTERIM / "s09k_blank.json"
TEXT_FOUND = INTERIM / "s09k_text_sections.json"
ORIGIN = INTERIM / "s09k_origin.json"
PREV = INTERIM / "s09k_prev.json"   # blank 이 함께 기록: 글로 찾은 절 (s06 text_fallback) — s10d '다른 항목에 기재' 유형
REVIEWED = INTERIM / "s09k_reviewed.json"        # '읽음'이 아닌 행을 원문으로 확인한 결과 (판정 바꿀 필요 없음)
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


def history_rows(code: str) -> list[tuple[str, str, str]]:
    """'정관 변경 이력' 표 → [(정관변경일 YYYYMMDD, 주요변경사항 · 변경이유 글, 원래 줄)].
    한 주총이 여러 줄로 이어지면 날짜는 첫 줄에만 있다(사조대림 2023.03.23 의 제44조(이익배당)는 둘째 줄) —
    날짜 없는 표 줄은 바로 위 날짜의 주총으로 잇는다. 표가 아닌 줄(' | ' 없음)에서 끊는다(뒤에 붙은 다른 표 · 재무표 방지)."""
    f = HIST / f"{code}.txt"
    out: list[list[str]] = []
    cont = False
    for ln in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
        cells = [c.strip() for c in ln.split(" | ")]
        m = ROW_DATE.search(cells[0]) if len(cells) >= 3 else None
        if m:
            out.append([f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}", " | ".join(cells[2:]), ln])
            cont = True
        elif cont and " | " in ln and "정관변경일" not in ln and not ROW_DATE.search(ln):
            out[-1][1] += " | " + " | ".join(cells)
            out[-1][2] += " / " + ln
        else:
            cont = False
    return [tuple(x) for x in out]


DIVROW = re.compile(r"이\s*익\s*배\s*당|배\s*당\s*기\s*준\s*일|결\s*산\s*배\s*당|배\s*당\s*을\s*받\s*을|이\s*익\s*의\s*배\s*당|배\s*당\s*금\s*의\s*지\s*급")
ART = re.compile(r"(?:제|第)\s*\d{1,3}\s*(?:조|條)")


def cmd_compare() -> None:
    from datetime import datetime, timedelta
    import s09i_pre_agm as I
    import s09e_agm_result_kind as E
    from s09c_dividend_build import DIVAMEND
    nl = I.notice_list()
    mdays: dict[str, list[str]] = {}

    def meeting_days(rc: str) -> list[str]:
        if rc not in mdays:
            try:
                mdays[rc] = [d.replace("-", "") for d in E.notice_meeting_days(rc)]
            except Exception:  # noqa: BLE001
                mdays[rc] = []
        return mdays[rc]
    rows = {}
    for sfx in ("", "kosdaq", "absent"):
        for r in read_json(X.paths(sfx)["out_json"]):
            rows[r["stock_code"]] = r
    secs = {p.parent.name.split("_", 1)[-1]: p for p in (ROOT / "data").glob("agm*/*/*/정관의변경.txt")}
    other = {k for k in read_json(INTERIM / "s09m_other_basis.json") if not k.startswith("_")}
    reviewed = {k: v for k, v in read_json(REVIEWED).items() if not k.startswith("_")} if REVIEWED.exists() else {}
    out = []
    for code, rep in read_json(REPORTS).items():
        for hi, body, ln in history_rows(code):
            if not DIVROW.search(body):                    # 주요변경사항 · 변경이유 칸 (이어지는 줄 포함)
                continue
            d = datetime(int(hi[:4]), int(hi[4:6]), int(hi[6:]))
            r = rows.get(code, {})
            att = r.get("charter_att_date") or ""
            if not att or hi <= att or hi > AS_OF.strftime("%Y%m%d"):
                continue                                   # 첨부 정관일 전 주총은 첨부 정관에 이미 들어 있다 (옛 판 첨부는 s09j)
            # 공고는 접수일이 아니라 공고 안에 적힌 주총일로 짝짓는다 — 최종본(기재정정)이 주총 뒤에 접수될 수 있다
            # (산일전기 20260326000400, 주총 2026-03-25). 같은 주총일 공고가 없으면 접수일 75일 창으로.
            lo = (d - timedelta(days=75)).strftime("%Y%m%d")
            ns = [n for n in nl.get(code, []) if hi in meeting_days(n["rcept_no"])]
            if not ns:
                ns = [n for n in nl.get(code, []) if lo <= n["rcept_dt"] <= hi]   # 주총일이 이력 날짜와 조금 다르게 적힌 공고 (한국전력공사 등)
            seen = [n["rcept_no"] for n in ns if n["rcept_no"] in secs]
            div = [rc for rc in seen for t in [secs[rc].read_text(encoding="utf-8")] if DIVAMEND.search(t) and ART.search(t)]
            done = (r.get("basis_agm_date") or "").replace("-", "") == hi or code in other
            status = "읽음" if div else "공고 없음" if not ns else "절 없음" if not seen else "대비표에 기준일 문구 없음"
            out.append({"stock_code": code, "corp_name": rep["corp_name"], "market": rep["market"], "amend_date": hi,
                        "status": status, "reflected": done, "reviewed": reviewed.get(f"{code}_{hi}"), "notices": [n["rcept_no"] for n in ns],
                        "tag": r.get("tag"), "tag_current": r.get("tag_current"), "basis_kind": r.get("basis_kind"),
                        "line": ln[:600]})
    write_json(COMPARE, out)
    from collections import Counter
    print(f"첨부 정관일 뒤 이익배당 · 기준일 개정 이력 {len(out)}행 · {dict(Counter(o['status'] for o in out))} → {COMPARE.name}")
    for o in out:
        if o["status"] != "읽음":
            print(f"  {o['status']:14s} {'반영됨' if o['reflected'] else '확인함' if o['reviewed'] else '확인 필요':6s} {o['market']} {o['stock_code']} {o['corp_name']} "
                  f"{o['amend_date']} | 지금 {o['tag_current']} ({o['basis_kind']})")


IMG_NAME = re.compile(r"정\s*관|대\s*비|신\s*구|비\s*교|변\s*경|개\s*정")


def cmd_blank() -> None:
    import s06_agm_xml as A
    import s09i_pre_agm as I
    owner = {n["rcept_no"]: c for c, ns in I.notice_list().items() for n in ns}
    rows = {}
    for sfx in ("", "kosdaq", "absent"):
        for r in read_json(X.paths(sfx)["out_json"]):
            rows[r["stock_code"]] = r
    reviewed = {k: v for k, v in read_json(REVIEWED).items() if not k.startswith("_")} if REVIEWED.exists() else {}
    srcs = [(f.stem, f) for d in ("opendart_doc_pre", "opendart_doc_early", "opendart_doc_prev") for f in (ROOT / "data/raw" / d).glob("*.zip")]
    srcs += [(f.stem, f) for f in (ROOT / "data").glob("agm*/*/*/*.xml")]
    seen, out, text_found = set(), [], []
    for rc, f in srcs:
        if rc in seen:
            continue
        seen.add(rc)
        try:
            if f.suffix == ".zip":
                with zipfile.ZipFile(f) as z:
                    raw = z.read(sorted(z.namelist(), key=len)[0])
            else:
                raw = f.read_bytes()
            root = A.parse(raw)[0]
        except Exception:  # noqa: BLE001
            continue
        secs, how = A.find_sections(root)
        if how == "text" and secs:                     # 서식 코드 · 제목 없이 글로 찾은 절 (다른 안건 항목 · 본문 별첨에 적은 공고)
            text_found.append({"rcept_no": rc, "stock_code": owner.get(rc) or "", "where_code": secs[0].get("WHERE_CODE") or "",
                               "where_title": (secs[0].get("WHERE_TITLE") or "").lstrip("□■ ").strip()})
        for sec in secs:
            text = re.sub(r"[\s/]+", "", " ".join(sec.itertext()))
            imgs = [x.get("SRC") or x.get("src") or x.get("FILE") or (x.text or "").strip() or " ".join(x.itertext()).strip()
                    for x in sec.iter() if isinstance(x.tag, str) and x.tag.upper() in ("IMG", "IMAGE")]
            tbl = [i for i in imgs if IMG_NAME.search(i)]
            no_art = not re.search(r"(?:제|第)\d{1,3}(?:조|條)", text)
            # 조 머리 없는 절 중 사업목적 목록만 바꾼 것은 빼고, 대비표를 다른 곳으로 미룬 문구나 기준일 문구가 있는 것만
            ref = no_art and re.search(r"첨부|별첨|하단|참조|참고하시기|대비표|대조표", text)
            div = no_art and re.search(r"배당|기준일|주주명부", text)
            if not (tbl or ref or div):
                continue
            code = owner.get(rc) or ""
            r = rows.get(code, {})
            out.append({"rcept_no": rc, "stock_code": code, "corp_name": r.get("corp_name"), "kind": "대비표 그림" if tbl else "첨부·참조만" if ref else "조 머리 없이 기준일 문구",
                        "images": tbl, "tag_current": r.get("tag_current"), "reviewed": reviewed.get(rc),
                        "tail": re.sub(r"\s+", " ", " ".join(sec.itertext()))[-160:]})
            break
    write_json(BLANK, out)
    write_json(TEXT_FOUND, text_found)
    print(f"서식 코드 · 제목 없이 글로 찾은 '정관의 변경' 절 {len(text_found)}건 → {TEXT_FOUND.name}")
    print(f"공고 {len(seen)} · '정관의 변경' 절이 대비표를 글로 싣지 않은 공고 {len(out)} → {BLANK.name}")
    for o in out:
        print(f"  {o['kind']:7s} {'확인함' if o['reviewed'] else '확인 필요':5s} {o['rcept_no']} {o['stock_code']} {o['corp_name']} 지금 {o['tag_current']} | "
              f"{(', '.join(o['images'][:2]) or o['tail'][-60:])}")


ORIGIN_WORD = re.compile(r"기\s*준\s*일|배\s*당\s*을\s*받\s*을|주\s*주\s*명\s*부|결\s*산\s*기\s*말|이\s*익\s*배\s*당|배\s*당\s*금")
HIST_WORD = re.compile(r"이\s*익\s*배\s*당(?!\s*에\s*관\s*한\s*우\s*선)|배\s*당\s*기\s*준\s*일|결\s*산\s*배\s*당|배\s*당\s*절\s*차|이\s*익\s*의\s*배\s*당|배\s*당\s*을\s*받\s*을")


# 결산배당과 무관한 배당 낱말 (동등배당 · 배당기산일 · 우선배당 · 분기 · 중간배당) — 지운 뒤 남은 '기준일 · 배당' 낱말만 근거로 본다
NOT_FINAL = re.compile(r"동\s*등\s*배\s*당|배\s*당\s*기\s*산\s*일|우\s*선\s*배\s*당|이\s*익\s*배\s*당\s*에\s*관\s*한\s*우\s*선\s*주\s*식|"
                       r"분\s*기\s*배\s*당[^|/]{0,40}|중\s*간\s*배\s*당[^|/]{0,40}|배\s*당\s*가\s*능\s*이\s*익|신\s*주\s*의\s*배\s*당")
REC_WORD = re.compile(r"기\s*준\s*일(?!\s*자)|배\s*당\s*절\s*차|결\s*산\s*배\s*당|이\s*익\s*배\s*당|이\s*익\s*의\s*배\s*당")


def _art_rx(n: str) -> re.Pattern:
    return re.compile(rf"(?:제|第)\s*{n}\s*(?:조|條)(?!\s*의)")


def cmd_origin() -> None:
    import s09i_pre_agm as I
    secs: dict[str, list[tuple[str, Path]]] = {}
    for p in (ROOT / "data").glob("agm*/*/*/정관의변경.txt"):
        code, rc = p.parent.parent.name.split("_")[0], p.parent.name.split("_", 1)[-1]
        secs.setdefault(code, []).append((rc, p))
    other = {k: v for k, v in read_json(INTERIM / "s09m_other_basis.json").items() if not k.startswith("_")}
    out, cnt = [], {}
    for sfx, mk in (("", "코스피"), ("kosdaq", "코스닥")):
        for r in read_json(X.paths(sfx)["out_json"]):
            if r.get("tag") not in ("정관no", "정관yesorno"):
                continue
            code, att = r["stock_code"], r.get("charter_att_date") or ""
            m = re.search(r"(?:제|第)\s*(\d{1,3})\s*(?:조|條)", r.get("basis_article") or "")
            rec = {"stock_code": code, "corp_name": r["corp_name"], "market": r.get("market") or mk, "tag": r["tag"],
                   "tag_current": r.get("tag_current"), "article": r.get("basis_article"), "amend_year": r.get("amend_year"),
                   "charter_att_date": att, "other_basis": code in other, "evidence": []}
            if re.search(r"스팩|기업인수목적", r["corp_name"]):
                rec["status"] = "스팩 (처음부터)"
            elif not m:
                rec["status"] = "근거 조 번호 없음"
            else:
                arx = _art_rx(m.group(1))
                for rc, p in secs.get(code, []):            # ① 첨부 정관일 전 공고 대비표의 같은 조 행
                    if att and rc[:8] > att:
                        continue
                    for ln in p.read_text(encoding="utf-8").splitlines():
                        head = " ".join(ln.split(" | ")[:2])[:80]
                        if (arx.search(head) or re.search(r"기\s*준\s*일|이\s*익\s*배\s*당", head[:40])) and ORIGIN_WORD.search(ln)                                 and not re.search(r"분\s*기\s*배\s*당|중\s*간\s*배\s*당", head[:40]):
                            rec["evidence"].append(f"공고 {rc} 같은 조 개정")
                            break
                hrows, years = [], set()
                for d, body, _ in history_rows(code):
                    hrows.append(d)
                    years.add(d[:4])
                    if att and d > att:
                        continue
                    if arx.search(body) or REC_WORD.search(NOT_FINAL.sub("", body)):
                        rec["evidence"].append(f"이력 {d} 기준일 · 배당 관련 개정")
                ay = str(r.get("amend_year") or "")
                if ay and (ay in years or any(rc[:4] == ay for rc, _ in secs.get(code, []))):
                    rec["evidence"].append(f"개정 표시 {ay}년에 주총 있음")
                rec["history_from"] = min(hrows) if hrows else None
                rec["status"] = ("근거 있음" if rec["evidence"] else "이력 없음" if not hrows
                                 else "후보 (이력은 긴데 그 조 개정 없음)" if min(hrows) < "20230101" else "이력 짧음 (2023 이후만)")
            cnt[rec["status"]] = cnt.get(rec["status"], 0) + 1
            out.append(rec)
    write_json(ORIGIN, out)
    print(f"첨부 정관 N · YorN {len(out)}사 · {cnt} → {ORIGIN.name}")
    for o in out:
        if o["status"].startswith("후보"):
            print(f"  후보 {o['market']} {o['stock_code']} {o['corp_name']} {o['tag']} {o['article']} | 개정 표시 {o['amend_year']} · 이력 {o['history_from']}~"
                  f"{' · 다른 공시로 판정' if o['other_basis'] else ''}")


ART_HEAD = re.compile(r"(?:^|\n)[ \t]*(?:제|第)\s*(\d{1,3})\s*(?:조|條)(\s*의\s*\d+)?\s*[\(\[【（<]")


def article_text(text: str, n: str) -> str:
    """정관 글에서 제n조(…) 머리부터 다음 조 머리 전까지 (스캔 · PDF 의 [이미지 …] · [쪽 n] 표시 줄은 지운다)."""
    t = re.sub(r"\[(?:이미지|쪽|PDF)[^\]]*\][^\n]*", "", text)
    heads = [(m.start(), m.group(1), bool(m.group(2))) for m in ART_HEAD.finditer(t)]   # '조의 N' 은 다른 조
    for i, (pos, num, sub) in enumerate(heads):
        if num == n and not sub:
            end = next((p for p, k, sb in heads[i + 1:] if k != n or sb), len(t))
            return t[pos:end].strip()[:2500]
    return ""


def _norm(s: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s)


def cmd_prev(codes: list[str] | None = None) -> None:
    import difflib
    import s04_charter as S4
    import s04b_charter_ocr as B
    from s09f_prev_charter import charter_att, fetch_pdf_text, od_list
    from concurrent.futures import ThreadPoolExecutor
    org = {o["stock_code"]: o for o in read_json(ORIGIN)}
    rows = {}
    for sfx in ("", "kosdaq"):
        for r in read_json(X.paths(sfx)["out_json"]):
            rows[r["stock_code"]] = (sfx, r)
    if not codes:                                      # 신고는 s10 이 붙인다 — site/dividend.js 에서 읽는다
        js = (ROOT / "site" / "dividend.js").read_text(encoding="utf-8")
        t = json.loads(js[js.index("{"):js.rindex("}") + 1])["tables"]["dividend"]
        filed = {x[t["cols"].index("stock_code")]: x[t["cols"].index("filed")] for x in t["rows"]}
        codes = [c for c, o in org.items() if o["status"].startswith("후보")
                 and (o["tag"] == "정관yesorno" or (o["tag"] == "정관no" and filed.get(c) not in ("Y", "N")))]
    old = read_json(PREV) if PREV.exists() else {}
    key = dart_keys()[0]
    od, web = Http(delay=0.7), Http(delay=0.8)          # DART 웹은 첨부 목록 · 정관 화면 · 이미지 모두 한 통로 (분당 75건 이하)
    ex = ThreadPoolExecutor(3)
    for code in codes:
        sfx, r = rows[code]
        if code in old and old[code].get("prev_article") is not None:
            continue
        S4.CHARTER = ROOT / "data" / (f"charter_{sfx}_prev" if sfx else "charter_prev")
        rec = {"stock_code": code, "corp_name": r["corp_name"], "market": r.get("market"), "tag": r["tag"],
               "article": r.get("basis_article"), "now_att_date": r.get("charter_att_date")}
        reps = sorted(od_list(od, key, r["corp_code"], "A001", "20220101"), key=lambda x: x["rcept_dt"], reverse=True)
        lim = (datetime.strptime(r["charter_att_date"], "%Y%m%d") - timedelta(days=200)).strftime("%Y%m%d")
        older = [x for x in reps if x["rcept_dt"] < lim and "사업보고서" in x["report_nm"]]
        for x in older[:2]:
            cands = charter_att(web, x["rcept_no"])
            if not cands:
                continue
            a = S4.pick(cands)
            doc = {"corp_code": r["corp_code"], "corp_name": r["corp_name"], "stock_code": code, "att_title": a["title"],
                   "att_date": a["att_date"], "rcpNo": a["rcpNo"], "dcmNo": a["dcmNo"], "att_url": a["url"]}
            m = S4.fetch_doc(web, web, doc)
            d = ROOT / m["folder"]
            if m["content_type"] == "pdf":
                fetch_pdf_text(web, d)
                full = d / "charter_pdf.txt"
            elif m["content_type"] in ("image", "mixed") and m["n_images"]:
                if not (d / "charter_ocr.txt").exists():
                    B.run_doc(ex, d, m, 3)
                full = d / "charter_ocr.txt"
            else:
                full = d / "charter.txt"
            rec.update(prev_rcept_no=x["rcept_no"], prev_report_nm=x["report_nm"], prev_att_date=a["att_date"],
                       prev_url=a["url"], prev_content_type=m["content_type"], prev_txt=full.relative_to(ROOT).as_posix())
            break
        n = re.search(r"(?:제|第)\s*(\d{1,3})\s*(?:조|條)", r.get("basis_article") or "")
        now_t = (ROOT / r["charter_fulltext_txt"]).read_text(encoding="utf-8") if r.get("charter_fulltext_txt") else ""
        prev_t = (ROOT / rec["prev_txt"]).read_text(encoding="utf-8") if rec.get("prev_txt") else ""
        rec["now_article"] = article_text(now_t, n.group(1)) if n else ""
        rec["prev_article"] = article_text(prev_t, n.group(1)) if n else ""
        a1, a2 = _norm(rec["prev_article"]), _norm(rec["now_article"])
        rec["similarity"] = round(difflib.SequenceMatcher(None, a1, a2).ratio(), 3) if a1 and a2 else None
        old[code] = rec
        write_json(PREV, old)
        print(f"{code} {r['corp_name']}: 전년도 {rec.get('prev_report_nm') or '없음'} {rec.get('prev_content_type') or ''} · 조항 유사도 {rec['similarity']}")
    ex.shutdown()
    print(f"{now_iso()} 끝 — {PREV.name} {len(old)}사")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "fetch", "scan", "compare", "blank", "origin", "prev"])
    ap.add_argument("--codes", default="", help="prev 대상 종목코드 (쉼표) — 없으면 origin 후보 중 YorN · 신고 미입력 N")
    a = ap.parse_args()
    if a.cmd == "prev":
        cmd_prev([c for c in a.codes.split(",") if c] or None)
    else:
        {"list": cmd_list, "fetch": cmd_fetch, "scan": cmd_scan, "compare": cmd_compare, "blank": cmd_blank, "origin": cmd_origin}[a.cmd]()
