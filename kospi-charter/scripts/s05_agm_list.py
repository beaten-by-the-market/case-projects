"""s05 주주총회소집공고 목록 (최종본) — 코스피 행마다 '원본 제출일 ~ 기준일'

사용자 결정(2026-11-16)
  · 기간 시작 = 사업보고서 **원본 최초 접수일** — 목록 행이 정정본이면 DART family 의 가장 오래된 본문 접수번호(s03)
  · 셈 = **소집공고 접수일**이 [원본 접수일, 기준일] 안인 최종본 소집공고 수 (양끝 포함)

  · OpenDART list.json, pblntf_detail_ty='E006'(주주총회소집공고), last_reprt_at='Y'
  · 회사별로 부르지 않고 시장 전체를 3개월 구간으로 한 번에 받아(호출 수 ≈ 쪽 수) 코스피 회사만 거른다
  · 응답 페이지는 data/raw/opendart_list/E006_Y_*.json

출력
  data/interim/s05_agm_notices.json   기간 안 코스피 회사의 소집공고 최종본 (API 열 + amend_tag)
  data/interim/s05_agm_map.json       사업보고서 rcept_no → orig_rcept_no·orig_rcept_dt·notices[접수번호…]
"""
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, INTERIM, RAW, Http, dart_keys, parse_report_nm, read_json, write_json  # noqa: E402
from s01_list import API_COLS, LIST_URL, windows  # noqa: E402


def fetch(http, keys, b, e):
    rows, page, ki = [], 1, 0
    while True:
        f = RAW / "opendart_list" / f"E006_Y_{b:%Y%m%d}_{e:%Y%m%d}_p{page:03d}.json"
        if f.exists():
            j = read_json(f)
        else:
            j = http.get(LIST_URL, params=dict(crtfc_key=keys[ki], bgn_de=f"{b:%Y%m%d}", end_de=f"{e:%Y%m%d}",
                                               pblntf_detail_ty="E006", last_reprt_at="Y", page_no=page,
                                               page_count=100)).json()
            if j.get("status") == "020":
                ki += 1
                if ki >= len(keys):
                    raise SystemExit("OpenDART 키 전부 한도 초과(020)")
                continue
            if j.get("status") not in ("000", "013"):
                raise SystemExit(f"OpenDART 오류 {j.get('status')} {j.get('message')}")
            write_json(f, j)
        if j.get("status") == "013":
            break
        rows += j["list"]
        if page >= j["total_page"]:
            break
        page += 1
    print(f"  {b} ~ {e}: {len(rows)}건", flush=True)
    return rows


def orig_of(rno: str, page: dict | None) -> str:
    """가족(family) 본문 중 가장 오래된 접수번호. 화면이 없으면 행 자신."""
    fam = [f["rcpNo"] for f in (page or {}).get("family", [])]
    return min(fam + [rno])


def main():
    reports = read_json(INTERIM / "s01_reports.json")
    market = read_json(INTERIM / "s02_market.json")
    pages = read_json(INTERIM / "s03_main.json")
    kospi = [r for r in reports if market[r["rcept_no"]]["market"] == "코스피"]
    origin = {r["rcept_no"]: orig_of(r["rcept_no"], pages.get(r["rcept_no"])) for r in kospi}
    start = min(date(int(o[:4]), int(o[4:6]), int(o[6:8])) for o in origin.values())
    print(f"코스피 {len(kospi)}행 · 소집공고 조회 {start} ~ {AS_OF}")

    http, keys = Http(delay=0.35), dart_keys()
    allrows = []
    for b, e in windows(start, AS_OF):
        allrows += fetch(http, keys, b, e)
    corps = {r["corp_code"] for r in kospi}
    seen, notices = set(), []
    for x in allrows:
        if x["corp_code"] in corps and x["rcept_no"] not in seen:
            seen.add(x["rcept_no"])
            p = parse_report_nm(x["report_nm"])
            notices.append({**{c: x.get(c, "") for c in API_COLS}, "amend_tag": p["amend_tag"]})
    notices.sort(key=lambda x: x["rcept_no"])
    write_json(INTERIM / "s05_agm_notices.json", notices)
    print(f"시장 전체 {len(allrows)}건 → 코스피 회사 {len(notices)}건")
    print("  보고서명:", Counter(n["report_nm"] for n in notices).most_common(8))

    by_corp = {}
    for n in notices:
        by_corp.setdefault(n["corp_code"], []).append(n)
    amap = {}
    for r in kospi:
        o = origin[r["rcept_no"]]
        ns = [n["rcept_no"] for n in by_corp.get(r["corp_code"], []) if o[:8] <= n["rcept_dt"] <= f"{AS_OF:%Y%m%d}"]
        amap[r["rcept_no"]] = {"orig_rcept_no": o, "orig_rcept_dt": o[:8], "notices": ns}
    write_json(INTERIM / "s05_agm_map.json", amap)
    used = {n for v in amap.values() for n in v["notices"]}
    print(f"원본 제출일 ~ 기준일 안 소집공고: {len(used)}건 · 행별 개수 분포 "
          f"{dict(sorted(Counter(len(v['notices']) for v in amap.values()).items()))} · "
          f"원본≠목록행 {sum(v['orig_rcept_no'] != k for k, v in amap.items())}행")


if __name__ == "__main__":
    main()
