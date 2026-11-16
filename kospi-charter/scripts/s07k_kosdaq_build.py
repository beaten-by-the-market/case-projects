"""s07k 코스닥 결과물 — s07_build.py 와 같은 열·규칙, 대상만 코스닥 행

  data/final/kosdaq_charter.json · .csv · .xlsx   사업보고서 목록의 코스닥 행 + 정관 열(CH_COLS) + 주총 열(AGM_COLS)
  data/final/kosdaq_charter_docs.json · .csv      코스닥 정관 문서 단위 색인
  data/final/kosdaq_agm_notices.json · .csv       코스닥 주주총회소집공고 단위 색인
  data/final/kosdaq_absent.json · .csv            KIND 코스닥 상장사 중 사업보고서가 없어 목록에 없는 회사와 근거 (s02c)
  data/final/kosdaq_manifest.json                 기준일·조회기간·수집시점·건수

  · 행 기본 열(build_rows)·OCR/PDF/Opus 색인 읽기·주총 열(add_agm)·CSV/XLSX 쓰기는 s07_build 의 함수를 그대로 쓴다.
    s07_build.INTERIM 을 data/interim/kosdaq 로 바꿔 코스닥 색인(s04*·s05·s06)을 읽게 한다
    (build_rows 는 바꾸기 전에 불러 공용 s01·s02·s03 을 읽는다 — annual_reports.json 의 코스닥 행과 같은 값).
  · s07_build.add_charter 는 시장이 '코스피'로 들어 있어 같은 내용을 시장만 바꿔 add_charter() 로 둔다.
  · data/final/annual_reports.* · manifest.json 은 코스피 s07 이 쓴다 — 여기서는 건드리지 않는다.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, BGN, FINAL, ROOT, main_url, now_iso, read_json, write_json  # noqa: E402
from _kosdaq import KQ_INTERIM, MARKET  # noqa: E402
import s07_build as s7  # noqa: E402


def add_charter(rows):
    """s07_build.add_charter 와 같은 규칙 — 시장만 코스닥. 색인은 s7.INTERIM(=코스닥)에서 읽는다."""
    per_row = read_json(KQ_INTERIM / "s04_charter.json")
    docs = read_json(KQ_INTERIM / "s04_docs.json")
    ocr, pdf, llm = s7.load_ocr(), s7.load_pdf(), s7.load_llm()
    for d in docs.values():                  # 'empty' 로 남은 PDF 첨부 정관만 'pdf' (본문 텍스트 + PDF 링크인 정관은 text 그대로)
        if d.get("folder") in pdf and d["content_type"] == "empty":
            d["content_type"] = "pdf"
    out = []
    for row in rows:
        if row["market"] != MARKET:
            continue
        c = per_row.get(row["rcept_no"], {"charter_status": "not_processed"})
        x = dict(row, **{k: None for k in s7.CH_COLS})
        x["charter_status"] = c["charter_status"]
        if c["charter_status"] == "ok":
            d = docs.get(c["doc_key"])
            x.update(charter_title=c["charter_title"], charter_url=c["charter_url"], n_charter_att=c["n_charter_att"],
                     charter_rcpNo=c["doc_key"].split("_")[0], charter_dcmNo=c["doc_key"].split("_")[1])
            if d is None:
                x["charter_status"] = "download_failed"
            else:
                f = d["folder"]
                x.update(charter_att_date=d["att_date"], charter_viewer_url=(d["viewer_urls"] or [None])[0],
                         charter_content_type=d["content_type"], charter_text_chars=d["text_chars"],
                         charter_n_images=d["n_images"], charter_dir=f, charter_txt=f"{f}/charter.txt",
                         charter_img_dir=f"{f}/img" if d["n_images"] else None, charter_meta=f"{f}/meta.json",
                         charter_ocr_txt=ocr.get(f, {}).get("ocr_txt"), charter_ocr_chars=ocr.get(f, {}).get("chars"),
                         charter_pdf_txt=pdf.get(f, {}).get("pdf_txt"), charter_n_pdfs=pdf.get(f, {}).get("n_pdfs"),
                         charter_pdf_chars=pdf.get(f, {}).get("chars"),
                         charter_llm_txt=llm.get(f, {}).get("llm_txt"), charter_llm_chars=llm.get(f, {}).get("chars"))
                # 정관 전문을 읽을 파일 하나: Opus 전사(실패 쪽 없을 때) → Windows OCR → PDF 글 → charter.txt (s07 과 같은 순서)
                # 코스닥에서 생긴 두 경우만 다르다 (코스피에는 없던 경우):
                #   · text — 본문 텍스트 정관은 같은 정관 PDF 가 함께 붙어도 charter.txt (MDS테크·LB인베스트먼트)
                #   · pdf 인데 PDF 를 하나도 읽지 못함(DART 미서비스·DRM) → 빈 값 (실패 안내 줄뿐인 파일을 가리키지 않는다)
                llm_ok = x["charter_llm_txt"] if llm.get(f, {}).get("errors", 1) == 0 else None
                if d["content_type"] == "text":
                    x["charter_fulltext_txt"] = x["charter_txt"]
                elif d["content_type"] == "pdf" and not llm_ok and not (pdf.get(f, {}).get("chars") or 0):
                    x["charter_fulltext_txt"] = None
                else:
                    x["charter_fulltext_txt"] = llm_ok or x["charter_ocr_txt"] or x["charter_pdf_txt"] or x["charter_txt"]
        out.append(x)
    return out, docs


def main():
    FINAL.mkdir(parents=True, exist_ok=True)
    rows = s7.build_rows()                       # 공용 s01·s02·s03 (INTERIM 바꾸기 전)
    s7.INTERIM = KQ_INTERIM                      # 이 뒤 s7.load_* · add_agm 은 코스닥 색인을 읽는다
    kc, docs = add_charter(rows)
    kc, notices = s7.add_agm(kc)
    kcols = s7.API_COLS + s7.ADD_COLS + s7.CH_COLS + s7.AGM_COLS
    write_json(FINAL / "kosdaq_charter.json", kc)
    s7.write_csv(FINAL / "kosdaq_charter.csv", kc, kcols)
    s7.write_xlsx(FINAL / "kosdaq_charter.xlsx", kc, kcols)
    from openpyxl import load_workbook          # s7.write_xlsx 의 시트 이름(kospi_charter)만 바꾼다
    wb = load_workbook(FINAL / "kosdaq_charter.xlsx")
    wb.active.title = "kosdaq_charter"
    wb.save(FINAL / "kosdaq_charter.xlsx")

    dcols = ["corp_code", "corp_name", "stock_code", "att_title", "att_date", "rcpNo", "dcmNo", "att_url",
             "content_type", "text_chars", "n_images", "n_image_errors", "n_nodes", "folder", "used_by_rcept_no",
             "fetched_at"]
    drows = sorted(({c: d.get(c) for c in dcols} for d in docs.values()), key=lambda d: (d["stock_code"], d["att_date"]))
    write_json(FINAL / "kosdaq_charter_docs.json", drows)
    s7.write_csv(FINAL / "kosdaq_charter_docs.csv", drows, dcols)
    ncols = list(notices[0]) if notices else ["rcept_no"]
    write_json(FINAL / "kosdaq_agm_notices.json", notices)
    s7.write_csv(FINAL / "kosdaq_agm_notices.csv", notices, ncols)

    # KIND 코스닥인데 사업보고서가 없어 목록에 없는 회사 (s02c) — 열 = s07 ABSENT_COLS + 코스닥에서 더한 두 열
    #   corp_code_match_by  고유번호를 찾은 방법 (기준일 당일 상장사는 corpCode 에 종목코드가 없어 name_unlisted)
    #   kind_titles_window  KIND 공시 제목별 건수 (예: 피씨엘 '회생절차개시신청'·'정기보고서 미제출 관련 상장폐지 절차 미진행')
    acols = s7.ABSENT_COLS + [c for c in ("corp_code_match_by", "kind_titles_window") if c not in s7.ABSENT_COLS]
    ab_f = KQ_INTERIM / "s02c_kosdaq_absent.json"
    ab = read_json(ab_f) if ab_f.exists() else None
    absent = []
    for a in (ab or {}).get("absent", []):
        r = {c: a.get(c) for c in acols}
        r["dart_url"] = main_url(a["last_filing_rcept_no"]) if a.get("last_filing_rcept_no") else None
        absent.append(r)
    write_json(FINAL / "kosdaq_absent.json", absent)
    dict_cols = [c for c in ("filing_forms_window", "kind_misc_groups", "kind_misc_kinds", "kind_titles_window") if c in acols]
    s7.write_csv(FINAL / "kosdaq_absent.csv",
                 [{**r, **{c: ";".join(f"{k} {v}건" for k, v in (r[c] or {}).items()) for c in dict_cols},
                   **({"kind_misc_items": ";".join(f"{d} {n} {t}" for d, n, t in (r["kind_misc_items"] or []))}
                      if "kind_misc_items" in acols else {})}
                  for r in absent], acols + ["dart_url"])

    def span(vals):
        v = sorted(x for x in vals if x)
        return [v[0], v[-1]] if v else None

    pages = read_json(KQ_INTERIM / "s03_main.json")
    adocs_f = KQ_INTERIM / "s06_agm_docs.json"
    manifest = {
        "generated_at": now_iso(), "market": MARKET, "as_of": str(AS_OF), "window": [str(BGN), str(AS_OF)],
        "fetched": {"dart_main": span(pages[x["rcept_no"]]["fetched_at"] for x in kc if x["rcept_no"] in pages),
                    "charter_docs": span(d.get("fetched_at") for d in docs.values()),
                    "agm_xml": span(m.get("fetched_at") for m in (read_json(adocs_f).values() if adocs_f.exists() else []))},
        "kind_kosdaq": ({"detail": ab["kind_detail"], "summary": ab["kind_summary"],
                         "absent_reason": dict(Counter(a["reason_code"] for a in absent))} if ab else None),
        "counts": {
            "kosdaq_rows": len(kc),
            "sec_group": dict(Counter(x["sec_group"] for x in kc)),
            "amend_tag": dict(Counter(x["amend_tag"] or "(없음)" for x in kc)),
            "kosdaq_absent": len(absent),
            "kosdaq_charter_status": dict(Counter(x["charter_status"] for x in kc)),
            "charter_docs": len(drows),
            "charter_content_type": dict(Counter(d["content_type"] for d in drows)),
            "charter_images": sum(d["n_images"] or 0 for d in drows),
            "charter_ocr_docs": sum(bool(x.get("charter_ocr_txt")) for x in kc),
            "charter_pdf_docs": sum(bool(x.get("charter_pdf_txt")) for x in kc),
            "charter_llm_docs": sum(bool(x.get("charter_llm_txt")) for x in kc),
            "agm_notices": len(notices),
            "agm_notices_with_charter_amend": sum(bool(n["has_charter_amend"]) for n in notices),
            "agm_notice_errors": sum(bool(n["error"]) for n in notices),
            "kosdaq_rows_agm_count": {str(k): v for k, v in sorted(Counter(x["agm_count"] for x in kc).items())},
            "kosdaq_rows_agm_charter_amend_count": {
                str(k): v for k, v in sorted(Counter(x["agm_charter_amend_count"] for x in kc).items())},
        },
    }
    write_json(FINAL / "kosdaq_manifest.json", manifest)
    for k, v in manifest["counts"].items():
        print(f"  {k}: {v}")

    missing = [r[c] for r in kc for c in ("charter_txt", "charter_meta", "charter_fulltext_txt")
               if r.get(c) and not (ROOT / r[c]).exists()]
    missing += [p for r in kc for p in r["agm_charter_amend_txt"] if not (ROOT / p).exists()]
    print(f"링크 파일 확인: 없는 경로 {len(missing)}건", missing[:5])


if __name__ == "__main__":
    main()
