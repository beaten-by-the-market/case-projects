"""블랙리스트 전수 감사. 606일 전체에서 오분류(누수)를 찾는다.

블랙리스트는 7일 표본으로 짰다. 전체 기간에는 표본에 없던 표현이 반드시 있다.
이 설계에서 위험한 오류는 **한 방향뿐**이다:
    블랙리스트에 없는 표현의 '거래소 조치'가 → 수시공시(잔여)로 흘러든다.
(반대 방향. 수시공시가 시장조치로 잘못 빠지는 것. 은 키워드가 명시적이라 거의 없다.)

그래서 수시공시 버킷을 **전수로 훑고**, 조치성 어휘를 가진 항목을 의심 목록으로 뽑는다.
네트워크를 쓰지 않는다 (data/gongsi.csv 사용).
"""

from __future__ import annotations

import csv
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

import classify as C  # noqa: E402

_force_utf8_stdout()
DATA = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent.parent / "output"
OUT.mkdir(exist_ok=True)

# 거래소 조치·공지 냄새가 나는 어휘. 수시공시 버킷에 이게 있으면 사람이 확인해야 한다.
SUSPECT = ["지정", "해제", "예고", "부과", "공표", "심의", "통보", "조치", "경보", "요건",
           "적출", "환기", "제재", "위반", "안내", "확대", "유예", "면제", "승인", "취소",
           "해당", "선정", "발동", "중단", "재개", "연장", "철회"]

_SP = re.compile(r"\s+")


def load_names() -> dict[str, str]:
    names = {}
    p = DATA / "master.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["code"]:
                    names[r["code"]] = r["name"]
    return names


def core(title: str, name: str | None) -> str:
    """회사명 접두를 떼어 공시 '유형'만 남긴다 (감사용 그룹핑)."""
    t = title.strip()
    if name:
        t = t.replace(name, "")
    # 남은 법인격 표기 제거
    t = re.sub(r"^[\s\(\)주식회사㈜]*", "", t)
    t = re.sub(r"^[^\s]{0,20}(\(주\)|㈜)\s*", "", t)
    return _SP.sub(" ", t).strip()


def main():
    names = load_names()
    rows = []
    with (DATA / "gongsi.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["mtvcd"] == "320":          # 코스닥
                rows.append(r)
    print(f"코스닥 공시 {len(rows):,}건 / 606 거래일 (일평균 {len(rows)/606:.0f}건)\n")

    buckets = defaultdict(list)
    for r in rows:
        buckets[C.bucket(r["title"])].append(r)

    print("--- 전체 기간 분류 ---")
    for k, v in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print(f"  {k:8s} {len(v):7,}  ({len(v)/len(rows)*100:5.1f}%)")

    susi = buckets["수시공시"]

    # ── 1. 고유 제목 유형 전수 (빈도순) ──
    types = Counter(core(r["title"], names.get(r["code"])) for r in susi)
    print(f"\n--- 수시공시 고유 제목 유형: {len(types):,}종 ---")
    path = OUT / "audit_susi_types.txt"
    with path.open("w", encoding="utf-8") as f:
        for t, n in types.most_common():
            f.write(f"{n}\t{t}\n")
    print(f"    전체 목록 저장: {path}")

    # ── 2. 의심 항목: 조치성 어휘를 가진 수시공시 ──
    flagged = Counter()
    for t, n in types.items():
        tn = _SP.sub("", t)
        hits = [w for w in SUSPECT if w in tn]
        if hits:
            flagged[t] = n
    tot_flag = sum(flagged.values())
    print(f"\n--- 의심(조치성 어휘 포함) 유형 {len(flagged):,}종 / {tot_flag:,}건 "
          f"({tot_flag/len(susi)*100:.1f}% of 수시공시) ---")
    print("    ※ 대부분은 정상이다(예: '최대주주 변경', '주식매수선택권 취소'). 눈으로 갈라야 한다.")
    for t, n in flagged.most_common(60):
        print(f"  {n:6,}  {t[:66]}")
    with (OUT / "audit_suspect_types.txt").open("w", encoding="utf-8") as f:
        for t, n in flagged.most_common():
            f.write(f"{n}\t{t}\n")

    # ── 3. 저빈도 꼬리 무작위 표본 (희귀 표현이 여기 숨는다) ──
    rare = [t for t, n in types.items() if n <= 3]
    random.seed(11)
    print(f"\n--- 저빈도(≤3건) 유형 {len(rare):,}종 중 무작위 40 ---")
    for t in random.sample(rare, min(40, len(rare))):
        print(f"  · {t[:74]}")

    # ── 4. 애프터 시간대 비중 (전체 기간 확정치) ──
    print("\n--- 애프터 시간대(15:40~20:00) 비중 · 전체 기간 ---")
    for label, sub in [("코스닥 전체", rows), ("수시공시만", susi)]:
        a = sum(1 for r in sub if C.is_after_hours(r["time"]))
        print(f"  {label:10s} {a:7,} / {len(sub):7,}  ({a/len(sub)*100:5.1f}%)")

    corr = sum(1 for r in susi if C.is_correction(r["title"]))
    print(f"\n정정공시: {corr:,} / {len(susi):,} ({corr/len(susi)*100:.1f}%)")


if __name__ == "__main__":
    main()
