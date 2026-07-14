"""코스닥 공시 제목 실사. '거래소 수시공시 + 주요사항보고서' 만 남기는 규칙을 만들기 위한 재료.

코드 필드(BIGCD/BONCD/SRCCD…)는 전부 단일값이라 구분력이 없음이 실측으로 확인됐다(probe_gongsi.py).
MTVCD 는 시장 구분(300 유가 · 320 코스닥 · 310 선옵 · 330 코넥스 · 360 시장경보)일 뿐이다.
→ 유형 분리는 **제목 텍스트 규칙**뿐. 그러니 제목을 실제로 보고 규칙을 짜고, 커버리지를 잰다.

실행: 등록 IP · 샌드박스 밖.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import load_env, _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
BASE = "https://checkapi.koscom.co.kr"
ENV = load_env()

# 서로 다른 성격의 날이 섞이도록 분기별로 흩어 뽑는다
DAYS = ["20240701", "20250102", "20250415", "20250814", "20251114", "20260519", "20260630"]

# 회사명 접두 제거용. "(주)X" "㈜X" "주식회사 X" "X(주)" 등
COMPANY = re.compile(r"^\s*(\(주\)|㈜|주식회사)?\s*[^\s]{1,30}?(\(주\)|㈜)?\s+")

# ── 제외 대상 (공시부 심사 물량이 아님) ────────────────────────────
MARKET_ACTION = [           # 거래소가 스스로 발동하는 시장조치·경보
    "투자주의", "투자경고", "투자위험", "단기과열", "공매도 과열", "공매도과열",
    "소수계좌", "시장경보", "매매거래 정지", "매매거래정지", "상장폐지", "정리매매",
    "관리종목", "불성실공시법인", "투자주의환기",
]
ISSUER_PRODUCT = [          # ELW/ETN/ETF 등 발행사·상품 공시
    "ELW", "ETN", "상장지수", "유동성공급", "LP", "지수산출", "괴리율",
    "주식선물", "주식옵션", "가격제한폭 확대",
]
NOTICE = ["대량매매내역", "기타시장안내", "시장조치", "안내사항", "매매방법"]

# ── 분석 대상: 거래소 수시공시 + 주요사항보고서 항목 ────────────────
CORP_DISCLOSURE = [
    # 자본조달 (주요사항보고서 대상 다수)
    "유상증자", "무상증자", "전환사채", "신주인수권부사채", "교환사채", "전환청구권",
    "신주발행", "출자", "증권 발행결과", "발행조건 확정",
    # 지배구조·구조변경 (주요사항보고서)
    "최대주주 변경", "최대주주변경", "합병", "분할", "영업양수", "영업양도",
    "주식교환", "타법인 주식", "회생절차", "부도", "해산", "감자",
    # 경영·실적
    "영업(잠정)실적", "매출액 또는 손익구조", "실적", "배당", "자기주식",
    "단일판매", "공급계약", "수주", "임원", "대표이사", "소송", "기업설명회", "IR",
    "주주총회", "감사보고서", "사업보고서", "현금·현물배당",
    "조회공시요구", "풍문",   # 조회공시 답변은 기업 제출 → 대상
]


def call(apiurl, params):
    body = urllib.parse.urlencode({"cust_id": ENV["CHECK_CUST_ID"],
                                   "auth_key": ENV["CHECK_AUTH_KEY"], **params}).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + apiurl, data=body), timeout=120) as r:
        payload = json.loads(r.read())
    if not payload.get("success"):
        raise RuntimeError(f"{apiurl} -> {payload.get('message')}")
    return payload["results"]


def bucket(title: str) -> str:
    t = title.replace(" ", "")
    if any(k.replace(" ", "") in t for k in MARKET_ACTION):
        return "제외:시장조치"
    if any(k.replace(" ", "") in t for k in ISSUER_PRODUCT):
        return "제외:발행사상품"
    if any(k.replace(" ", "") in t for k in NOTICE):
        return "제외:안내통계"
    if any(k.replace(" ", "") in t for k in CORP_DISCLOSURE):
        return "대상:기업공시"
    return "미분류"


def main():
    rows = []
    for d in DAYS:
        rows += call("/news/gongsi/gongsi_basic", {"sdate": d, "edate": d, "dcnt": "3000"})
        time.sleep(1.2)
    kosdaq = [r for r in rows if str(r.get("MTVCD")) == "320"]
    print(f"전체 {len(rows):,}건 · 코스닥(MTVCD=320) {len(kosdaq):,}건 · {len(DAYS)}일 표본\n")

    b = Counter(bucket(r.get("TITLE") or "") for r in kosdaq)
    tot = len(kosdaq)
    print("--- 코스닥 공시 분류 (초안 규칙) ---")
    for k, n in b.most_common():
        print(f"  {k:14s} {n:5d}  ({n/tot*100:5.1f}%)")

    print("\n--- 미분류 제목 전수 (규칙 보강용) ---")
    unc = Counter()
    for r in kosdaq:
        t = (r.get("TITLE") or "").strip()
        if bucket(t) == "미분류":
            unc[COMPANY.sub("", t)[:52]] += 1
    for t, n in unc.most_common(45):
        print(f"  {n:4d}  {t}")

    print("\n--- '대상:기업공시' 표본 40 (오분류 눈검사) ---")
    hit = [COMPANY.sub("", (r.get("TITLE") or "").strip())[:56]
           for r in kosdaq if bucket(r.get("TITLE") or "") == "대상:기업공시"]
    for t, n in Counter(hit).most_common(40):
        print(f"  {n:4d}  {t}")

    print("\n--- 시각 분포: 애프터 시간대(15:40~20:00) 비중 ---")
    for label, sub in [("전체 코스닥", kosdaq),
                       ("대상:기업공시만", [r for r in kosdaq
                                       if bucket(r.get("TITLE") or "") == "대상:기업공시"])]:
        after = sum(1 for r in sub if 154000 <= int((r.get("TIME") or "0")[:6] or 0) <= 200000)
        print(f"  {label:16s} {after:5d} / {len(sub):5d}  ({after/max(len(sub),1)*100:5.1f}%)")


if __name__ == "__main__":
    main()
