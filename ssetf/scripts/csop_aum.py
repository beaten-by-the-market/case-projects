"""
CSOP 홍콩 레버리지/인버스 상품(삼성·하이닉스 2x/-2x)의 Total NAV(AUM) 수집.

Total NAV(AUM) = 단위당 NAV × 발행좌수(Outstanding Units).
두 조각을 어디서 얻느냐에 따라 소스가 둘이다:

┌─ --source ice  (기본, 토큰 불필요) ───────────────────────────────────┐
│ 단위당 NAV를 ICE iNAV 공개 API에서 받는다(토큰·쿠키 불필요, 실시간). │
│   GET https://inav.ice.com/api/1/csop/application/index/quote          │
│       ?symbol=<코드>&language=en                                       │
│   응답: INTRA_DAY_ESTIMATED_NAV_PER_UNIT (통화별), INTRA_DAY_MARKET_PRICE│
│   · 삼성(7747/9747)은 USD·HKD 둘 다, 하이닉스(7709)·인버스는 HKD만.     │
│ 발행좌수는 ICE에 없다 → --units 로 주거나 캐시(data/csop_units.json)    │
│ 사용, 없으면 DEFAULT_UNITS 시드값(경고와 함께). 좌수는 설정/환매로     │
│ 매일 조금씩 바뀌니 가끔 CSOP 페이지에서 읽어 --units로 갱신 권장.       │
└───────────────────────────────────────────────────────────────────────┘
┌─ --source hkex (토큰 필요) ────────────────────────────────────────────┐
│ HKEX 위젯 getequityquote가 nav·amt_os(좌수)를 한 번에 준다 →           │
│ Total NAV = nav × amt_os. hkex_history.py와 같은 위젯·token.            │
│ (좌수까지 자동이라 --units 불필요. 대신 DevTools 토큰 캡처 필요.)       │
└───────────────────────────────────────────────────────────────────────┘

※ 왜 csopasset.com을 직접 안 긁나: 'Total NAV' 값은 /asset/lai/js/<slug>.js가
  주입하는데 그 경로 전체가 WAF로 막혀(비브라우저 302, Googlebot 403) HTTP
  스크래핑 불가. 그래서 ICE(무토큰) 또는 HKEX(토큰)로 우회 계산한다.

■ 듀얼카운터 합산 금지: 삼성 2x는 '하나의 펀드', 7747(HKD)·9747(USD)은 통화만
  다른 같은 값(좌수 공유). 더하면 이중계상. 하이닉스 2x(7709)는 HKD 카운터만.

■ 검증(2026-07-03 CSOP 공시): 삼성 NAV/unit 17.67 × 177,500,000좌
    = 3,135,908,512 USD = CSOP 'Total NAV (USD)'. ✅

사용 예:
    python csop_aum.py                                  # ICE, 시드좌수로 삼성·하이닉스
    python csop_aum.py --units 7747=177500000 7709=8000000   # 좌수 갱신(캐시에 저장)
    python csop_aum.py 9747 7747 7709 9347 7347         # 전부
    python csop_aum.py --source hkex --token "<TOKEN>"  # HKEX 토큰 경로(좌수 자동)
"""

import argparse
import json
import os
import sys
from datetime import date

import pandas as pd
import requests

# HKEX 소스에서만 쓰는 검증된 위젯 호출부(JSONP·token·에러처리) 재사용
from hkex_history import _get

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ICE_URL = "https://inav.ice.com/api/1/csop/application/index/quote"
HKD_PER_USD = 7.8  # 하이닉스처럼 HKD만 있는 상품의 대략적 USD 환산(페그). 정밀 환산은 naver_fx.py.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
    "Accept": "*/*",
}

# 종목 카탈로그. counter_ccy=그 카운터의 NAV 표기통화. same_fund=짝 카운터(합산금지 안내).
PRODUCTS = {
    "9747": {"name": "CSOP Samsung 2x", "underlying": "Samsung Electronics",
             "lev": "2x", "counter_ccy": "USD", "same_fund": "7747",
             "csop_url": "https://www.csopasset.com/en/products/hk-smsn-2l"},
    "7747": {"name": "CSOP Samsung 2x", "underlying": "Samsung Electronics",
             "lev": "2x", "counter_ccy": "HKD", "same_fund": "9747",
             "csop_url": "https://www.csopasset.com/en/products/hk-smsn-2l"},
    "7709": {"name": "CSOP SK Hynix 2x", "underlying": "SK Hynix",
             "lev": "2x", "counter_ccy": "HKD", "same_fund": None,
             "csop_url": "https://www.csopasset.com/en/products/hk-skhy-2l"},
    "9347": {"name": "CSOP Samsung -2x Inverse", "underlying": "Samsung Electronics",
             "lev": "-2x", "counter_ccy": "USD", "same_fund": "7347",
             "csop_url": "https://www.csopasset.com/en/products/hk-smsn-2i"},
    "7347": {"name": "CSOP Samsung -2x Inverse", "underlying": "Samsung Electronics",
             "lev": "-2x", "counter_ccy": "HKD", "same_fund": "9347",
             "csop_url": "https://www.csopasset.com/en/products/hk-smsn-2i"},
}
DEFAULT_SYMS = ["9747", "7709"]  # 삼성 USD 표기 + 하이닉스(HKD only)

