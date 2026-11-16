"""s05k 코스닥 주주총회소집공고 목록 (최종본) — s05_agm_list.py 와 같은 규칙, 대상만 코스닥 행

  · 기간 = [사업보고서 원본 최초 접수일(s03k family 의 가장 오래된 본문), 기준일], 소집공고 **접수일** 기준 (01 R6)
  · OpenDART list.json E006 · last_reprt_at=Y 를 시장 전체로 3개월 구간씩 받아 코스닥 회사만 거른다
    (s05_agm_list.fetch 그대로 — 응답 페이지 캐시 data/raw/opendart_list/E006_Y_{시작}_{끝}_pNNN.json 을 코스피와 같이 쓴다.
     구간 시작이 코스피와 다르면 새 구간 파일을 받는다)

출력
  data/interim/kosdaq/s05_agm_notices.json   기간 안 코스닥 회사의 소집공고 최종본 (API 열 + amend_tag)
  data/interim/kosdaq/s05_agm_map.json       사업보고서 rcept_no → orig_rcept_no·orig_rcept_dt·notices[접수번호…]
"""
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, Http, dart_keys, parse_report_nm, read_json, write_json  # noqa: E402
from _kosdaq import KQ_INTERIM, MARKET, kosdaq_rows  # noqa: E402
from s01_list import API_COLS, windows  # noqa: E402
from s05_agm_list import fetch, orig_of  # noqa: E402


def main():
    rows, _ = kosdaq_rows()
    pages = read_json(KQ_INTERIM / "s03_main.json")
    origin = {r["rcept_no"]: orig_of(r["rcept_no"], pages.get(r["rcept_no"])) for r in rows}
    start = min(date(int(o[:4]), int(o[4:6]), int(o[6:8])) for o in origin.values())
    print(f"{MARKET} {len(rows)}행 (화면 없음 {sum(r['rcept_no'] not in pages for r in rows)}) · 소집공고 조회 {start} ~ {AS_OF}")

    http, keys = Http(delay=0.35), dart_keys()
    allrows = []
    for b, e in windows(start, AS_OF):
        allrows += fetch(http, keys, b, e)
    corps = {r["corp_code"] for r in rows}
    seen, notices = set(), []
    for x in allrows:
        if x["corp_code"] in corps and x["rcept_no"] not in seen:
            seen.add(x["rcept_no"])
            p = parse_report_nm(x["report_nm"])
            notices.append({**{c: x.get(c, "") for c in API_COLS}, "amend_tag": p["amend_tag"]})
    notices.sort(key=lambda x: x["rcept_no"])
    write_json(KQ_INTERIM / "s05_agm_notices.json", notices)
    print(f"시장 전체 {len(allrows)}건 → {MARKET} 회사 {len(notices)}건")
    print("  보고서명:", Counter(n["report_nm"] for n in notices).most_common(8))

    by_corp = {}
    for n in notices:
        by_corp.setdefault(n["corp_code"], []).append(n)
    amap = {}
    for r in rows:
        o = origin[r["rcept_no"]]
        ns = [n["rcept_no"] for n in by_corp.get(r["corp_code"], []) if o[:8] <= n["rcept_dt"] <= f"{AS_OF:%Y%m%d}"]
        amap[r["rcept_no"]] = {"orig_rcept_no": o, "orig_rcept_dt": o[:8], "notices": ns}
    write_json(KQ_INTERIM / "s05_agm_map.json", amap)
    used = {n for v in amap.values() for n in v["notices"]}
    print(f"원본 제출일 ~ 기준일 안 소집공고: {len(used)}건 · 행별 개수 분포 "
          f"{dict(sorted(Counter(len(v['notices']) for v in amap.values()).items()))} · "
          f"원본≠목록행 {sum(v['orig_rcept_no'] != k for k, v in amap.items())}행")


if __name__ == "__main__":
    main()
