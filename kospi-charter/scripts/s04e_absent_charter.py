"""s04e 사업보고서가 없어 목록에 없는 회사의 정관 — 증권신고서 · 분할공시(모회사) · 기타신고사항 · 홈페이지 (01 R8)

사용자 지시(2026-11-17): KIND 상장회사인데 조회기간에 사업보고서가 없어 정관 표에 들어오지 못한 회사 중 **신규상장·투자회사**는
증권신고서(또는 증권신고서 + 주총 소집공고)·홈페이지 등에서 정관을 찾아 지금 화면(근거문서 탭) 안에 넣는다.

대상 = data/final/kospi_absent.json ∪ kosdaq_absent.json 중 reason_code 가 new_listing · no_annual_report 인 회사
       (no_report_in_window — 예전엔 사업보고서를 냈던 회사, 예 피씨엘 — 은 이번 대상이 아니다)

근거문서 (charter_source_doc, 값 네 가지로 고정)
  증권신고서         조회기간 OpenDART 공시(최종본, s02b·s02c 캐시) 중 보고서명에 '증권신고서'가 든 것의 가장 늦은 접수번호.
                     지분증권 · 증권예탁증권(DR) · 합병(스팩합병 상장) 모두. 그 main.do 의 att 에서 R5-2 로 정관을 고른다
  분할공시(모회사)   인적분할 재상장 — 자기 증권신고서가 없다. 모회사의 분할 공시(att 에 신설회사 정관) — MANUAL 에 손으로
  기타신고사항       투자회사 — KIND '기타신고사항' 정관 개정 공지의 첨부 — MANUAL
  홈페이지           투자회사 — 회사 홈페이지에 게시한 정관 — MANUAL

정관 받기·글은 코스피 규칙 그대로(R5): s04_charter.fetch_doc · s04c(PDF) · s04b(OCR) · s04d(Opus) 를 저장 위치만 바꿔 쓴다(_kosdaq.patch).
소집공고(R6): 셈 기간 = [근거문서 원본 최초 접수일(family 의 가장 오래된 본문), 기준일]. E006 목록은 s05·s05k 가 받아 둔 시장 전체 캐시를 합쳐 쓴다.

저장   data/charter_absent/{종목코드}_{회사명}/{첨부일자}_{dcmNo}/   (data/charter/ 와 같은 구조)
       data/agm_absent/…                                          (data/agm/ 과 같은 구조)
중간   data/interim/absent/   s04e_plan.json · s03_main.json · s04_docs.json · s04b/c/d · s05·s06 (이름은 코스피와 같다)
결과   data/final/absent_charter.json · .csv   (1행 = 회사, 두 시장 함께)

하위 명령
  plan                      대상·근거문서 고르기 (네트워크 없음)
  fetch                     DART 근거문서 main.do → 정관 원문·이미지 (DART 웹, 분당 상한 --per-min, 기본 45)
  pdf | ocr                 PDF 정관 받기·글자 / Windows OCR
  llm pages|organize        스캔 쪽 전사 — Claude API 는 쓰지 않는다(사용자 지시 2026-11-17). pages 로 목록·JPEG 를 만들어
                            다른 세션 에이전트가 results.jsonl 에 전사를 넣으면 organize 로 charter_llm.txt 를 만든다
  agm                       소집공고 목록(캐시) · 원문(OpenDART document.xml)
  build                     결과물
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import re
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (AS_OF, FINAL, INTERIM, RAW, ROOT, Http, cached_text, dart_keys, main_url, now_iso,  # noqa: E402
                     parse_report_nm, read_json, write_json)
from _kosdaq import patch  # noqa: E402

A_INTERIM = INTERIM / "absent"
A_CHARTER = ROOT / "data" / "charter_absent"
A_AGM = ROOT / "data" / "agm_absent"
A_LLM = RAW / "llm_ocr_absent"
DOCS = ("증권신고서", "분할공시(모회사)", "기타신고사항", "홈페이지")
TARGET_REASONS = ("new_listing", "no_annual_report")
ABSENT = (("코스피", FINAL / "kospi_absent.json", RAW / "opendart_absent"),
          ("코스닥", FINAL / "kosdaq_absent.json", RAW / "opendart_absent_kosdaq"))

# 증권신고서가 없는 회사 — 출처를 확인해 손으로 적는다 (근거는 docs/03).
#   DART 문서: {"doc", "rcept_no"(그 공시 접수번호), "note"}
#   KIND·홈페이지: {"doc", "url"(파일 주소), "page"(공시·게시 화면 주소), "kind_acptno"(KIND), "dt"(YYYYMMDD), "nm", "note"}
MANUAL: dict[str, dict] = {
    # 인적분할 재상장 — 모회사의 회사분할결정 주요사항보고서 att '계약서(계획서)'(= 분할계획서)의 '[첨부3] 분할신설회사 정관(안)'
    # 쪽만 뽑는다(pages, 분할계획서 원문의 이미지 번호). 모회사의 분할 증권신고서 att '정관'은 모회사 자신의 정관이라 쓰지 않는다.
    # 모회사·쪽 범위는 OpenDART 목록과 분할계획서 OCR 로 확인(2026-11-17, docs/03)
    "0220W0": {"doc": "분할공시(모회사)", "rcept_no": "20260514000430", "nm": "[기재정정]주요사항보고서(회사분할결정) (㈜한화)",
               "dt": "20260514", "filer": "㈜한화 000880", "att_match": "계약서(계획서)", "pages": [24, 38],
               "part": "[첨부3] 분할신설회사의 정관(안)",
               "note": "KIND 재상장(인적분할) 20260821000488 · ㈜한화 증권신고서(분할) 20260604000183"},
    "0218L0": {"doc": "분할공시(모회사)", "rcept_no": "20260710000095", "nm": "[기재정정]주요사항보고서(회사분할결정) (토비스)",
               "dt": "20260710", "filer": "토비스 051360", "att_match": "계약서(계획서)", "pages": [19, 32],
               "part": "[첨부3] 분할신설회사 정관(안)",
               "note": "KIND 재상장 20260723000896 · 토비스 증권신고서(분할) 20260428000591 · "
                       "자율공시 '인적분할신설회사 (주)네오뷰의 주권재상장 예비심사 결과' 20260312902115"},
    # 투자회사: KIND 기타신고사항 'MKIF 정관 일부 개정'(2026-05-11)이 개정 정관을 홈페이지에 게시했다고 알린다 → 근거문서 = 기타신고사항,
    # 정관 파일 = 홈페이지 게시본(공시에 첨부가 없다). 사용자 지적(2026-11-17)으로 '홈페이지'에서 바꿈. 폴더는 처음 받은 {dt}_home 그대로(folder_tag)
    "088980": {"doc": "기타신고사항", "kind_acptno": "20260511000505", "folder_tag": "home",
               "url": "https://www.mkif.com/assets/mkif/ko-kr/investor-centre/public-filings-and-reports/2026/"
                      "mkif-articles-of-incorporation.pdf",
               "page": "https://www.mkif.com/ko/investor-centre/public-filings-and-reports.html",
               "nm": "기타신고사항 'MKIF 정관 일부 개정' (개정 정관은 MKIF 홈페이지 게시본)", "dt": "20260511",
               "note": "KIND 20260511000505 기타신고사항 'MKIF 정관 일부 개정': 개정된 정관을 MKIF 홈페이지에 게시했다고 알림. 정관 파일은 그 홈페이지 게시본"},
    # 투자회사 — KIND '기타신고사항' 정관 개정 공지의 '기타공시첨부서류'(문서 후보 둘째 content_id → searchContents 로 주소)
    "415640": {"doc": "기타신고사항", "kind_acptno": "20260225001757", "dt": "20260225",
               "url": "https://kind.krx.co.kr/external/2026/02/25/001757/20260225001091/"
                      "%EB%B0%9C%ED%95%B4%EC%9D%B8%ED%94%84%EB%9D%BC%20%EA%B0%9C%EC%A0%95%EC%A0%95%EA%B4%80_20260225.pdf",
               "referer": "https://kind.krx.co.kr/external/2026/02/25/001757/20260225001091/90999.htm",
               "file_name": "발해인프라 개정정관_20260225.pdf",
               "nm": "기타신고사항 '케이비발해인프라투융자회사 정관 일부 개정' 첨부 개정정관",
               "note": "KIND 20260225001757 첨부(content_id 20260225001091). 앞선 개정 공지 20251117000589"},
    "094800": {"doc": "기타신고사항", "kind_acptno": "20251230000116", "dt": "20251230",
               "url": "https://kind.krx.co.kr/external/2025/12/30/000116/20251230000287/"
                      "%EC%A0%95%EA%B4%80_%EB%AF%B8%EB%9E%98%EC%97%90%EC%85%8B%EB%A7%B5%EC%8A%A4%EB%A6%AC%EC%96%BC%ED%8B%B0"
                      "%EB%B6%80%EB%8F%99%EC%82%B0%EA%B3%B5%EB%AA%A8%ED%88%AC%EC%9E%90%ED%9A%8C%EC%82%AC_20251230.docx",
               "referer": "https://kind.krx.co.kr/external/2025/12/30/000116/20251230000287/90999.htm",
               "file_name": "정관_미래에셋맵스리얼티부동산공모투자회사_20251230.docx",
               "nm": "기타신고사항 '정관 변경 안내의 건' 첨부 정관",
               "note": "KIND 20251230000116 첨부(content_id 20251230000287): 정관(docx) · 정관변경 대비표 · 이사회의사록 중 정관"},
}


def docx_lines(path: Path) -> list[str]:
    """Word(.docx) 본문 → 줄 목록. 문단은 한 줄, 표는 행마다 칸을 ' | ' 로 (charter.txt 와 같은 꼴). 원문 순서대로."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(str(path))
    out = []
    for el in doc.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = " ".join(Paragraph(el, doc).text.replace("\xa0", " ").split())
            if t:
                out.append(t)
        elif tag == "tbl":
            for row in Table(el, doc).rows:
                cells = []
                for c in row.cells:
                    t = " ".join(c.text.replace("\xa0", " ").split())
                    if t and (not cells or cells[-1] != t):          # 가로 병합 칸은 같은 글이 되풀이된다
                        cells.append(t)
                if cells:
                    out.append(" | ".join(cells))
    return out
