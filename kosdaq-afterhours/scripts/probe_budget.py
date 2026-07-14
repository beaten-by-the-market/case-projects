"""수집 전 바이트 예산 실측. 1GB/일 한도 안에 들어오는지 확인한다.

각 endpoint를 딱 1회씩 호출해 **원시 응답 바이트**를 재고, 계획된 콜 수로 곱해 총량을 추정한다.
동시에 data_list 가 실제로 먹히는지(= 요청 필드만 오는지) 대조한다.
data_list 가 조용히 무시되면 123필드가 와서 총량이 20배가 된다 → 여기서 반드시 잡는다.

실행: 등록 IP · 샌드박스 밖.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import load_env, _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
BASE = "https://checkapi.koscom.co.kr"
ENV = load_env()

# 거래대금 = (매도대금 + 매수대금)/2. 거래여부는 거래량>0.
SLIM = ["F16013", "F06505_12", "F06507_12", "F06509_12", "F06510_12"]

D = "20260710"          # 최근 거래일 1일 표본
TRADING_DAYS = 245      # 2025-07-01 ~ 2026-07-10 대략


def raw_call(apiurl: str, params: dict) -> tuple[int, dict]:
    """원시 응답 바이트 수와 파싱 결과를 함께 돌려준다."""
    body = json.dumps({"cust_id": ENV["CHECK_CUST_ID"],
                       "auth_key": ENV["CHECK_AUTH_KEY"], **params}).encode()
    req = urllib.request.Request(BASE + apiurl, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read()
    return len(blob), json.loads(blob)


def check(res: dict, apiurl: str) -> list:
    """success:false 를 빈 결과로 흘리지 않는다 (한도초과·rate limit이 여기로 온다)."""
    if isinstance(res, dict) and res.get("success") is False:
        msg = res.get("message", "")
        if "No Data" in str(msg):
            return []
        raise RuntimeError(f"{apiurl} 실패: {msg}")
    return res.get("results") or res.get("result") or []


def probe(label: str, apiurl: str, params: dict, calls: int, expect_fields: list | None):
    nbytes, res = raw_call(apiurl, params)
    rows = check(res, apiurl)
    nfields = len(rows[0]) if rows else 0
    total_mb = nbytes * calls / 1e6

    print(f"\n[{label}] {apiurl}")
    print(f"  응답 {nbytes:,} bytes · {len(rows):,} rows · {nfields} fields")
    if expect_fields:
        got = set(rows[0]) if rows else set()
        missing = set(expect_fields) - got
        extra = got - set(expect_fields)
        if missing:
            print(f"  !! data_list 요청 {len(expect_fields)}개 중 미반환: {sorted(missing)}"
                  f"  (없는 F-code는 조용히 버려진다)")
        if extra:
            print(f"  !! data_list 무시됨. 요청 외 필드 {len(extra)}개가 왔다. 수집하면 한도 폭발.")
        if not missing and not extra:
            print("  data_list OK (요청 필드와 정확히 일치)")
    print(f"  → {calls}콜 예상: {total_mb:,.1f} MB")
    return total_mb


def main():
    print(f"바이트 예산 실측 (표본일 {D}, 거래일 {TRADING_DAYS}일 기준)")
    print("일 사용량 한도 = 1,000,000,000 bytes (cust_id 단위)")

    slim = {"sdate": D, "edate": D, "data_list": ",".join(SLIM),
            "criteria_code": "F06508_12", "sort_code": "0"}
    total = 0.0
    for fam, mkt in [("m003", "KRX 코스닥"), ("m001", "KRX 코스피"),
                     ("m223", "NXT 코스닥"), ("m222", "NXT 코스피")]:
        total += probe(f"D1/D2 {mkt}", f"/stock/{fam}/rank_invest_date",
                       dict(slim), TRADING_DAYS, SLIM)
        time.sleep(1.2)  # 시계열 rate limit: 초당 1회

    total += probe("D3 공시", "/news/gongsi/gongsi_basic",
                   {"sdate": D, "edate": D, "dcnt": "3000"}, TRADING_DAYS, None)
    time.sleep(1.2)
    total += probe("D4 마스터", "/stock/m003/basic_info_all_port",
                   {"codelist": "'005930'"}, 2, None)

    print(f"\n{'='*60}")
    print(f"전체 예상 수집량: {total:,.0f} MB  (한도 1,000 MB)")
    if total > 700:
        print("!! 한도의 70% 초과. 기간 단축 또는 시장 축소 필요")
    elif total > 400:
        print("주의: 한도의 40% 초과. 같은 날 다른 수집 작업과 겹치지 말 것")
    else:
        print("여유 있음. 하루 안에 수집 가능")


if __name__ == "__main__":
    main()
