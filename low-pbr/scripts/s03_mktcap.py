"""s03 시가총액 — 종목별 일별 시가총액(CHECK) → 회차별 20거래일 일평균 (R3).

원천: CHECK /stock/m001/hist_info (유가) · /stock/m003/hist_info (코스닥), data_list=F12506,F15028,F16143,F15001
  F12506 입회일 · F15028 시가총액(원) · F16143 상장주식수 · F15001 종가
  한 종목 2020.09~2026.10 한 번에 (약 1,500행, 70KB). 이전상장 종목은 두 시장을 모두 받아 날짜로 합친다.

대상: universe_snap 의 보통주 전체 + pref_map 의 종류주.
일 사용량 한도(1GB/일, cust_id) 때문에 --max-mb 를 넘으면 멈춘다. 캐시가 있어 재실행하면 이어 받는다.

출력
  data/interim/mktcap_daily.csv   code, date, mktcap, shares, close, src(m001|m003)   (구간 날짜만)
  data/interim/mktcap_round.csv   round, code(보통주), n_days, mktcap_common, mktcap_pref, mktcap_avg
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ROOT, GatewayError, NotCached, call, rows  # noqa: E402

INTER = ROOT / "data" / "interim"
FIELDS = "F12506,F15028,F16143,F15001"
SDATE, EDATE = "20200901", "20261022"


def fetch_code(code: str, families: list[str], offline: bool = False) -> tuple[list[dict], int]:
    out, nbytes = [], 0
    for fam in families:
        try:
            d = call(f"/stock/{fam}/hist_info", offline=offline, jcode=code, sdate=SDATE, edate=EDATE, data_list=FIELDS)
        except NotCached:
            raise
        except GatewayError as e:
            if "유효하지" in str(e) or "jcode" in str(e):
                continue
            raise
        nbytes += len(json.dumps(d))
        for r in rows(d):
            if r.get("F12506"):
                out.append({"date": str(r["F12506"]), "mktcap": int(r.get("F15028") or 0),
                            "shares": int(r.get("F16143") or 0), "close": int(r.get("F15001") or 0), "src": fam})
    return out, nbytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=float, default=600)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cache-only", action="store_true",
                    help="네트워크 없이 캐시된 종목만으로 회차 평균을 만든다 (수집 중간 집계·웹페이지용)")
    args = ap.parse_args()

    rounds = list(csv.DictReader(open(INTER / "rounds.csv", encoding="utf-8")))
    cal = [r["date"] for r in csv.DictReader(open(INTER / "calendar.csv", encoding="utf-8"))]
    win = {}
    for r in rounds:
        i = cal.index(r["base_date"])
        win[r["round"]] = set(cal[i - 19: i + 1])
    need_days = set().union(*win.values())

    snap = list(csv.DictReader(open(INTER / "universe_snap.csv", encoding="utf-8")))
    mk_of = defaultdict(set)
    for s in snap:
        mk_of[s["code"]].add(s["market"])
    prefs = list(csv.DictReader(open(INTER / "pref_map.csv", encoding="utf-8")))
    for p in prefs:
        mk_of[p["pref_code"]] |= mk_of.get(p["common_code"], set()) or {"KOSPI", "KOSDAQ"}

    codes = sorted(mk_of)
    if args.limit:
        codes = codes[: args.limit]
    print(f"대상 {len(codes)}종목 (보통주 {len({s['code'] for s in snap})}, 종류주 {len(prefs)})")

    daily, total, empty, pending = [], 0, [], []
    for i, code in enumerate(codes, 1):
        fams = ["m001" if "KOSPI" in mk_of[code] else None, "m003" if "KOSDAQ" in mk_of[code] else None]
        try:
            rs, nb = fetch_code(code, [f for f in fams if f], offline=args.cache_only)
        except NotCached:
            pending.append(code)
            continue
        total += nb
        got = [r for r in rs if r["date"] in need_days]
        if not got:
            empty.append(code)
        daily += [{"code": code, **r} for r in got]
        if i % 100 == 0:
            print(f"  {i}/{len(codes)}  누적 {total / 1e6:.0f}MB  빈 종목 {len(empty)}", flush=True)
        if total / 1e6 > args.max_mb:
            print(f"--max-mb {args.max_mb} 도달 — {i}종목에서 멈춘다. 내일 다시 실행하면 캐시로 이어진다.")
            break

    with open(INTER / "mktcap_daily.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "date", "mktcap", "shares", "close", "src"])
        w.writeheader()
        w.writerows(sorted(daily, key=lambda r: (r["code"], r["date"])))

    # 회차별 평균: 보통주 + 종류주 (같은 날짜끼리 더한 뒤 20일 평균). 거래일 중 시세가 없는 날은 0 으로 보지 않고 빠진 날로 센다.
    by = defaultdict(dict)
    for r in daily:
        by[r["code"]][r["date"]] = r["mktcap"]
    pref_of = defaultdict(list)
    for p in prefs:
        pref_of[p["common_code"]].append(p["pref_code"])
    out = []
    for r in rounds:
        days = win[r["round"]]
        for code in {s["code"] for s in snap if s["round"] == r["round"]} - set(pending):
            c = [by[code][d] for d in days if d in by.get(code, {})]
            pv = [sum(by[p].get(d, 0) for p in pref_of.get(code, [])) for d in days if d in by.get(code, {})]
            out.append({"round": r["round"], "code": code, "n_days": len(c),
                        "mktcap_common": round(sum(c) / len(c)) if c else "",
                        "mktcap_pref": round(sum(pv) / len(pv)) if pv else 0,
                        "mktcap_avg": round((sum(c) + sum(pv)) / len(c)) if c else ""})
    with open(INTER / "mktcap_round.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(sorted(out, key=lambda r: (r["round"], r["code"])))
    print(f"미수집(캐시 없음) {len(pending)}종목")
    print(f"완료: 응답 {total / 1e6:.0f}MB · 일별 {len(daily)}행 · 회차행 {len(out)} · 시세 없는 종목 {len(empty)}")
    if empty:
        print("  시세 없음 예:", empty[:20])


if __name__ == "__main__":
    main()
