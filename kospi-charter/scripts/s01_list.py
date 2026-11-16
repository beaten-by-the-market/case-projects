"""s01 최근 1년 사업보고서 목록 — OpenDART list.json (최종보고서만)

  · pblntf_detail_ty='A001'(사업보고서), last_reprt_at='Y'  ← OpenDartReader dart.list(..., final=True) 와 같다
  · 회사를 지정하지 않으면 검색기간이 3개월로 제한된다 → 3개월 이하 구간으로 쪼개 부른다
  · A001 에는 '사업보고서제출기한연장신고서'도 들어 있다 → 목록에서는 빼고 개수만 기록한다
  · 응답 페이지는 data/raw/opendart_list/ 에 그대로 저장한다 (다시 돌리면 캐시를 읽는다)

  · 한 회사가 기간 안에 사업보고서를 여러 번 냈으면 **가장 최근 것 하나만** 남긴다 (사용자 지시 2026-11-16)
    '최근' = 결산기(report_period)가 가장 늦은 것 → 같으면 접수번호가 늦은 것
    (옛 사업연도 보고서의 늦은 정정본, 6개월 결산 리츠의 앞 기수가 빠진다 — logs/s01_dropped_older.csv)

출력
  data/interim/s01_list_api.json      API 가 준 행 그대로 (연장신고서 포함)
  data/interim/s01_reports_all.json   사업보고서 전부 + 보고서명 해석(amend_tag·report_period·fiscal_year·settle_month)
  data/interim/s01_reports.json       위에서 회사별 가장 최근 1건

사용법
    python scripts/s01_list.py            # 캐시가 있으면 그대로 쓴다
    python scripts/s01_list.py --refresh  # 캐시를 무시하고 다시 받는다
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, BGN, INTERIM, RAW, Http, dart_keys, parse_report_nm, read_json, write_json  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
API_COLS = ["corp_code", "corp_name", "stock_code", "corp_cls", "report_nm", "rcept_no", "flr_nm", "rcept_dt", "rm"]


def windows(bgn: date, end: date) -> list[tuple[date, date]]:
    """[bgn, end] 를 '3개월 - 1일' 이하 구간으로 자른다 (11-16 → 02-15, 02-16 → 05-15 …)."""
    out, s = [], bgn
    while s <= end:
        m = s.month + 3
        y = s.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        try:
            e = date(y, m, s.day) - timedelta(days=1)
        except ValueError:                       # 31일 등 → 말일 다음날 기준
            e = date(y, m + 1 if m < 12 else 1, 1) - timedelta(days=1)
        e = min(e, end)
        out.append((s, e))
        s = e + timedelta(days=1)
    return out


def fetch_window(http: Http, keys: list[str], b: date, e: date, refresh: bool) -> list[dict]:
    rows, page, ki = [], 1, 0
    while True:
        f = RAW / "opendart_list" / f"A001_Y_{b:%Y%m%d}_{e:%Y%m%d}_p{page:03d}.json"
        if f.exists() and not refresh:
            j = read_json(f)
        else:
            params = dict(crtfc_key=keys[ki], bgn_de=f"{b:%Y%m%d}", end_de=f"{e:%Y%m%d}",
                          pblntf_detail_ty="A001", last_reprt_at="Y", page_no=page, page_count=100)
            j = http.get(LIST_URL, params=params).json()
            if j.get("status") == "020":         # 키 일일 한도 → 다음 키
                ki += 1
                if ki >= len(keys):
                    raise SystemExit("OpenDART 키 전부 한도 초과(020) — 내일 다시 실행")
                continue
            if j.get("status") not in ("000", "013"):
                raise SystemExit(f"OpenDART 오류 {j.get('status')} {j.get('message')}")
            write_json(f, j)
        if j.get("status") == "013":             # 조회된 데이터가 없음
            break
        rows += j["list"]
        print(f"  {b} ~ {e}  page {page}/{j['total_page']}  (구간 {j['total_count']}건)", flush=True)
        if page >= j["total_page"]:
            break
        page += 1
    return rows


def main(refresh: bool = False):
    keys = dart_keys()
    http = Http(delay=0.35)
    print(f"조회기간 {BGN} ~ {AS_OF} (기준일 {AS_OF}), 최종보고서만")
    api_rows = []
    for b, e in windows(BGN, AS_OF):
        api_rows += fetch_window(http, keys, b, e, refresh)

    seen, dup = set(), 0
    uniq = []
    for r in api_rows:
        if r["rcept_no"] in seen:
            dup += 1
            continue
        seen.add(r["rcept_no"])
        uniq.append({c: r.get(c, "") for c in API_COLS})
    write_json(INTERIM / "s01_list_api.json", uniq)

    reports, ext = [], 0
    for r in uniq:
        p = parse_report_nm(r["report_nm"])
        if p["form_nm"] != "사업보고서":         # 사업보고서제출기한연장신고서 등
            ext += 1
            continue
        r = dict(r, stock_code=r["stock_code"].strip(), **p)
        reports.append(r)
    reports.sort(key=lambda r: (r["rcept_dt"], r["rcept_no"]))
    write_json(INTERIM / "s01_reports_all.json", reports)

    # 회사(corp_code)마다 가장 최근 사업보고서 하나만 (사용자 지시 2026-11-16)
    # '최근' = 결산기(report_period)가 가장 늦은 것, 같으면 접수번호가 늦은 것.
    # 접수일로만 고르면 옛 사업연도 보고서의 늦은 정정본이 이길 수 있다 → 결산기를 먼저 본다.
    latest = {}
    for r in reports:
        k = (r["report_period"] or "", r["rcept_no"])
        if r["corp_code"] not in latest or k > latest[r["corp_code"]][0]:
            latest[r["corp_code"]] = (k, r)
    keep = {v[1]["rcept_no"] for v in latest.values()}
    dropped = [r for r in reports if r["rcept_no"] not in keep]
    by_rcept = {}
    for r in reports:
        if r["corp_code"] not in by_rcept or r["rcept_no"] > by_rcept[r["corp_code"]]["rcept_no"]:
            by_rcept[r["corp_code"]] = r
    differ = sum(by_rcept[c]["rcept_no"] not in keep for c in by_rcept)
    reports = [r for r in reports if r["rcept_no"] in keep]
    write_json(INTERIM / "s01_reports.json", reports)
    import csv
    from _common import LOGS
    LOGS.mkdir(exist_ok=True)
    with open(LOGS / "s01_dropped_older.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=API_COLS + ["kept_rcept_no", "kept_report_nm"], extrasaction="ignore")
        w.writeheader()
        for r in dropped:
            k = latest[r["corp_code"]][1]
            w.writerow(dict(r, kept_rcept_no=k["rcept_no"], kept_report_nm=k["report_nm"]))

    from collections import Counter
    print(f"API 행 {len(api_rows)} (중복 {dup}) → 사업보고서 {len(reports) + len(dropped)}건, "
          f"제외(연장신고서 등) {ext}건")
    print(f"회사별 최근 1건만: {len(reports)}사 · 뺀 옛 보고서 {len(dropped)}건 (logs/s01_dropped_older.csv) · "
          f"접수일 기준으로 골랐다면 달라졌을 회사 {differ}사")
    print("  정정 접두어:", dict(Counter(r["amend_tag"] or "(없음)" for r in reports)))
    print("  corp_cls(현재 기준):", dict(Counter(r["corp_cls"] for r in reports)))
    print("  사업연도:", dict(sorted(Counter(r["fiscal_year"] for r in reports).items())))
    return reports


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    main(ap.parse_args().refresh)