A_SRC = ROOT / "data" / "charter_absent_src"        # 정관을 뽑아낸 원문 전체(분할계획서 등) — 정관 폴더와 따로


def make_subset(src: dict, pages: list[int], part: str) -> dict:
    """원문 문서(meta)의 이미지 pages[0]~pages[1] 쪽만 정관 문서로 만든다 — data/charter_absent/…/{첨부일자}_{dcmNo}_p{a}-{b}/."""
    import shutil
    a, b = pages
    sd = ROOT / src["folder"]
    d = A_CHARTER / sd.parent.name / f"{sd.name}_p{a:03d}-{b:03d}"
    imgs = [im for im in src["images"] if a <= int(Path(im["file"]).stem) <= b]
    if len(imgs) != b - a + 1 or any("error" in im for im in imgs):
        raise SystemExit(f"{src['corp_name']} 쪽 {a}~{b} 이미지가 모자라거나 오류: {len(imgs)}장")
    (d / "img").mkdir(parents=True, exist_ok=True)
    new_imgs, lines = [], [f"{part} · {src['att_title']} 이미지 {a}~{b}쪽"]     # 화면에 나오므로 em dash 를 쓰지 않는다(사용자 지시)
    for k, im in enumerate(imgs, 1):
        rel = f"img/{k:03d}{Path(im['file']).suffix}"
        shutil.copyfile(sd / im["file"], d / rel)
        new_imgs.append({**im, "file": rel, "src_page": int(Path(im["file"]).stem)})
        lines.append(f"[이미지 {k:03d}: 원문 {int(Path(im['file']).stem)}쪽] → {rel}")
    (d / "charter.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {k: src[k] for k in ("corp_code", "corp_name", "stock_code", "att_title", "att_date", "rcpNo", "dcmNo", "att_url",
                                "viewer_urls")}
    meta.update(n_nodes=src.get("n_nodes"), content_type="image", text_chars=0, n_images=len(new_imgs),
                n_image_errors=0, images=new_imgs, folder=d.relative_to(ROOT).as_posix(), fetched_at=src.get("fetched_at"),
                subset_of=src["folder"], subset_pages=[a, b], subset_part=part)
    write_json(d / "meta.json", meta)
    return meta


