"""s07e 사업보고서가 없어 목록에 없는 회사의 정관 결과물 (s04e → data/final/absent_charter.json · .csv)

1행 = 회사 1곳 (두 시장 함께, 키 market + stock_code). 정관 열(CH_COLS)·주총 열(AGM_COLS)은 kospi_charter 와 같은 규칙(s07).
사업보고서 열(report_nm · rcept_no · fiscal_year …)은 없고, 대신 근거문서 열을 둔다.

  market · stock_code · corp_name · corp_code · sec_group · listed_date · settle_month(OpenDART company.json acc_mt)
  reason_code · reason                      빠진 이유 (kospi_absent · kosdaq_absent 그대로)
  charter_source_doc                        근거문서: '증권신고서' · '분할계획서' · '기타신고사항' · '홈페이지'
  charter_source_rcept_no · _nm · _dt       근거문서 접수번호(DART·KIND, 홈페이지는 빈 값) · 이름 · 날짜(YYYYMMDD)
  charter_source_url                        근거문서 화면: DART main.do · KIND disclsviewer · 홈페이지 게시 화면
  CH_COLS                                   charter_url = 정관 첨부(DART att) 또는 원본 파일 주소(KIND·홈페이지)
  AGM_COLS                                  orig_rcept_no · orig_rcept_dt = 소집공고 셈 기간 시작으로 쓴 근거문서 원본

빠진 이유(reason)에 em dash 를 쓰지 않는다(사용자 지시) — 들어 있으면 멈춘다.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, ROOT, main_url, read_json, write_json  # noqa: E402
import s07_build as s7  # noqa: E402
from s04e_absent_charter import A_INTERIM, plan_path  # noqa: E402

SRC_COLS = ["charter_source_doc", "charter_source_rcept_no", "charter_source_nm", "charter_source_dt", "charter_source_url"]
HEAD = ["market", "stock_code", "corp_name", "corp_code", "sec_group", "listed_date", "settle_month", "reason_code", "reason"]
COLS = HEAD + SRC_COLS + s7.CH_COLS + s7.AGM_COLS


def kind_url(acptno: str) -> str:
    return f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acptno}"


def main():
    plan = read_json(plan_path())
    docs_f = A_INTERIM / "s04_docs.json"
    docs = read_json(docs_f) if docs_f.exists() else {}
    s7.INTERIM = A_INTERIM                               # load_ocr/pdf/llm · add_agm 이 이 폴더의 색인을 읽는다
    ocr, pdf, llm = s7.load_ocr(), s7.load_pdf(), s7.load_llm()
    amap_f = A_INTERIM / "s05_agm_map.json"
    rows = []
    for p in plan:
        if "—" in (p.get("reason") or ""):
            raise SystemExit(f"reason 에 em dash: {p['corp_name']} — s02b/s02c 를 고쳐 다시 돌린다")
        src = p.get("source") or {}
        x = {k: p.get(k) for k in HEAD if k != "settle_month"}
        x["settle_month"] = p.get("acc_mt")
        rno = src.get("rcept_no") or src.get("kind_acptno")
        x.update(charter_source_doc=p.get("source_doc"), charter_source_rcept_no=rno,
                 charter_source_nm=src.get("nm"), charter_source_dt=src.get("dt"),
                 charter_source_url=(main_url(src["rcept_no"]) if src.get("rcept_no")
                                     else kind_url(src["kind_acptno"]) if src.get("kind_acptno") else src.get("page")))
        x.update({k: None for k in s7.CH_COLS})
        x["charter_status"] = p.get("charter_status") or ("source_pending" if not p.get("source_doc") else "not_processed")
        d = docs.get(p.get("doc_key") or "")
        if x["charter_status"] == "ok" and d:
            f = d["folder"]
            ctype = "pdf" if f in pdf and d["content_type"] == "empty" else d["content_type"]
            x.update(charter_title=p.get("charter_title") or d.get("att_title"), charter_url=p.get("charter_url") or d.get("att_url"),
                     n_charter_att=p.get("n_charter_att"), charter_rcpNo=d.get("rcpNo"), charter_dcmNo=d.get("dcmNo"),
                     charter_att_date=d.get("att_date"), charter_viewer_url=(d.get("viewer_urls") or [None])[0],
                     charter_content_type=ctype, charter_text_chars=d.get("text_chars"), charter_n_images=d.get("n_images"),
                     charter_dir=f, charter_txt=f"{f}/charter.txt" if (ROOT / f / "charter.txt").exists() else None,
                     charter_img_dir=f"{f}/img" if d.get("n_images") else None, charter_meta=f"{f}/meta.json",
                     charter_ocr_txt=ocr.get(f, {}).get("ocr_txt"), charter_ocr_chars=ocr.get(f, {}).get("chars"),
                     charter_pdf_txt=pdf.get(f, {}).get("pdf_txt"), charter_n_pdfs=pdf.get(f, {}).get("n_pdfs"),
                     charter_pdf_chars=pdf.get(f, {}).get("chars"),
                     charter_llm_txt=llm.get(f, {}).get("llm_txt"), charter_llm_chars=llm.get(f, {}).get("chars"))
            llm_ok = x["charter_llm_txt"] if llm.get(f, {}).get("errors", 1) == 0 else None
            if ctype == "text":                                          # 01 R7-7 과 같은 규칙
                x["charter_fulltext_txt"] = x["charter_txt"]
            elif ctype == "pdf" and not llm_ok and not (pdf.get(f, {}).get("chars") or 0):
                x["charter_fulltext_txt"] = None
            else:
                x["charter_fulltext_txt"] = llm_ok or x["charter_ocr_txt"] or x["charter_pdf_txt"] or x["charter_txt"]
        x["rcept_no"] = p["stock_code"]                                  # add_agm 이 s05_agm_map 을 이 키로 찾는다
        x["rcept_dt"] = ""
        rows.append(x)
    if amap_f.exists():
        rows, notices = s7.add_agm(rows)
    else:
        notices = []
        for x in rows:
            x.update(orig_rcept_no=None, orig_rcept_dt=None, agm_count=None, agm_charter_amend_count=None, agm_rcept_nos=[],
                     agm_kinds=[], agm_charter_amend_rcept_nos=[], agm_charter_amend_txt=[], agm_charter_amend_dart_url=[],
                     agm_errors=None)
    for x in rows:
        x.pop("rcept_no", None)
        x.pop("rcept_dt", None)
        if x.get("charter_status") != "ok":                              # 소집공고는 정관을 찾은 회사만 센다
            x.update(orig_rcept_no=None, orig_rcept_dt=None, agm_count=None, agm_charter_amend_count=None)
    rows = [{c: x.get(c) for c in COLS} for x in rows]
    write_json(FINAL / "absent_charter.json", rows)
    s7.write_csv(FINAL / "absent_charter.csv", rows, COLS)
    print(f"absent_charter {len(rows)}행 · 근거문서 {dict(Counter((r['market'], r['charter_source_doc']) for r in rows))}"
          f" · 정관 {dict(Counter(r['charter_status'] for r in rows))} · 종류 {dict(Counter(r['charter_content_type'] for r in rows))}"
          f" · 소집공고 {sum(r['agm_count'] or 0 for r in rows)}건(정관변경 {sum(r['agm_charter_amend_count'] or 0 for r in rows)})")
    missing = [r[c] for r in rows for c in ("charter_txt", "charter_meta", "charter_fulltext_txt") if r.get(c) and not (ROOT / r[c]).exists()]
    missing += [q for r in rows for q in (r["agm_charter_amend_txt"] or []) if not (ROOT / q).exists()]
    print(f"링크 파일 확인: 없는 경로 {len(missing)}건", missing[:5])


if __name__ == "__main__":
    main()
