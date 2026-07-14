"""코스닥 애프터마켓 연구. 데이터 수집 (D1~D4).

  D1  KRX 코스닥(m003)·코스피(m001)  종목×일별 거래대금/거래량   2024-01-01 ~ 2026-06-30
  D2  NXT 코스닥(m223)·코스피(m222)  종목×일별                2025-03-24 ~ 2026-06-30
  D3  일별 전체 공시 (제목·시각·종목코드)                        2024-01-01 ~ 2026-06-30
  D4  종목 마스터 (종목명·시총·증권그룹·상장주식수)                 현재 스냅샷

실행: 등록 IP · 샌드박스 밖.
    python collect.py            # 전체 (체크포인트에서 이어받음)
    python collect.py --only d3  # 일부만

## 반드시 지키는 안전장치 (전부 이 레포의 실제 사고에서 나온 것)
1. 바이트 미터 + 700MB 자체 상한. 일 한도 1e9 를 넘기면 **그날 다른 모든 작업의 호출까지 죽는다**.
2. success:false 를 빈 결과로 흘리지 않는다. 과거에 코스닥 305일이 빈 값인 채 "완료"가 찍혔다.
   단 휴장일은 "No Data" 로 오므로 **거래일 달력(m002)으로 거래일에만 호출**한다.
3. data_list 는 없는 F-code 를 조용히 버린다. 시작 시 요청·반환 필드를 대조하고, 안 맞으면 중단.
4. 완료 시 커버 거래일 수를 출력해 완전성을 검사한다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import load_env, quote_codelist, _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()

BASE = "https://checkapi.koscom.co.kr"
ENV = load_env()
CID, KEY = ENV["CHECK_CUST_ID"], ENV["CHECK_AUTH_KEY"]

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)

KRX_START, END = "20240101", "20260630"
NXT_START = "20250324"           # NXT 첫 거래일 (실측)

BYTE_CAP = 700_000_000           # 일 한도 1e9 보호
TS_INTERVAL = 1.15               # 시계열 endpoint 초당 1회 제한

# 단축코드 · 매도거래량 · 매수거래량 · 매도거래대금 · 매수거래대금 (투자자번호 12 = 전체)
# 거래대금 = (매도대금+매수대금)/2 · 거래여부 = 거래량>0.  ⚠ F06506 은 존재하지 않는 코드다.
SLIM = ["F16013", "F06505_12", "F06507_12", "F06509_12", "F06510_12"]

_bytes = 0
_last_ts = 0.0


class Quota(Exception):
    """일 사용량 한도 또는 자체 상한 도달."""


class ApiError(Exception):
    """success=false 또는 네트워크 오류. 절대 빈 결과로 흘리지 않는다."""


def call(apiurl, params=None, timeseries=False, tries=4):
    """No Data(휴장일·해당없음)는 [] 로, 그 외 실패는 예외로."""
    global _bytes, _last_ts
    if _bytes > BYTE_CAP:
        raise Quota(f"자체 상한 {BYTE_CAP:,}B 도달 (누적 {_bytes:,}B)")
    if timeseries:
        gap = time.time() - _last_ts
        if gap < TS_INTERVAL:
            time.sleep(TS_INTERVAL - gap)
    body = urllib.parse.urlencode({"cust_id": CID, "auth_key": KEY, **(params or {})}).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(BASE + apiurl, data=body)
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read()
            _bytes += len(raw)
            if timeseries:
                _last_ts = time.time()
            payload = json.loads(raw)
            if payload.get("success"):
                return payload["results"]
            msg = json.dumps(payload.get("message") or payload, ensure_ascii=False)
            if "No Data" in msg:
                return []                              # 휴장일 / 해당 없음
            if "사용량" in msg or "초과" in msg:
                raise Quota(msg)
            raise ApiError(f"{apiurl} {params} -> {msg}")
        except (Quota, ApiError):
            raise
        except Exception as exc:
            if attempt == tries - 1:
                raise ApiError(f"{apiurl} {params} -> {exc}")
            time.sleep(1.5 * (attempt + 1))


def trading_days(sdate, edate):
    """거래일 달력. 코스피 지수(m002) 일별정보. 휴장일에 호출을 낭비하지 않기 위해."""
    days = set()
    y0, y1 = int(sdate[:4]), int(edate[:4])
    for y in range(y0, y1 + 1):                        # hist_info 는 1년 초과 조회 불가
        s = max(sdate, f"{y}0101")
        e = min(edate, f"{y}1231")
        rows = call("/stock/m002/hist_info", {"jcode": "1", "sdate": s, "edate": e}, timeseries=True)
        days |= {str(r["F12506"]) for r in rows}
    return sorted(days)


def probe_slim():
    """data_list 가 실제로 먹히는지. 안 먹으면 123필드가 와서 한도가 즉시 터진다."""
    for fam in ["m003", "m001", "m223", "m222"]:
        rows = call(f"/stock/{fam}/rank_invest_date", {
            "criteria_code": "F06508_12", "sort_code": "0",
            "sdate": "20260630", "edate": "20260630", "data_list": ",".join(SLIM)})
        if not rows:
            raise ApiError(f"probe {fam}: 빈 응답")
        keys = set(rows[0]) - {"SDATE", "EDATE"}
        if keys != set(SLIM):
            raise ApiError(f"probe {fam}: data_list 불일치. 요청={SLIM} 반환={sorted(keys)}")
    print(f"[probe] data_list OK. 4개 패밀리 전부 {len(SLIM)}필드만 반환")


def _ckpt(name):
    p = DATA / f".{name}.done"
    done = set(p.read_text().split()) if p.exists() else set()
    return p, done


def collect_daily(tag, fams, days):
    """rank_invest_date. 하루 1콜로 전종목. 날짜별 체크포인트."""
    out = DATA / f"{tag}.csv"
    ck, done = _ckpt(tag)
    todo = [d for d in days if d not in done]
    print(f"[{tag}] 거래일 {len(days)} · 남은 {len(todo)}")
    new = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "fam", "code", "vol_sell", "vol_buy", "amt_sell", "amt_buy"])
        for i, d in enumerate(todo, 1):
            for fam in fams:
                rows = call(f"/stock/{fam}/rank_invest_date", {
                    "criteria_code": "F06508_12", "sort_code": "0",
                    "sdate": d, "edate": d, "data_list": ",".join(SLIM)})
                for r in rows:
                    w.writerow([d, fam, r.get("F16013"), r.get("F06505_12"), r.get("F06507_12"),
                                r.get("F06509_12"), r.get("F06510_12")])
            f.flush()
            with ck.open("a") as c:
                c.write(d + "\n")
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  {d}  누적 {_bytes/1e6:.0f}MB")


def collect_gongsi(days):
    out = DATA / "gongsi.csv"
    ck, done = _ckpt("gongsi")
    todo = [d for d in days if d not in done]
    print(f"[gongsi] 거래일 {len(days)} · 남은 {len(todo)}")
    new = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "code", "mtvcd", "title"])
        for i, d in enumerate(todo, 1):
            rows = call("/news/gongsi/gongsi_basic", {"sdate": d, "edate": d, "dcnt": "3000"})
            if len(rows) >= 3000:
                raise ApiError(f"gongsi {d}: dcnt 상한 도달({len(rows)}). 잘렸을 수 있다. dcnt 상향 필요")
            for r in rows:
                w.writerow([d, r.get("TIME"), (r.get("NCD") or "").strip(),
                            r.get("MTVCD"), (r.get("TITLE") or "").strip()])
            f.flush()
            with ck.open("a") as c:
                c.write(d + "\n")
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  {d}  누적 {_bytes/1e6:.0f}MB")


def collect_d5(days):
    """코스닥 전종목 일별 OHLC. H5(가격충격) 용. rank_invest_date 에는 가격이 없다.

    코스닥 과거 일별 전종목 시세를 한 번에 주는 endpoint 는 없다(hist_info_port 는 m003 에서 404).
    → 종목별 hist_info 루프가 유일한 길. 시계열이므로 rate limit 1.15초 적용.
    F15023(거래대금)도 함께 받아 rank_invest_date 거래대금을 **교차검증**한다.
    """
    fields = ["F12506", "F15001", "F15009", "F15010", "F15011", "F15015", "F15023", "F15028"]

    # 유니버스 = 현재 상장분(code_info) ∪ 기간 중 거래된 종목(daily_krx).
    # code_info 는 현재 상장분만 준다 → 상폐 종목이 통째로 빠지고, 그게 하필 저유동성·부실 종목이라
    # 생존편향이 생긴다. hist_info 는 상폐 종목의 과거 시세를 그대로 보관하므로 코드만 알면 받아진다.
    codes = {str(r["F16013"]) for r in call("/stock/m003/code_info")}
    krx = DATA / "daily_krx.csv"
    if krx.exists():
        with krx.open(encoding="utf-8") as f:
            codes |= {r["code"] for r in csv.DictReader(f) if r["fam"] == "m003"}
    codes = sorted(codes)
    out = DATA / "ohlc_kosdaq.csv"
    ck, done = _ckpt("ohlc_kosdaq")
    todo = [c for c in codes if c not in done]
    print(f"[ohlc] 코스닥 {len(codes)}종목 · 남은 {len(todo)}  (~{len(todo)*1.15/60:.0f}분)")
    new = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["code", "date", "close", "open", "high", "low", "vol", "amt", "mktcap"])
        for i, code in enumerate(todo, 1):
            rows = call("/stock/m003/hist_info", {
                "jcode": code, "sdate": days[0], "edate": days[-1],
                "data_list": ",".join(fields)}, timeseries=True)
            for r in rows:
                w.writerow([code, r.get("F12506"), r.get("F15001"), r.get("F15009"),
                            r.get("F15010"), r.get("F15011"), r.get("F15015"),
                            r.get("F15023"), r.get("F15028")])
            f.flush()
            with ck.open("a") as c:
                c.write(code + "\n")
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  누적 {_bytes/1e6:.0f}MB")


def collect_master():
    """종목 마스터. 종목명·시총·증권그룹(ETF/ETN 제외용)·상장주식수. 현재 상장분만."""
    out = DATA / "master.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fam", "code", "name", "group", "mktcap", "shares"])
        for fam in ["m003", "m001"]:
            codes = [str(r["F16013"]) for r in call(f"/stock/{fam}/code_info")]
            print(f"[master] {fam} 종목 {len(codes)}")
            for i in range(0, len(codes), 500):        # 영숫자 코드는 작은따옴표 필수 (코스콤 버그 우회)
                chunk = codes[i:i + 500]
                rows = call(f"/stock/{fam}/basic_info_all_port", {
                    "codelist": quote_codelist(chunk),
                    "data_list": "F16013,F16002,F34501,F15028,F16143"})
                for r in rows:
                    w.writerow([fam, r.get("F16013"), r.get("F16002"), r.get("F34501"),
                                r.get("F15028"), r.get("F16143")])
    print(f"[master] 저장 {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=["d1", "d2", "d3", "d4"])
    args = ap.parse_args()

    probe_slim()
    days = trading_days(KRX_START, END)
    print(f"[달력] {KRX_START}~{END} 거래일 {len(days)}일")
    nxt_days = [d for d in days if d >= NXT_START]

    try:
        if "d4" in args.only:
            collect_master()
        if "d1" in args.only:
            collect_daily("daily_krx", ["m003", "m001"], days)
        if "d2" in args.only:
            collect_daily("daily_nxt", ["m223", "m222"], nxt_days)
        if "d3" in args.only:
            collect_gongsi(days)
        if "d5" in args.only:
            collect_d5(days)
    except Quota as q:
        print(f"\n!! 한도 도달로 중단: {q}")
        print("   체크포인트는 남았다. 내일(한도 리셋 후) 같은 명령으로 이어받으면 된다.")
        sys.exit(2)

    # ── 완전성 검사 (여기서 조용한 누락을 잡는다) ──
    print(f"\n{'='*60}\n누적 수신 {_bytes/1e6:,.0f} MB / 한도 1,000 MB")
    for tag, expect in [("daily_krx", len(days)), ("daily_nxt", len(nxt_days)),
                        ("gongsi", len(days))]:
        _, done = _ckpt(tag)
        mark = "OK" if len(done) == expect else "!! 누락"
        print(f"  {tag:11s} {len(done):4d}/{expect:4d} 거래일  {mark}")


if __name__ == "__main__":
    main()