def plan_path() -> Path:
    return A_INTERIM / "s04e_plan.json"


# ── plan ────────────────────────────────────────────────────────────────────
def window_filings(raw: Path, corp_code: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(raw / f"{corp_code}_all_Y_p*.json"))):
        rows += read_json(Path(f)).get("list", [])
    return sorted(rows, key=lambda r: r["rcept_no"])


def cmd_plan():
    out = []
    for market, absf, raw in ABSENT:
        for a in read_json(absf):
            if a.get("reason_code") not in TARGET_REASONS:
                continue
            rec = {"market": market, **{k: a.get(k) for k in ("stock_code", "corp_name", "corp_code", "sec_group",
                                                              "listed_date", "acc_mt", "reason_code", "reason")}}
            reg = [r for r in window_filings(raw, a["corp_code"]) if "증권신고서" in r["report_nm"]] if a.get("corp_code") else []
            m = MANUAL.get(a["stock_code"])
            if m:
                rec.update(source_doc=m["doc"], source=m, plan_status="manual")
            elif reg:
                r = reg[-1]
                rec.update(source_doc="증권신고서", plan_status="auto",
                           source={"rcept_no": r["rcept_no"], "nm": r["report_nm"].strip(), "dt": r["rcept_dt"],
                                   "filer": r["flr_nm"], "n_reg": len(reg)})
            else:
                rec.update(source_doc=None, source=None, plan_status="pending")
            out.append(rec)
    write_json(plan_path(), out)
    print(f"대상 {len(out)}사 · {dict(Counter((r['market'], r['plan_status'], r['source_doc']) for r in out))}")
    for r in out:
        if r["plan_status"] == "pending":
            print(f"  출처 미정: {r['market']} {r['stock_code']} {r['corp_name']} [{r['sec_group']}] 상장 {r['listed_date']}")
    return out


