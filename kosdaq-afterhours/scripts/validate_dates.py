"""공시 본문의 '지정일/해제일/정지일' vs 우리 규칙이 계산한 날짜. 표본 검증.

우리는 "시장경보류는 장 마감 후 발표되므로 **공시 다음 거래일**부터 효력"이라는 규칙을 썼다.
그런데 **공시일 ≠ 효력일**일 수 있다. 본문에는 실제 날짜가 명시된다:

    투자경고종목 지정 | ... | 2. 지정일 | 2026년 01월 22일
    관리종목 지정    | ... | 3.지정일  | 2026-04-02
    주권매매거래정지  | ... | 3.정지기간 | 가.정지일시 | 2026-04-20

→ 본문 날짜를 정답으로 삼아 우리 규칙의 일치율을 잰다.

⚠ 매매거래정지는 정지일이 **공시 다음 거래일이 아닐 수 있다**(원풍물산: 공시 4/15 → 정지 4/20).
   그래서 규칙 B는 '다음 거래일'이 아니라 **거래량 0**으로 찾는다. 그 판단이 맞는지도 여기서 확인한다.
"""

from __future__ import annotations

import html
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import load_env, _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
E = load_env()
BASE = "https://checkapi.koscom.co.kr"
DATA = Path(__file__).resolve().parent.parent / "data"
N = 12          # 유형별 표본 수


def call(u, p):
    b = urllib.parse.urlencode({"cust_id": E["CHECK_CUST_ID"], "auth_key": E["CHECK_AUTH_KEY"], **p}).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + u, data=b), timeout=120) as r:
        pl = json.loads(r.read())
    return pl["results"] if pl.get("success") else []


def clean(body: str) -> str:
    t = re.sub(r"\.[A-Z][\w-]*\s*\{[^}]*\}", " ", body)      # CSS 룰
    t = re.sub(r"<[^>]+>", " | ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", re.sub(r"(\s*\|\s*)+", " | ", t)).strip(" |")


DATE_PATS = [
    r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
    r"(\d{4})-(\d{2})-(\d{2})",
    r"(\d{4})\.(\d{2})\.(\d{2})",
]


def dates_after(txt: str, *labels: str) -> str | None:
    """라벨 뒤에 처음 나오는 날짜를 YYYYMMDD 로."""
    for lab in labels:
        i = txt.find(lab)
        if i < 0:
            continue
        seg = txt[i:i + 160]
        for pat in DATE_PATS:
            m = re.search(pat, seg)
            if m:
                return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    return None


def main():
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["n"] = g.title.fillna("").str.replace(r"\s+", "", regex=True)
    # status.py 와 동일한 전처리: 안내·우려·(정정) 제외
    g = g[~g.n.str.contains("기타시장안내|우려", na=False)]
    g = g[~g.n.str.contains(r"\(정정\)", na=False)]
    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    d = d[d.fam == "m003"].copy()
    d["vol"] = d[["vol_sell", "vol_buy"]].fillna(0).max(axis=1)
    days = sorted(d.date.unique())

    def next_td(x):
        return next((t for t in days if t > x), None)

    CASES = [
        ("투자경고 지정", g.n.str.contains("투자경고종목") & ~g.n.str.contains("해제|예고"), ("지정일",), "next"),
        ("투자경고 해제", g.n.str.contains("투자경고종목") & g.n.str.contains("해제") & ~g.n.str.contains("일부해제"), ("지정해제", "해제일"), "next"),
        ("투자위험 지정", g.n.str.contains("투자위험종목") & ~g.n.str.contains("해제|예고"), ("지정일",), "next"),
        ("관리종목 지정", g.n.str.contains("관리종목") & ~g.n.str.contains("해제|예고"), ("지정일",), "next"),
        ("관리종목 전체해제", g.n.str.contains("관리종목") & g.n.str.contains("해제") & ~g.n.str.contains("일부해제"), ("해제일", "지정해제"), "next"),
        ("환기종목 지정", g.n.str.contains("투자주의환기종목") & ~g.n.str.contains("해제|예고"), ("지정일",), "next"),
        ("매매거래정지", g.n.str.contains("주권매매거래정지") & ~g.n.str.contains("해제"), ("정지일시", "정지일"), "vol"),
    ]

    random.seed(3)
    for lab, mask, labels, mode in CASES:
        sub = g[mask]
        smp = sub.sample(min(N, len(sub)), random_state=3)
        ok = diff = nobody = 0
        bad = []
        for r in smp.itertuples():
            rows = call("/news/gongsi/gongsi_basic", {"sdate": r.date, "edate": r.date, "dcnt": "3000"})
            hit = [x for x in rows if (x.get("NCD") or "").strip() == r.code
                   and (x.get("TITLE") or "").strip() == r.title]
            if not hit:
                nobody += 1
                continue
            b = call("/news/gongsi/gongsi_body", {"ndate": hit[0]["DATE"], "ncode": hit[0]["CODE"]})
            time.sleep(1.15)
            txt = clean(b[0]["BODY"]) if b else ""
            truth = dates_after(txt, *labels)
            if not truth:
                nobody += 1
                continue

            if mode == "next":
                ours = next_td(r.date)
            else:                                  # 규칙 B: 공시 후 3거래일 내 첫 무거래일
                x = d[d.code == r.code].sort_values("date")
                dts, vols = list(x.date), list(x.vol)
                i = next((k for k, t in enumerate(dts) if t >= r.date), None)
                ours = None
                if i is not None:
                    j, start = i, i
                    while j < len(dts) and vols[j] > 0 and j - start <= 3:
                        j += 1
                    if j < len(dts) and vols[j] == 0:
                        ours = dts[j]
            if ours == truth:
                ok += 1
            else:
                diff += 1
                bad.append((r.code, r.date, truth, ours, r.title[:40]))

        tot = ok + diff
        print(f"\n[{lab}] 표본 {len(smp)} · 본문 날짜 추출 {tot} · 본문없음/미추출 {nobody}")
        if tot:
            print(f"  일치 {ok}/{tot} ({ok/tot*100:.0f}%)")
        for c, dd, t, o, ti in bad[:5]:
            print(f"    불일치 {c} 공시{dd} · 본문 {t} · 우리 {o}  | {ti}")


if __name__ == "__main__":
    main()
