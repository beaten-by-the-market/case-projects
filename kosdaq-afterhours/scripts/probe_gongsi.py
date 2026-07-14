"""공시 피드의 코드 필드로 '거래소 수시공시 / 주요사항보고서' 를 갈라낼 수 있는지 실측.

gongsi_basic 은 DART 원문이 아니라 KRX 공시 + 시장조치가 섞인 스트림이다.
분석 대상은 **거래소 수시공시 + 주요사항보고서** 뿐이고, 시장경보·ETF LP·통계 등은 빼야 한다.
BIGCD(대분류) · BONCD(본문분류) · SRCCD(원천소스) · MTVCD(뉴스원) 각각이
실제로 무엇을 구분하는지 제목 표본과 대조해 확인한다.

실행: 등록 IP · 샌드박스 밖.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import load_env, _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
BASE = "https://checkapi.koscom.co.kr"
ENV = load_env()
DAYS = ["20260629", "20260630"]


def call(apiurl, params):
    body = urllib.parse.urlencode({"cust_id": ENV["CHECK_CUST_ID"],
                                   "auth_key": ENV["CHECK_AUTH_KEY"], **params}).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + apiurl, data=body), timeout=120) as r:
        payload = json.loads(r.read())
    if not payload.get("success"):
        raise RuntimeError(f"{apiurl} -> {payload.get('message')}")
    return payload["results"]


def main():
    rows = []
    for d in DAYS:
        rows += call("/news/gongsi/gongsi_basic", {"sdate": d, "edate": d, "dcnt": "3000"})
        time.sleep(1.2)
    print(f"공시 {len(rows):,}건 ({', '.join(DAYS)})\n")

    for fld in ["MTVCD", "BIGCD", "SRCCD", "BONCD", "IMPCD", "SKCD", "FUNCCD", "LANGCD"]:
        cnt = Counter(str(r.get(fld)) for r in rows)
        if len(cnt) == 1:
            print(f"--- {fld}: 단일값 {list(cnt)[0]} (구분력 없음)")
            continue
        print(f"--- {fld}: {len(cnt)}개 값")
        samples = defaultdict(list)
        for r in rows:
            v = str(r.get(fld))
            if len(samples[v]) < 4:
                samples[v].append(r.get("TITLE", "")[:58])
        for v, n in cnt.most_common(12):
            print(f"  [{v}] {n:5d}건")
            for t in samples[v]:
                print(f"        · {t}")
        print()

    # 종목코드(NCD) 유무. 종목 귀속 가능한 공시만 분석 대상이 된다
    with_ncd = sum(1 for r in rows if (r.get("NCD") or "").strip())
    print(f"NCD(종목코드) 있는 공시: {with_ncd:,} / {len(rows):,}")

    # 제목 앞머리 패턴. 실제로 어떤 유형들이 오는지 육안 확인
    print("\n--- 제목 접두 패턴 상위 30 ---")
    head = Counter()
    for r in rows:
        t = (r.get("TITLE") or "").strip()
        head[t.split("(")[0][:22]] += 1
    for h, n in head.most_common(30):
        print(f"  {n:5d}  {h}")

    print("\n--- '주요사항보고서' 포함 제목 표본 ---")
    ms = [r for r in rows if "주요사항" in (r.get("TITLE") or "")]
    print(f"  총 {len(ms)}건")
    for r in ms[:8]:
        print(f"  MTVCD={r.get('MTVCD')} BIGCD={r.get('BIGCD')} BONCD={r.get('BONCD')} "
              f"SRCCD={r.get('SRCCD')} | {r.get('TITLE','')[:60]}")


if __name__ == "__main__":
    main()