# 발행좌수 시드값(마지막으로 확인된 값). --units로 갱신하면 캐시에 덮어써진다.
# 삼성 2x는 7747·9747이 좌수를 공유(같은 펀드).
DEFAULT_UNITS = {
    "7747": {"units": 177500000, "asof": "2026-07-03"},
    "9747": {"units": 177500000, "asof": "2026-07-03"},
    # 7709(하이닉스)·9347/7347(인버스)은 미확인 → --units로 넣어야 AUM 산출됨
}
UNITS_CACHE = "csop_units.json"

# Windows 콘솔(cp949)에서 한글/CSV 로그가 깨지지 않도록 UTF-8로 재설정
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _num(x):
    """콤마 섞인 문자열 숫자 -> float. 빈값/None -> NaN."""
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return float("nan")


# ── ICE (무토큰) ────────────────────────────────────────────────────────
def get_ice_quote(sym: str) -> dict:
    """ICE iNAV: 통화별 단위당 NAV·시장가. 토큰/쿠키 불필요."""
    r = requests.get(ICE_URL, params={"symbol": str(sym), "language": "en"},
                     headers=HEADERS, timeout=20)
    r.raise_for_status()
    q = r.json().get("quote", {})
    ccys = q.get("columnLabels", [])[3:]        # ['','DATE','TIME', <통화들...>]
    nav, mkt, asof = {}, {}, None
    for row in q.get("rows", []):
        vals = dict(zip(ccys, (_num(v) for v in row.get("values", []))))
        if row.get("label") == "INTRA_DAY_ESTIMATED_NAV_PER_UNIT":
            nav = vals
            asof = f"{row.get('date')} {row.get('time')}".strip()
        elif row.get("label") == "INTRA_DAY_MARKET_PRICE":
            mkt = vals
    if not nav:
        raise RuntimeError(f"{sym}: ICE NAV 없음")
    return {"nav": nav, "mkt": mkt, "asof": asof}


# ── HKEX (토큰) ─────────────────────────────────────────────────────────
def get_hkex_quote(sym: str, token: str) -> dict:
    """HKEX 위젯: nav(단위당)·amt_os(발행좌수)·ISIN 등."""
    d = _get("getequityquote", {"sym": str(sym).lstrip("0") or "0",
                                "token": token, "lang": "eng"})
    q = d.get("quote", {})
    as_of = next((q[k] for k in q if "date" in k.lower() and q.get(k)), None)
    return {"nav": _num(q.get("nav")), "units": _num(q.get("amt_os")),
            "isin": q.get("isin"), "ccy": q.get("ccy"),
            "mgmt_fee": q.get("management_fee"), "asof": as_of}


def usd_equiv(total: float, ccy: str) -> float:
    """카운터 통화 Total NAV -> USD 근사(HKD는 페그). USD면 그대로."""
    if ccy == "USD":
        return total
    if ccy == "HKD":
        return total / HKD_PER_USD
    return float("nan")


# ── 발행좌수 캐시 ───────────────────────────────────────────────────────
def load_units(outdir: str) -> dict:
    path = os.path.join(outdir, UNITS_CACHE)
    cache = {k: dict(v) for k, v in DEFAULT_UNITS.items()}   # 시드 복사
    if os.path.exists(path):
        try:
            cache.update(json.load(open(path, encoding="utf-8")))
        except (ValueError, OSError):
            pass
    return cache


