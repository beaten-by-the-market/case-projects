"""s03k 코스닥 행의 DART 공시화면(main.do) — s03_dart_main.py 와 같은 규칙, 대상만 코스닥 행 전부

  · 대상 = s01 사업보고서 행 중 s02 시장이 코스닥인 것 전부 (코스피 s03 은 '[첨부정정] 전부 ∪ 코스피 행')
  · main.do 한 번으로 family(본문 목록 → rcept_no_new·원본 최초 접수번호)와 att(첨부문서 목록 = attach_docs) 를 읽는다
  · 화면 원본은 코스피와 같은 캐시 data/raw/dart_main/{rcept_no}.html 을 쓴다 — 코스닥 [첨부정정] 행은 코스피 s03 이
    이미 받아 두었으므로 그 저장본을 읽는다(받은 시각은 fetched_at 에 남는다)

출력  data/interim/kosdaq/s03_main.json   rcept_no → {fetched_at, family[], att[], rcept_no_new, new_status, new_after_amend}
"""
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import RAW, Http, attach_docs_from_html, cached_text, main_url, read_json, select_options, write_json  # noqa: E402
from _kosdaq import KQ_INTERIM, kosdaq_rows  # noqa: E402
from s03_dart_main import ATTACH_CORR  # noqa: E402


def page_record(rno: str, amend_tag: str, html: str, f: Path) -> dict:
    """s03_dart_main.main() 의 행 기록과 같은 모양."""
    family = [{"rcpNo": v.replace("rcpNo=", "")[-14:], "title": t} for v, t in select_options(html, "family")]
    rec = {"fetched_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"),
           "family": family, "att": attach_docs_from_html(html)}
    if ATTACH_CORR in amend_tag:
        if family:
            rec["rcept_no_new"], rec["new_status"] = family[0]["rcpNo"], "family_first"
        else:
            rec["rcept_no_new"], rec["new_status"] = rno, "fallback_no_family"
    else:
        rec["rcept_no_new"], rec["new_status"] = rno, "not_attach_corr"
    rec["new_after_amend"] = rec["rcept_no_new"] > rno
    return rec


def main():
    rows, _ = kosdaq_rows()
    out_f = KQ_INTERIM / "s03_main.json"
    out = read_json(out_f) if out_f.exists() else {}
    http = Http(delay=1.0)
    cached = sum((RAW / "dart_main" / f"{r['rcept_no']}.html").exists() for r in rows)
    print(f"코스닥 {len(rows)}행 · 화면 저장본 있음 {cached} · 받을 것 {len(rows) - cached}", flush=True)
    for i, r in enumerate(rows, 1):
        rno = r["rcept_no"]
        f = RAW / "dart_main" / f"{rno}.html"
        try:
            html = cached_text(f, lambda: http.get(main_url(rno)).text)
        except RuntimeError as e:
            print(f"  실패 {rno} {r['corp_name']}: {e}", flush=True)
            continue
        out[rno] = page_record(rno, r["amend_tag"], html, f)
        if i % 100 == 0:
            write_json(out_f, out)
            print(f"  {i}/{len(rows)}", flush=True)
    write_json(out_f, out)

    ac = [out[r["rcept_no"]] for r in rows if ATTACH_CORR in r["amend_tag"] and r["rcept_no"] in out]
    print("첨부정정 rcept_no_new:", dict(Counter(x["new_status"] for x in ac)),
          "· 첨부정정보다 뒤 본문:", sum(x["new_after_amend"] for x in ac))
    print(f"받은 화면 {sum(r['rcept_no'] in out for r in rows)}/{len(rows)} · 첨부 목록 빈 화면 "
          f"{sum(1 for r in rows if r['rcept_no'] in out and not out[r['rcept_no']]['att'])}")


if __name__ == "__main__":
    main()
