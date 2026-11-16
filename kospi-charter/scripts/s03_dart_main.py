"""s03 DART 공시화면(main.do) — rcept_no_new(첨부정정) + 첨부문서 목록(attach_docs)

대상 = 최종보고서가 [첨부정정]인 행(시장 무관) ∪ 코스피 행(s02, KIND 기준일 현재).
main.do 한 번으로 두 가지를 같이 읽는다.

1) rcept_no_new  — 사용자 기존 프로젝트 규칙 그대로 (dart_disclosure/snowflake_dart_annualrep.ipynb get_recent,
   seibro-api/seibro_api/dart_report.py _get_rcept_no_new)
     · [첨부정정] 은 첨부서류만 갈아 끼운 공시라 접수번호는 새로 받지만 본문이 없다
     · main.do 의 <select id="family">(+본문선택+) 첫 옵션 = 가장 최근 본문 → 그 rcpNo 가 rcept_no_new
     · [첨부정정] 이 아닌 행은 rcept_no_new = rcept_no
     · family 가 비어 있거나 받지 못하면 rcept_no 로 둔다(status 로 표시)
   family 는 '지금' 기준 목록이다. 첨부정정 뒤에 [기재정정] 이 또 나왔으면 첫 옵션은 그 뒤 본문이다
   (예: HL홀딩스 첨부정정 20260318001665 → 20260813001221). 그런 행은 new_after_amend=True 로 남긴다.
   [첨부추가] 는 접수번호를 새로 받지 않는다(원 공시 행의 이름만 바뀐다) → 대상 아님.

2) 첨부문서 목록 — OpenDartReader.attach_docs(rcp_no) 와 같은 규칙(<select id="att">).
   att 도 보고서 가족 전체의 '지금' 목록이다. 원본·정정 어느 접수번호로 열어도 같은 목록이 나온다.

원본 화면은 data/raw/dart_main/{rcept_no}.html 에 저장 (받은 시각은 s03_main.json fetched_at).

출력  data/interim/s03_main.json   rcept_no → {fetched_at, family[], att[], rcept_no_new, new_status, new_after_amend}
"""
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (INTERIM, RAW, Http, attach_docs_from_html, cached_text, main_url, read_json,  # noqa: E402
                     select_options, write_json)

ATTACH_CORR = "[첨부정정]"


def targets(reports, market):
    return [r for r in reports
            if ATTACH_CORR in r["amend_tag"] or market[r["rcept_no"]]["market"] == "코스피"]


def prewarm():
    """s02 를 기다리지 않고 화면 캐시만 미리 받는다: [첨부정정] ∪ 현재 corp_cls='Y'.
    (제출 당시 코스피였지만 지금은 아닌 행은 s02 뒤 main() 이 마저 받는다)"""
    reports = read_json(INTERIM / "s01_reports.json")
    http = Http(delay=1.0)
    tg = [r for r in reports if ATTACH_CORR in r["amend_tag"] or r["corp_cls"] == "Y"]
    print(f"미리 받기 {len(tg)}건", flush=True)
    for i, r in enumerate(tg, 1):
        try:
            cached_text(RAW / "dart_main" / f"{r['rcept_no']}.html", lambda: http.get(main_url(r["rcept_no"])).text)
        except RuntimeError as e:
            print(f"  실패 {r['rcept_no']}: {e}", flush=True)
        if i % 100 == 0:
            print(f"  {i}/{len(tg)}", flush=True)


def main():
    reports = read_json(INTERIM / "s01_reports.json")
    market = read_json(INTERIM / "s02_market.json")
    out_f = INTERIM / "s03_main.json"
    out = read_json(out_f) if out_f.exists() else {}
    http = Http(delay=1.0)

    tg = targets(reports, market)
    print(f"대상 {len(tg)}건 (첨부정정 {sum(ATTACH_CORR in r['amend_tag'] for r in tg)} · "
          f"코스피 {sum(market[r['rcept_no']]['market'] == '코스피' for r in tg)})", flush=True)
    for i, r in enumerate(tg, 1):
        rno = r["rcept_no"]
        f = RAW / "dart_main" / f"{rno}.html"
        try:
            html = cached_text(f, lambda: http.get(main_url(rno)).text)
        except RuntimeError as e:
            print(f"  실패 {rno} {r['corp_name']}: {e}", flush=True)
            continue
        family = [{"rcpNo": v.replace("rcpNo=", "")[-14:], "title": t} for v, t in select_options(html, "family")]
        att = attach_docs_from_html(html)
        rec = {"fetched_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"),
               "family": family, "att": att}
        if ATTACH_CORR in r["amend_tag"]:
            if family:
                rec["rcept_no_new"], rec["new_status"] = family[0]["rcpNo"], "family_first"
            else:
                rec["rcept_no_new"], rec["new_status"] = rno, "fallback_no_family"
        else:
            rec["rcept_no_new"], rec["new_status"] = rno, "not_attach_corr"
        rec["new_after_amend"] = rec["rcept_no_new"] > rno
        out[rno] = rec
        if i % 50 == 0:
            write_json(out_f, out)
            print(f"  {i}/{len(tg)}", flush=True)
    write_json(out_f, out)

    ac = [out[r["rcept_no"]] for r in tg if ATTACH_CORR in r["amend_tag"] and r["rcept_no"] in out]
    print("첨부정정 rcept_no_new:", dict(Counter(x["new_status"] for x in ac)),
          "· 첨부정정보다 뒤 본문:", sum(x["new_after_amend"] for x in ac))
    print(f"받은 화면 {sum(r['rcept_no'] in out for r in tg)}/{len(tg)}")


if __name__ == "__main__":
    prewarm() if "--prewarm" in sys.argv else main()