def save_units(outdir: str, cache: dict):
    path = os.path.join(outdir, UNITS_CACHE)
    json.dump(cache, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def parse_units_args(pairs) -> dict:
    """'7747=177500000' / '7747:177500000' 형태를 {sym: units}로."""
    out = {}
    for p in pairs or []:
        for sep in ("=", ":"):
            if sep in p:
                s, n = p.split(sep, 1)
                out[s.strip()] = _num(n)
                break
        else:
            print(f"[무시] --units 형식오류: {p} (예: 7747=177500000)", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description="CSOP 홍콩 L&I 상품 Total NAV(AUM) 수집")
    ap.add_argument("syms", nargs="*", default=DEFAULT_SYMS,
                    help=f"종목코드(기본: {' '.join(DEFAULT_SYMS)}). 후보: {', '.join(PRODUCTS)}")
    ap.add_argument("--source", choices=["ice", "hkex"], default="ice",
                    help="NAV 소스: ice=무토큰(좌수는 --units/캐시), hkex=토큰(좌수 자동)")
    ap.add_argument("--units", nargs="*", default=[],
                    help="발행좌수 지정/갱신: '7747=177500000 7709=8000000' (캐시에 저장)")
    ap.add_argument("--token", default=os.environ.get("HKEX_TOKEN"),
                    help="HKEX 위젯 token(--source hkex일 때). 환경변수 HKEX_TOKEN 가능")
    ap.add_argument("--outdir", default="data", help="저장 폴더")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # 발행좌수: --units > 캐시 > 시드
    units_cache = load_units(args.outdir)
    cli_units = parse_units_args(args.units)
    if cli_units:
        today = date.today().isoformat()
        for s, n in cli_units.items():
            units_cache[s] = {"units": n, "asof": today}
            # 같은 펀드 짝 카운터도 동일 좌수로 동기화
            twin = PRODUCTS.get(s, {}).get("same_fund")
            if twin:
                units_cache[twin] = {"units": n, "asof": today}
        save_units(args.outdir, units_cache)
        print(f"[좌수 갱신·저장] {os.path.join(args.outdir, UNITS_CACHE)}")

    if args.source == "hkex" and not args.token:
        sys.exit("오류: --source hkex 는 --token 필요 (HKEX getequityquote 토큰)")
    if args.source == "hkex":
        args.token = args.token.replace("%2b", "+").replace("%2B", "+")

    rows, dup_funds = [], {}
    for sym in args.syms:
        meta = PRODUCTS.get(sym, {})
        ccy = meta.get("counter_ccy")
        try:
            if args.source == "ice":
                iq = get_ice_quote(sym)
                # counter 통화 NAV(없으면 아무 통화나), USD NAV(있으면)
                nav_ct = iq["nav"].get(ccy) if ccy else next(iter(iq["nav"].values()), float("nan"))
                nav_usd = iq["nav"].get("USD")
                u = units_cache.get(sym, {})
                units, u_asof = u.get("units", float("nan")), u.get("asof")
                total = (nav_ct or float("nan")) * units
                total_usd = (nav_usd * units) if nav_usd else usd_equiv(total, ccy)
                isin, mgmt, nav_asof = None, None, iq["asof"]
                if not cli_units and u_asof:
                    print(f"  · {sym} 좌수 {units:,.0f} (as of {u_asof}, 캐시/시드값 — "
                          f"필요시 --units로 갱신)", file=sys.stderr)
            else:  # hkex
                hq = get_hkex_quote(sym, args.token)
                nav_ct, units = hq["nav"], hq["units"]
                total = nav_ct * units
                nav_usd = nav_ct if (ccy == "USD" or hq["ccy"] == "USD") else None
                total_usd = usd_equiv(total, ccy or hq["ccy"])
                isin, mgmt, nav_asof = hq["isin"], hq["mgmt_fee"], hq["asof"]
                ccy = ccy or hq["ccy"]
        except Exception as e:
            print(f"[실패] {sym}: {e}", file=sys.stderr)
            continue

        row = {
            "Symbol": f"{sym.zfill(4)}.HK", "Product": meta.get("name"),
            "Underlying": meta.get("underlying"), "Leverage": meta.get("lev"),
            "CounterCcy": ccy, "NAV": nav_ct, "OutstandingUnits": units,
            "TotalNAV": total, "TotalNAV_USD": total_usd,
            "Source": args.source, "AsOf": nav_asof, "ISIN": isin,
            "MgmtFee": mgmt, "CSOP_URL": meta.get("csop_url"),
        }
        rows.append(row)
        u_str = f"{units:,.0f}" if units == units else "?(좌수미상 --units 필요)"
        t_str = f"{total:,.0f}" if total == total else "N/A"
        print(f"[{row['Symbol']}] {row['Product']}  "
              f"TotalNAV({ccy})={t_str}  (≈${total_usd:,.0f})  "
              f"NAV={nav_ct}  좌수={u_str}" + (f"  [{nav_asof}]" if nav_asof else ""))

        twin = meta.get("same_fund")
        if twin and twin in [s for s in args.syms if s != sym]:
            dup_funds[meta["name"]] = True

    for fund in dup_funds:
        print(f"[주의] '{fund}'는 듀얼카운터(동일 펀드). Total NAV 카운터별 합산 금지 "
              f"— 통화만 다른 같은 값입니다.")

    if rows:
        out = os.path.join(args.outdir, "csop_aum_snapshot.csv")
        pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[저장] {out}")
        print("[검증팁] 의심되면 각 행 CSOP_URL의 'Total NAV'와 눈으로 대조하세요.")


if __name__ == "__main__":
    main()