# ── fetch (KIND·홈페이지 파일) ──────────────────────────────────────────────
def fetch_file(p: dict, src: dict, http: Http) -> dict:
    """KIND 첨부·홈페이지 PDF → data/charter_absent/{종목코드}_{회사명}/{날짜}_{kind|home}/ (pdf/001.pdf · charter_pdf.txt ·
    pdf.json · charter.txt · meta.json). 글은 s04c.extract 그대로(글자층, 글자 30자 미만 쪽만 Windows OCR)."""
    import importlib
    from urllib.parse import unquote, urlparse

    import s04c_charter_pdf as s4c
    from _common import safe_name
    from s04ck_kosdaq_pdf import CTRL

    tag = src.get("folder_tag") or ("home" if p["source_doc"] == "홈페이지" else "kind")   # 폴더 꼬리 (MANUAL 의 folder_tag 가 있으면 그것)
    d = A_CHARTER / f"{p['stock_code']}_{safe_name(p['corp_name'])}" / f"{src['dt']}_{tag}"
    if (d / "meta.json").exists():
        return read_json(d / "meta.json")
    fl0 = src.get("file_name") or unquote(Path(urlparse(src["url"]).path).name)
    if fl0.lower().endswith(".docx"):                                  # Word 정관 → 텍스트 정관(text)
        f = d / "doc" / "001.docx"
        if not (f.exists() and f.read_bytes()[:2] == b"PK"):
            if src.get("referer"):
                http.s.headers["Referer"] = src["referer"]
            r = http.get(src["url"])
            if r.content[:2] != b"PK":
                raise RuntimeError(f"docx 아님 ({r.headers.get('Content-Type')}, {len(r.content)}B)")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(r.content)
        b = f.read_bytes()
        lines = docx_lines(f)
        (d / "charter.txt").write_text(CTRL.sub("", "\n".join(lines) + "\n"), encoding="utf-8")
        chars = len(re.sub(r"\s", "", "".join(lines).replace("|", "")))
        meta = {"corp_code": p["corp_code"], "corp_name": p["corp_name"], "stock_code": p["stock_code"], "att_title": src["nm"],
                "att_date": src["dt"], "rcpNo": src.get("kind_acptno"), "dcmNo": None, "att_url": src["url"],
                "viewer_urls": [src.get("referer") or src.get("page")], "n_nodes": 0,
                "content_type": "text" if chars >= 200 else "empty", "text_chars": chars, "n_images": 0, "n_image_errors": 0,
                "images": [], "docs": [{"file": "doc/001.docx", "src_url": src["url"], "flNm": fl0, "bytes": len(b),
                                        "sha256": hashlib.sha256(b).hexdigest()}],
                "folder": d.relative_to(ROOT).as_posix(), "fetched_at": now_iso(), "source_doc": p["source_doc"],
                "source_note": src.get("note"), "text_from": "docx (python-docx 문단·표)"}
        write_json(d / "meta.json", meta)
        return meta
    pdf = d / "pdf" / "001.pdf"
    if not (pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"):
        if src.get("referer"):
            http.s.headers["Referer"] = src["referer"]
        r = http.get(src["url"])
        if r.content[:4] != b"%PDF":
            raise RuntimeError(f"PDF 아님 ({r.headers.get('Content-Type')}, {len(r.content)}B)")
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(r.content)
    b = pdf.read_bytes()
    fl = src.get("file_name") or unquote(Path(urlparse(src["url"]).path).name)
    pages, summ = s4c.extract(pdf, RAW / "pdf_pages" / f"{p['stock_code']}_{d.name}", importlib.import_module("s04b_charter_ocr"))
    lines = [f"[PDF 001: {fl}] → pdf/001.pdf"]
    for pg in pages:
        lines.append(f"[쪽 {pg['n']}{' · OCR' if pg['ocr'] else ''}]")
        lines += pg["lines"]
    body = CTRL.sub("", "\n".join(lines) + "\n")                            # 01 R7-8
    (d / "charter_pdf.txt").write_text(body, encoding="utf-8")
    (d / "charter.txt").write_text(lines[0] + "\n", encoding="utf-8")
    chars = len(re.sub(r"\s", "", "\n".join(x for x in body.splitlines() if not x.startswith("["))))
    rec = {"file": "pdf/001.pdf", "src_url": src["url"], "flNm": fl, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
           **summ}
    write_json(d / "pdf.json", {"pdfs": [rec], "total_chars": chars, **{k: summ[k] for k in ("pages", "text_pages", "ocr_pages")},
                                "created_at": now_iso(), "engine": {"text": "PyMuPDF (s04c.extract)",
                                                                    "ocr": "Windows.Media.Ocr ko" if summ["ocr_pages"] else None}})
    meta = {"corp_code": p["corp_code"], "corp_name": p["corp_name"], "stock_code": p["stock_code"], "att_title": src["nm"],
            "att_date": src["dt"], "rcpNo": src.get("kind_acptno"), "dcmNo": None, "att_url": src["url"],
            "viewer_urls": [src.get("page")], "n_nodes": 0, "content_type": "pdf", "text_chars": 0, "n_images": 0,
            "n_image_errors": 0, "images": [], "pdfs": [rec], "n_pdfs": 1, "folder": d.relative_to(ROOT).as_posix(),
            "fetched_at": now_iso(), "source_doc": p["source_doc"], "source_note": src.get("note")}
    write_json(d / "meta.json", meta)
    idx_f = A_INTERIM / "s04c_pdf.json"
    idx = read_json(idx_f) if idx_f.exists() else {}
    idx[meta["folder"]] = {"pdf_txt": f"{meta['folder']}/charter_pdf.txt", "total_chars": chars, "n_pdfs": 1,
                           "pages": summ["pages"], "ocr_pages": summ["ocr_pages"]}
    write_json(idx_f, idx)
    return meta


# ── fetch (DART) ────────────────────────────────────────────────────────────
def cmd_fetch(per_min: int):
    import s04_charter as s4
    from s03k_kosdaq_main import page_record

    patch(s4, CHARTER=A_CHARTER)
    Http.PER_MIN = {**Http.PER_MIN, "dart.fss.or.kr": per_min, "opendart.fss.or.kr": per_min}   # 이 프로세스만
    plan = read_json(plan_path())
    http, img_http = Http(delay=1.0), Http(delay=0.5)
    pages_f, docs_f = A_INTERIM / "s03_main.json", A_INTERIM / "s04_docs.json"
    pages = read_json(pages_f) if pages_f.exists() else {}
    docs = read_json(docs_f) if docs_f.exists() else {}
    names = Counter()
    for p in plan:
        src = p.get("source") or {}
        rno = src.get("rcept_no")
        if p["source_doc"] in ("기타신고사항", "홈페이지") and src.get("url"):
            try:
                m = fetch_file(p, src, Http(delay=2.0))
            except RuntimeError as e:
                p["charter_status"] = "download_failed"
                print(f"  파일 받기 실패 {p['corp_name']}: {e}", flush=True)
                continue
            key = f"{p['stock_code']}_{Path(m['folder']).name}"
            m["used_by_stock_code"] = [p["stock_code"]]
            write_json(ROOT / m["folder"] / "meta.json", m)
            docs[key] = m
            p.update(charter_status="ok", doc_key=key, charter_title=src["nm"], charter_url=src["url"], n_charter_att=1)
            print(f"  {p['market']} {p['corp_name']} {p['source_doc']} → {src['nm']} · {m['content_type']} "
                  f"글자 {m.get('text_chars')}", flush=True)
            continue
        if p["source_doc"] not in ("증권신고서", "분할공시(모회사)") or not rno:
            continue
        f = RAW / "dart_main" / f"{rno}.html"
        try:
            html = cached_text(f, lambda: http.get(main_url(rno)).text)
        except RuntimeError as e:
            print(f"  화면 실패 {rno} {p['corp_name']}: {e}", flush=True)
            continue
        pg = page_record(rno, "", html, f)
        pages[rno] = pg
        cands = []
        for i, a in enumerate(pg["att"]):
            a = dict(a, att_order=i, **s4.parse_att_title(a["title"]))
            names[a["att_name"]] += 1
            if (src["att_match"] in a["att_name"]) if src.get("att_match") else s4.is_charter(a["att_name"]):
                cands.append(a)
        p["n_att"], p["n_charter_att"] = len(pg["att"]), len(cands)
        if not cands:
            p["charter_status"] = "no_charter_attachment"
            print(f"  정관 첨부 없음: {p['corp_name']} {rno} 첨부 {[a['title'] for a in pg['att']][:8]}", flush=True)
            continue
        a = s4.pick(cands)
        doc = {"corp_code": p["corp_code"], "corp_name": p["corp_name"], "stock_code": p["stock_code"],
               "att_title": a["title"], "att_date": a["att_date"], "rcpNo": a["rcpNo"], "dcmNo": a["dcmNo"],
               "att_url": a["url"]}
        try:
            if src.get("att_match"):                       # 분할계획서 등 → 원문은 A_SRC, 정관 쪽만 A_CHARTER
                patch(s4, CHARTER=A_SRC)
                m = make_subset(s4.fetch_doc(http, img_http, doc), src["pages"], src["part"])
                patch(s4, CHARTER=A_CHARTER)
            else:
                m = s4.fetch_doc(http, img_http, doc)
        except RuntimeError as e:
            patch(s4, CHARTER=A_CHARTER)
            p["charter_status"] = "download_failed"
            print(f"  정관 받기 실패 {p['corp_name']}: {e}", flush=True)
            continue
        key = f"{a['rcpNo']}_{a['dcmNo']}" + (f"_p{src['pages'][0]}-{src['pages'][1]}" if src.get("pages") else "")
        m["used_by_stock_code"] = [p["stock_code"]]
        write_json(ROOT / m["folder"] / "meta.json", m)
        docs[key] = m
        title = a["title"] + (f" {src['part']} ({src['pages'][0]}~{src['pages'][1]}쪽)" if src.get("pages") else "")
        p.update(charter_status="ok", doc_key=key, charter_title=title, charter_url=a["url"])
        print(f"  {p['market']} {p['corp_name']} {p['source_doc']} {rno} → {a['title']} · {m['content_type']} img={m['n_images']}",
              flush=True)
    write_json(pages_f, pages)
    write_json(docs_f, docs)
    write_json(plan_path(), plan)
    print("첨부 이름 상위:", names.most_common(12))
    print("정관:", dict(Counter(p.get("charter_status", "-") for p in plan)),
          "· 종류", dict(Counter(m["content_type"] for m in docs.values())))


# ── pdf · ocr · llm ─────────────────────────────────────────────────────────
def cmd_pdf(force: bool, per_min: int):
    import s04c_charter_pdf as s4c
    from s04ck_kosdaq_pdf import CTRL

    patch(s4c, CHARTER=A_CHARTER, INTERIM=A_INTERIM)
    Http.PER_MIN = {**Http.PER_MIN, "dart.fss.or.kr": per_min}
    s4c.main(force, 0)
    for tf in A_CHARTER.glob("*/*/charter_pdf.txt"):              # 01 R7-8 과 같은 정리
        t = tf.read_text(encoding="utf-8")
        if CTRL.search(t):
            tf.write_text(CTRL.sub("", t), encoding="utf-8")
            print(f"  제어문자 지움 {tf.parent.relative_to(ROOT).as_posix()}")


def cmd_ocr():
    import s04b_charter_ocr as s4b
    patch(s4b, CHARTER=A_CHARTER, INTERIM=A_INTERIM)
    s4b.main(0, False, 3)


def cmd_llm(sub: str, n: int):
    """스캔 쪽 전사 — 사용자 지시(2026-11-17): Claude API 는 쓰지 않는다. 전사는 다른 세션의 에이전트가 한다.

    pages     s04d 와 같은 규칙으로 대상 쪽 목록(custom_id → 쪽)과 보낼 JPEG(회색조·긴 변 2,576px)를 만든다. API 호출 없음.
              → data/interim/absent/s04d_pages.json · data/interim/absent/llm_pages_todo.json(절대 경로 목록)
    organize  data/raw/llm_ocr_absent/results.jsonl (s04d 와 같은 한 줄 형식 {custom_id, ok, text, stop_reason, source, at})
              을 읽어 문서마다 charter_llm.txt · llm_ocr.json · s04d_llm.json 을 만든다 (s04d.organize 그대로)
    """
    import s04d_charter_llm_ocr as s4d
    patch(s4d, CHARTER=A_CHARTER, INTERIM=A_INTERIM, LLM=A_LLM, PAGES_F=A_INTERIM / "s04d_pages.json",
          BATCHES_F=A_INTERIM / "s04d_batches.json", RESULTS_F=A_LLM / "results.jsonl", INDEX_F=A_INTERIM / "s04d_llm.json")
    if sub == "pages":
        # 요청 ID 를 폴더·파일·쪽에서 만든 고정 값으로 — s04d 의 p00001… 은 폴더 순서라 문서가 더해지면 밀린다(넘긴 쪽과 어긋남)
        pages = read_json(s4d.PAGES_F) if s4d.PAGES_F.exists() else {}
        for it in s4d.build_pages().values():
            cid = "a" + hashlib.md5(f"{it['folder']}|{it['file']}|{it.get('page') or ''}".encode()).hexdigest()[:12]
            pages.setdefault(cid, it)
        live = {it["folder"] for it in s4d.build_pages().values()}
        pages = {c: it for c, it in pages.items() if it["folder"] in live}       # 지운 문서의 쪽은 뺀다
        write_json(s4d.PAGES_F, pages)
        done = {k for k, r in s4d.load_results().items() if r.get("ok")}
        todo = []
        for cid, it in pages.items():
            if cid in done:
                continue
            s4d.prepared_jpeg(cid, it)                             # 로컬에서 줄인 JPEG 만 만든다
            todo.append({"custom_id": cid, "image": str((A_LLM / "img" / f"{cid}.jpg").resolve()), **it})
        write_json(A_INTERIM / "llm_pages_todo.json", {"prompt_system": s4d.SYSTEM, "prompt": s4d.PROMPT,
                                                        "results_jsonl": str(s4d.RESULTS_F.resolve()), "pages": todo})
        print(f"쪽 {len(pages)} · 끝남 {len(done)} · 전사할 쪽 {len(todo)} → {A_INTERIM / 'llm_pages_todo.json'}")
    elif sub == "organize":
        s4d.organize()
    else:
        raise SystemExit("Claude API 는 쓰지 않는다(사용자 지시 2026-11-17) — llm pages | llm organize 만")


# ── agm ─────────────────────────────────────────────────────────────────────
def cached_e006() -> list[dict]:
    """s05·s05k 가 받아 둔 E006(최종본) 시장 전체 페이지를 합친다 — 접수번호 한 번씩."""
    seen, rows, spans = set(), [], []
    for f in sorted((RAW / "opendart_list").glob("E006_Y_*_p*.json")):
        m = re.match(r"E006_Y_(\d{8})_(\d{8})_p\d+", f.stem)
        spans.append((m[1], m[2]))
        for r in read_json(f).get("list", []):
            if r["rcept_no"] not in seen:
                seen.add(r["rcept_no"])
                rows.append(r)
    return rows, sorted(set(spans))


def cmd_agm():
    import s06_agm_xml as s6
    from s01_list import API_COLS

    patch(s6, AGM=A_AGM)
    plan = read_json(plan_path())
    pages = read_json(A_INTERIM / "s03_main.json")
    allrows, spans = cached_e006()
    cover = min(s for s, _ in spans)
    starts = []                                                        # 근거문서 원본 접수일 — 캐시보다 이르면 그 구간만 더 받는다
    for p in plan:
        src = p.get("source") or {}
        if p.get("charter_status") == "ok" and src.get("rcept_no") in pages:
            starts.append(min([f["rcpNo"] for f in pages[src["rcept_no"]].get("family", [])] + [src["rcept_no"]])[:8])
    if starts and min(starts) < cover:
        from datetime import timedelta

        from s05_agm_list import fetch as e006_fetch
        b = date(int(min(starts)[:4]), int(min(starts)[4:6]), int(min(starts)[6:]))
        e = date(int(cover[:4]), int(cover[4:6]), int(cover[6:])) - timedelta(days=1)
        print(f"E006 캐시({cover} ~) 앞 구간 {b} ~ {e} 를 더 받는다", flush=True)
        seen = {r["rcept_no"] for r in allrows}
        allrows += [r for r in e006_fetch(Http(delay=0.35), dart_keys(), b, e) if r["rcept_no"] not in seen]
        cover = f"{b:%Y%m%d}"
    by_corp = {}
    for x in allrows:
        by_corp.setdefault(x["corp_code"], []).append(x)
    notices, amap = {}, {}
    for p in plan:
        src = p.get("source") or {}
        if p.get("charter_status") != "ok":
            continue
        if src.get("rcept_no") and src["rcept_no"] in pages:          # DART 근거문서: family 의 가장 오래된 본문
            fam = [f["rcpNo"] for f in pages[src["rcept_no"]].get("family", [])]
            orig = min(fam + [src["rcept_no"]])
            o_dt = orig[:8]
        else:                                                          # KIND·홈페이지: 그 공시·게시일
            orig, o_dt = src.get("kind_acptno") or "", src.get("dt") or ""
        if o_dt and o_dt < cover:
            raise SystemExit(f"E006 캐시가 {cover} 부터라 {p['corp_name']} 기간 시작 {o_dt} 를 덮지 못한다 — s05 로 더 받아야 한다")
        ns = sorted((n for n in by_corp.get(p["corp_code"], []) if o_dt and o_dt <= n["rcept_dt"] <= f"{AS_OF:%Y%m%d}"),
                    key=lambda n: n["rcept_no"])
        for n in ns:
            notices[n["rcept_no"]] = {**{c: n.get(c, "") for c in API_COLS},
                                      "amend_tag": parse_report_nm(n["report_nm"])["amend_tag"], "stock_code_": p["stock_code"]}
        amap[p["stock_code"]] = {"orig_rcept_no": orig, "orig_rcept_dt": o_dt, "notices": [n["rcept_no"] for n in ns]}
    write_json(A_INTERIM / "s05_agm_notices.json", sorted(notices.values(), key=lambda n: n["rcept_no"]))
    write_json(A_INTERIM / "s05_agm_map.json", amap)
    print(f"E006 캐시 {len(allrows):,}건({cover} ~) → 대상 회사 기간 안 {len(notices)}건 · 회사별 "
          f"{dict(sorted(Counter(len(v['notices']) for v in amap.values()).items()))}")

    out_f = A_INTERIM / "s06_agm_docs.json"
    out = read_json(out_f) if out_f.exists() else {}
    http, keys, ki = Http(delay=0.5, timeout=120), dart_keys(), 0
    for rno, n in sorted(notices.items()):
        d = s6.notice_dir(n, n["stock_code_"])
        meta_f = d / "meta.json"
        if meta_f.exists():
            out[rno] = read_json(meta_f)
            continue
        d.mkdir(parents=True, exist_ok=True)
        files = sorted(d.glob("*.xml"))
        if not files:
            while True:
                r = http.get(s6.DOC_URL, params={"crtfc_key": keys[ki], "rcept_no": rno})
                if r.content[:2] == b"PK":
                    break
                st = re.search(rb"<status>(\d+)</status>", r.content)
                st = st.group(1).decode() if st else "?"
                if st == "020" and ki + 1 < len(keys):
                    ki += 1
                    continue
                break
            if r.content[:2] != b"PK":
                meta = {"rcept_no": rno, "error": f"document.xml status {st}", "folder": d.relative_to(ROOT).as_posix()}
                write_json(meta_f, meta)
                out[rno] = meta
                print(f"  원문 없음 {rno} {n['corp_name']} ({st})", flush=True)
                continue
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            for name in zf.namelist():
                (d / Path(name).name).write_bytes(zf.read(name))
            files = sorted(d.glob("*.xml"))
        main_f = next((f for f in files if f.stem == rno), max(files, key=lambda f: f.stat().st_size))
        root, enc = s6.parse(main_f.read_bytes())
        secs, how = s6.find_sections(root)
        if not secs and len(files) > 1:
            for f in files:
                if f != main_f:
                    secs, how = s6.find_sections(s6.parse(f.read_bytes())[0])
                    if secs:
                        how += f"@{f.name}"
                        break
        txt_rel, chars = None, 0
        if secs:
            body = "\n\n".join(s6.section_text(s) for s in secs)
            chars = len(re.sub(r"\s", "", body))
            (d / "정관의변경.txt").write_text(body, encoding="utf-8")
            txt_rel = (d / "정관의변경.txt").relative_to(ROOT).as_posix()
        meta = {"rcept_no": rno, "corp_code": n["corp_code"], "corp_name": n["corp_name"], "stock_code": n["stock_code_"],
                "report_nm": n["report_nm"], "rcept_dt": n["rcept_dt"], "dart_url": main_url(rno),
                "agm_kind": s6.agm_kind(root), "has_charter_amend": bool(secs), "detect": how, "n_sections": len(secs),
                "section_chars": chars, "charter_amend_txt": txt_rel, "main_xml": main_f.name, "encoding": enc,
                "files": [{"name": f.name, "bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
                          for f in files],
                "folder": d.relative_to(ROOT).as_posix(), "fetched_at": now_iso()}
        write_json(meta_f, meta)
        out[rno] = meta
    out = {k: v for k, v in out.items() if k in notices}
    write_json(out_f, out)
    ok = [m for m in out.values() if "error" not in m]
    print(f"원문 {len(ok)}/{len(notices)} · 정관의 변경 있음 {sum(m['has_charter_amend'] for m in ok)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "fetch", "pdf", "ocr", "llm", "agm", "build"])
    ap.add_argument("sub", nargs="?", default="")
    ap.add_argument("--per-min", type=int, default=45, help="DART 웹 분당 상한 (다른 수집과 합쳐 80 이하로)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    A_INTERIM.mkdir(parents=True, exist_ok=True)
    if a.cmd == "plan":
        cmd_plan()
    elif a.cmd == "fetch":
        cmd_fetch(a.per_min)
    elif a.cmd == "pdf":
        cmd_pdf(a.force, a.per_min)
    elif a.cmd == "ocr":
        cmd_ocr()
    elif a.cmd == "llm":
        cmd_llm(a.sub, a.n)
    elif a.cmd == "agm":
        cmd_agm()
    elif a.cmd == "build":
        from s07e_absent_build import main as build
        build()
