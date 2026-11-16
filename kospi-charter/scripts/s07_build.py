"""s07 결과물 만들기

  data/final/annual_reports.json · .csv     최근 1년 사업보고서(최종본) 전체 + rcept_no_new·사업연도·결산월·소속시장(KIND 기준일 현재)
  data/final/kospi_charter.json · .csv · .xlsx
                                            위 목록의 코스피 행 + 정관 URL + 내려받은 원문 위치(상대경로 링크)
  data/final/charter_docs.json · .csv       정관 문서 단위 색인 (같은 정관을 여러 행이 쓰면 한 줄)
  data/final/agm_notices.json · .csv        주주총회소집공고 단위 색인 (정관의 변경 절 유무·txt 위치)
  data/final/manifest.json                  기준일·조회기간·건수·출처·생성시각

경로 열(charter_dir·charter_txt·charter_img_dir·charter_meta)은 이 케이스 폴더(kospi-charter/) 기준 상대경로다.
엑셀은 data/final/ 에 있으므로 하이퍼링크를 '../charter/…' 로 건다.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, BGN, FINAL, INTERIM, ROOT, main_url, now_iso, read_json, write_json  # noqa: E402

API_COLS = ["corp_code", "corp_name", "stock_code", "corp_cls", "report_nm", "rcept_no", "flr_nm", "rcept_dt", "rm"]
ADD_COLS = ["rcept_no_new", "fiscal_year", "settle_month", "report_period", "market",
            "market_basis_date", "sec_group", "market_match_by", "amend_tag", "rcept_no_new_status", "dart_url"]
CH_COLS = ["charter_status", "charter_title", "charter_att_date", "charter_rcpNo", "charter_dcmNo", "charter_url",
           "charter_viewer_url", "charter_content_type", "charter_text_chars", "charter_n_images", "n_charter_att",
           "charter_dir", "charter_txt", "charter_img_dir", "charter_meta", "charter_ocr_txt", "charter_ocr_chars",
           "charter_pdf_txt", "charter_n_pdfs", "charter_pdf_chars", "charter_llm_txt", "charter_llm_chars",
           "charter_fulltext_txt"]
AGM_COLS = ["orig_rcept_no", "orig_rcept_dt", "agm_count", "agm_charter_amend_count", "agm_rcept_nos", "agm_kinds",
            "agm_charter_amend_rcept_nos", "agm_charter_amend_txt", "agm_charter_amend_dart_url", "agm_errors"]
LIST_COLS = {"agm_rcept_nos", "agm_kinds", "agm_charter_amend_rcept_nos", "agm_charter_amend_txt",
             "agm_charter_amend_dart_url", "used_by_rcept_no"}


def build_rows():
    reports = read_json(INTERIM / "s01_reports.json")
    market = read_json(INTERIM / "s02_market.json")
    pages = read_json(INTERIM / "s03_main.json")
    rows = []
    for r in reports:
        m, pg = market[r["rcept_no"]], pages.get(r["rcept_no"])
        row = {c: r[c] for c in API_COLS}
        if "[첨부정정]" in r["amend_tag"]:
            new, st = (pg["rcept_no_new"], pg["new_status"]) if pg else (r["rcept_no"], "fallback_not_fetched")
            if pg and pg["new_after_amend"]:
                st += "_after_amend"
        else:
            new, st = r["rcept_no"], ""
        row.update(rcept_no_new=new, fiscal_year=r["fiscal_year"], settle_month=r["settle_month"],
                   report_period=r["report_period"], market=m["market"],
                   market_basis_date=m["snap_date"], sec_group=m["sec_group"], market_match_by=m["match_by"],
                   amend_tag=r["amend_tag"], rcept_no_new_status=st, dart_url=main_url(r["rcept_no"]))
        rows.append(row)
    return rows


def load_ocr() -> dict:
    """s04b(스캔 정관 OCR) 결과 — 정관 폴더(케이스 기준 상대경로) → {ocr_txt, total_chars}. 없으면 빈 dict."""
    f = INTERIM / "s04b_ocr.json"
    if not f.exists():
        return {}
    out = {}
    for k, v in read_json(f).items():
        txt = v.get("ocr_txt") or ""
        folder = txt.rsplit("/", 1)[0] if txt else k.replace("\\", "/")
        if txt and (ROOT / txt).exists():
            out[folder] = {"ocr_txt": txt, "chars": v.get("total_chars")}
    return out


def load_pdf() -> dict:
    """s04c(PDF 첨부 정관) 결과 — 정관 폴더 → {pdf_txt, n_pdfs, chars}. 없으면 빈 dict."""
    f = INTERIM / "s04c_pdf.json"
    if not f.exists():
        return {}
    return {k: {"pdf_txt": v["pdf_txt"], "n_pdfs": v.get("n_pdfs"), "chars": v.get("total_chars")}
            for k, v in read_json(f).items() if v.get("pdf_txt") and (ROOT / v["pdf_txt"]).exists()}


def load_llm() -> dict:
    """s04d(Opus 전사) 결과 — 정관 폴더 → {llm_txt, chars, errors}. 없으면 빈 dict."""
    f = INTERIM / "s04d_llm.json"
    if not f.exists():
        return {}
    return {k: {"llm_txt": v["llm_txt"], "chars": v.get("total_chars"), "errors": v.get("errors", 0)}
            for k, v in read_json(f).items() if v.get("llm_txt") and (ROOT / v["llm_txt"]).exists()}


def add_charter(rows):
    per_row = read_json(INTERIM / "s04_charter.json")
    docs = read_json(INTERIM / "s04_docs.json")
    ocr = load_ocr()
    pdf = load_pdf()
    llm = load_llm()
    for d in docs.values():                  # s04 첫 실행 때 'empty' 로 남은 PDF 첨부 정관 → 'pdf' (s04c 가 받았다)
        if d.get("folder") in pdf:
            d["content_type"] = "pdf"
    out = []
    for row in rows:
        if row["market"] != "코스피":
            continue
        c = per_row.get(row["rcept_no"], {"charter_status": "not_processed"})
        x = dict(row, **{k: None for k in CH_COLS})
        x["charter_status"] = c["charter_status"]
        if c["charter_status"] == "ok":
            d = docs.get(c["doc_key"])
            x.update(charter_title=c["charter_title"], charter_url=c["charter_url"], n_charter_att=c["n_charter_att"],
                     charter_rcpNo=c["doc_key"].split("_")[0], charter_dcmNo=c["doc_key"].split("_")[1])
            if d is None:
                x["charter_status"] = "download_failed"
            else:
                x.update(charter_att_date=d["att_date"], charter_viewer_url=(d["viewer_urls"] or [None])[0],
                         charter_content_type=d["content_type"], charter_text_chars=d["text_chars"],
                         charter_n_images=d["n_images"], charter_dir=d["folder"],
                         charter_txt=f"{d['folder']}/charter.txt",
                         charter_img_dir=f"{d['folder']}/img" if d["n_images"] else None,
                         charter_meta=f"{d['folder']}/meta.json",
                         charter_ocr_txt=ocr.get(d["folder"], {}).get("ocr_txt"),
                         charter_ocr_chars=ocr.get(d["folder"], {}).get("chars"),
                         charter_pdf_txt=pdf.get(d["folder"], {}).get("pdf_txt"),
                         charter_n_pdfs=pdf.get(d["folder"], {}).get("n_pdfs"),
                         charter_pdf_chars=pdf.get(d["folder"], {}).get("chars"),
                         charter_llm_txt=llm.get(d["folder"], {}).get("llm_txt"),
                         charter_llm_chars=llm.get(d["folder"], {}).get("chars"))
                # 정관 전문을 읽을 파일 하나: Opus 전사(실패 쪽 없을 때) → Windows OCR → PDF 글 → charter.txt
                llm_ok = x["charter_llm_txt"] if llm.get(d["folder"], {}).get("errors", 1) == 0 else None
                x["charter_fulltext_txt"] = llm_ok or x["charter_ocr_txt"] or x["charter_pdf_txt"] or x["charter_txt"]
        out.append(x)
    return out, docs


def add_agm(kc):
    """주총 열 — s05(원본 제출일·기간 안 소집공고)·s06(정관의 변경 절)."""
    amap = read_json(INTERIM / "s05_agm_map.json")
    adocs = read_json(INTERIM / "s06_agm_docs.json")
    for x in kc:
        a = amap.get(x["rcept_no"], {"orig_rcept_no": x["rcept_no"], "orig_rcept_dt": x["rcept_dt"], "notices": []})
        ns = [adocs.get(n, {"rcept_no": n, "error": "not_fetched"}) for n in a["notices"]]
        am = [m for m in ns if m.get("has_charter_amend")]
        x.update(orig_rcept_no=a["orig_rcept_no"], orig_rcept_dt=a["orig_rcept_dt"],
                 agm_count=len(ns), agm_charter_amend_count=len(am),
                 agm_rcept_nos=[m["rcept_no"] for m in ns], agm_kinds=[m.get("agm_kind", "") for m in ns],
                 agm_charter_amend_rcept_nos=[m["rcept_no"] for m in am],
                 agm_charter_amend_txt=[m["charter_amend_txt"] for m in am],
                 agm_charter_amend_dart_url=[m["dart_url"] for m in am],
                 agm_errors=sum("error" in m for m in ns))
    notices = []
    used = {}
    for x in kc:
        for n in x["agm_rcept_nos"]:
            used.setdefault(n, []).append(x["rcept_no"])
    src = {n["rcept_no"]: n for n in read_json(INTERIM / "s05_agm_notices.json")}
    for n, by in sorted(used.items()):
        m, s = adocs.get(n, {}), src[n]
        notices.append({"corp_code": s["corp_code"], "corp_name": s["corp_name"], "stock_code": m.get("stock_code"),
                        "rcept_no": n, "rcept_dt": s["rcept_dt"], "report_nm": s["report_nm"],
                        "amend_tag": s["amend_tag"], "agm_kind": m.get("agm_kind"),
                        "has_charter_amend": m.get("has_charter_amend"), "detect": m.get("detect"),
                        "section_chars": m.get("section_chars"), "charter_amend_txt": m.get("charter_amend_txt"),
                        "folder": m.get("folder"),
                        "main_xml": f"{m['folder']}/{m['main_xml']}" if m.get("main_xml") else None,
                        "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={n}", "error": m.get("error"),
                        "used_by_rcept_no": by})
    return kc, notices


def flat(v, sep=";"):
    return sep.join(str(i) for i in v) if isinstance(v, list) else v


def write_csv(path: Path, rows: list[dict], cols: list[str]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows({k: flat(v) for k, v in r.items()} for r in rows)


def write_xlsx(path: Path, rows: list[dict], cols: list[str]):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "kospi_charter"
    ws.append(cols)
    link = Font(color="0563C1", underline="single")
    web_cols = {"dart_url", "charter_url", "charter_viewer_url", "agm_charter_amend_dart_url"}
    local_cols = {"charter_dir", "charter_txt", "charter_img_dir", "charter_meta", "charter_ocr_txt", "charter_pdf_txt", "charter_llm_txt",
                  "charter_fulltext_txt", "agm_charter_amend_txt"}
    for i, r in enumerate(rows, start=2):
        for j, c in enumerate(cols, start=1):
            v = r.get(c)
            first = v[0] if isinstance(v, list) and v else (None if isinstance(v, list) else v)
            cell = ws.cell(row=i, column=j, value=flat(v, "\n"))
            if first and c in web_cols:                  # 여러 개면 첫 번째에 링크, 글자는 전부
                cell.hyperlink, cell.font = first, link
            elif first and c in local_cols:              # 통합문서(data/final) 기준 상대경로
                cell.hyperlink, cell.font = "../" + first.removeprefix("data/"), link
    for j, c in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(j)].width = min(48, max(10, len(c) + 2))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def main():
    FINAL.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    cols = API_COLS + ADD_COLS
    write_json(FINAL / "annual_reports.json", rows)
    write_csv(FINAL / "annual_reports.csv", rows, cols)

    kc, docs = add_charter(rows)
    kc, notices = add_agm(kc)
    kcols = cols + CH_COLS + AGM_COLS
    write_json(FINAL / "kospi_charter.json", kc)
    write_csv(FINAL / "kospi_charter.csv", kc, kcols)
    write_xlsx(FINAL / "kospi_charter.xlsx", kc, kcols)

    dcols = ["corp_code", "corp_name", "stock_code", "att_title", "att_date", "rcpNo", "dcmNo", "att_url",
             "content_type", "text_chars", "n_images", "n_image_errors", "n_nodes", "folder", "used_by_rcept_no",
             "fetched_at"]
    drows = [{c: d.get(c) for c in dcols} for d in docs.values()]       # used_by_rcept_no 는 JSON 배열, CSV 는 ";"
    drows.sort(key=lambda d: (d["stock_code"], d["att_date"]))
    write_json(FINAL / "charter_docs.json", drows)
    write_csv(FINAL / "charter_docs.csv", drows, dcols)
    ncols = list(notices[0]) if notices else ["rcept_no"]
    write_json(FINAL / "agm_notices.json", notices)
    write_csv(FINAL / "agm_notices.csv", notices, ncols)

    # 수집시점 — DART 화면·원문은 받은 때 기준이라 범위를 남긴다 (웹페이지 '한계'에 표시)
    def span(vals):
        v = sorted(x for x in vals if x)
        return [v[0], v[-1]] if v else None

    pages = read_json(INTERIM / "s03_main.json")
    fetched = {
        "dart_main": span(pages[r["rcept_no"]]["fetched_at"] for r in rows if r["rcept_no"] in pages),
        "charter_docs": span(d.get("fetched_at") for d in docs.values()),
        "agm_xml": span(m.get("fetched_at") for m in read_json(INTERIM / "s06_agm_docs.json").values()),
    }
    manifest = {
        "generated_at": now_iso(), "as_of": str(AS_OF), "window": [str(BGN), str(AS_OF)], "fetched": fetched,
        "source": {"list": "OpenDART list.json pblntf_detail_ty=A001 last_reprt_at=Y",
                   "market": "KIND listed_issue_status — 기준일 현재 상장 목록 한 번 (제출 당시 아님)",
                   "rcept_no_new": "DART main.do <select id=family> 첫 옵션 ([첨부정정] 행만)",
                   "charter": "DART main.do <select id=att> (OpenDartReader.attach_docs 규칙) → viewer.do",
                   "agm": "OpenDART list.json E006 last_reprt_at=Y, 접수일 ∈ [원본 최초 접수일, 기준일] → document.xml, "
                          "TITLE@AASSOCNOTE=L0-0-2-2-0(정관의 변경)"},
        "counts": {
            "annual_reports": len(rows),
            "market": dict(Counter(r["market"] for r in rows)),
            "amend_tag": dict(Counter(r["amend_tag"] or "(없음)" for r in rows)),
            "fiscal_year": {str(k): v for k, v in sorted(Counter(r["fiscal_year"] for r in rows).items())},
            "settle_month": {str(k): v for k, v in sorted(Counter(r["settle_month"] for r in rows).items())},
            "rcept_no_new_changed": sum(r["rcept_no_new"] != r["rcept_no"] for r in rows),
            "kospi_rows": len(kc),
            "kospi_charter_status": dict(Counter(r["charter_status"] for r in kc)),
            "charter_docs": len(drows),
            "charter_content_type": dict(Counter(d["content_type"] for d in drows)),
            "charter_images": sum(d["n_images"] or 0 for d in drows),
            "charter_ocr_docs": sum(bool(x.get("charter_ocr_txt")) for x in kc),
            "charter_pdf_docs": sum(bool(x.get("charter_pdf_txt")) for x in kc),
            "charter_llm_docs": sum(bool(x.get("charter_llm_txt")) for x in kc),
            "agm_notices": len(notices),
            "agm_notices_with_charter_amend": sum(bool(n["has_charter_amend"]) for n in notices),
            "agm_notice_errors": sum(bool(n["error"]) for n in notices),
            "kospi_rows_agm_count": {str(k): v for k, v in sorted(Counter(x["agm_count"] for x in kc).items())},
            "kospi_rows_agm_charter_amend_count": {
                str(k): v for k, v in sorted(Counter(x["agm_charter_amend_count"] for x in kc).items())},
        },
    }
    write_json(FINAL / "manifest.json", manifest)
    for k, v in manifest["counts"].items():
        print(f"  {k}: {v}")

    missing = [r for r in kc for c in ("charter_txt", "charter_meta") if r.get(c) and not (ROOT / r[c]).exists()]
    missing += [p for r in kc for p in r["agm_charter_amend_txt"] if not (ROOT / p).exists()]
    print(f"링크 파일 확인: 없는 경로 {len(missing)}건")


if __name__ == "__main__":
    main()
