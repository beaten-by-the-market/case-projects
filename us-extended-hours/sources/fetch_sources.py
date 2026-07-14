"""
1차 출처 재수집 스크립트.  → sources/MANIFEST.md 의 모든 파일을 원래 URL에서 다시 받는다.

⚠ SEC(sec.gov)는 스크립트 접근을 자주 차단한다(HTML 오류페이지를 PDF인 척 돌려준다).
   그래서 SEC 규칙제정 문서는 **연방관보(Federal Register) 전문 텍스트**로 받는다.
   연방관보본과 SEC PDF본은 같은 문서다. 인용 시 릴리스 번호를 쓰면 된다.

⚠ 나스닥 Workday·NYSE careers·나스닥 룰북은 SPA(자바스크립트)라 curl로 본문이 안 나온다.
   - 나스닥 채용: Workday **JSON API**를 쓴다 (아래 nasdaq_jobs()).
   - NYSE 채용: 페이지의 **JSON-LD**(<script type="application/ld+json">)를 파싱한다.
   - NYSE 룰북: nyseguide.srorules.com 의 콘텐츠 API. 여기서는 자동화하지 않는다
     (수집 시점 원문을 nyse_rule-7.34_trading-sessions_current.txt 에 보존해 둠).

사용:  python fetch_sources.py
"""

import json
import pathlib
import re
import urllib.request

HERE = pathlib.Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (research; contact via repo owner)"}

# ── SEC 규칙제정 문서 (연방관보 전문) ──────────────────────────────────────
# 릴리스번호 → (연방관보 raw text URL, 저장 파일명)
FEDERAL_REGISTER = {
    "34-105199": (  # 나스닥 23/5 승인 (SR-NASDAQ-2025-109), 2026-04-10
        "https://www.federalregister.gov/documents/full_text/text/2026/04/15/2026-07259.txt",
        "34-105199_nasdaq-23-5-approval.txt",
    ),
    "34-105860": (  # 야간 기업행위 강제정지 (SR-NASDAQ-2026-057), 2026-07-08
        "https://www.federalregister.gov/documents/full_text/text/2026/07/13/2026-14014.txt",
        "34-105860_nasdaq-corporate-action-halts.txt",
    ),
    "34-105596": (  # LULD 제27차 개정 — 야간 가격밴드 (File 4-631), 2026-06-01
        "https://www.federalregister.gov/documents/full_text/text/2026/06/04/2026-11147.txt",
        "34-105596_luld-27th-overnight-bands.txt",
    ),
}

# ── 거래소 공식 문서 ───────────────────────────────────────────────────────
DOCS = {
    "https://www.nyse.com/publicdocs/nyse/NYSE_Extended_Hours_Trading_FAQ.pdf":
        "nyse_extended-hours-FAQ_v3.0_2026-05.pdf",
    "https://www.nasdaqtrader.com/trader.aspx?id=marketwatch":
        "nasdaqtrader_marketwatch-hours.html",
}


def get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=60
    ).read()


def strip_fr_html(raw: bytes) -> str:
    """연방관보 전문 페이지는 <html><pre>…</pre> 로 감싸여 온다. 본문만 꺼낸다."""
    t = raw.decode("utf-8", errors="replace")
    m = re.search(r"<pre>(.*?)</pre>", t, re.S)
    body = m.group(1) if m else t
    return re.sub(r"<[^>]+>", "", body).strip()


def nasdaq_jobs(search_text: str) -> list[dict]:
    """나스닥 Workday JSON API.  ⚠ 살아 있는 채용판은 Global_External_Site 다
    (US_External_Career_Site 는 무엇을 검색해도 0건을 돌려주는 죽은 엔드포인트)."""
    req = urllib.request.Request(
        "https://nasdaq.wd1.myworkdayjobs.com/wday/cxs/nasdaq/Global_External_Site/jobs",
        data=json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0,
                         "searchText": search_text}).encode(),
        headers={**UA, "Content-Type": "application/json", "Accept": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["jobPostings"]


def ice_job(job_id: int) -> dict | None:
    """NYSE/ICE 채용공고는 SPA다. 본문은 JSON-LD 에 들어 있다."""
    html = get(f"https://careers.ice.com/jobs/{job_id}").decode("utf-8", "replace")
    for m in re.finditer(
        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S
    ):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
    return None


if __name__ == "__main__":
    for rel, (url, name) in FEDERAL_REGISTER.items():
        (HERE / name).write_text(strip_fr_html(get(url)), encoding="utf-8")
        print(f"  {rel:12} -> {name}")

    for url, name in DOCS.items():
        (HERE / name).write_bytes(get(url))
        print(f"  {'docs':12} -> {name}")

    for j in nasdaq_jobs("MarketWatch"):
        print(f"  nasdaq job   -> {j['title']} | {j['locationsText']} | {j['postedOn']}")

    for jid in (12950, 13053):
        d = ice_job(jid)
        if d:
            print(f"  ice job {jid} -> {d['title']} | {d['datePosted'][:10]}")
