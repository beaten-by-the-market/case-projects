"""
미국 거래정지 원자료 집계. → B2-disclosure-halts.md §B2-5 · §B2-6 의 모든 표를 재현한다.

⚠ 중복 제거가 필수다. 월별 CSV를 단순히 이어붙이면 12,837건이 13,696건으로 부풀어
   뉴스형 정지가 1,645 → 2,378로 45% 과대집계된다.

   ⚠ 원인을 정확히 알 것 (이전 판의 설명은 틀렸다):
     ✗ "경계일 정지가 인접 월 파일에 중복돼 들어온다" → 아니다.
       월 경계를 넘는 중복은 0건이다.
     ✓ API가 같은 파일 안에 한 정지를 두 줄로 내보낸다:
         · 정지(halt) 행     — 재개 필드가 비어 있다
         · 재개(resume) 행   — 재개 필드가 채워져 있다
   → (일자, 시각, 종목, 거래소, 사유) 5개 키로 중복을 제거한다.

   ⚠⚠ keep=first는 건수는 맞히지만 재개시각을 파괴한다.
      858개 중복군 중 835개에서 두 행 중 하나만 재개시각을 갖는다.
      재개시각을 분석하려면 반드시 "재개 필드가 있는 행"을 우선해서 골라야 한다.
      (그렇게 하면 19:50 코호트의 재개기록이 350건 → 668건으로 늘어난다.)

⚠ 사유 코드의 대소문자가 흔들린다("News pending" / "News Pending").
   소문자화는 매칭 단계에만 적용되고 중복제거 키에는 적용되지 않는다.
   → 순수 대소문자 중복 23건이 살아남는다. 엄밀한 집계는 1,645가 아니라 1,609건이다.
     (비율은 견고하다: 88.9% → 88.9%)

⚠ 타임존: ET 벽시계다. 검증 — LULD 정지 10,972건이 전부 09:30-16:00 안에 떨어진다.
   LULD는 정규장에만 존재하므로 UTC일 수 없다.

⚠ "NYSE 공개 API"지만 내용의 86%가 나스닥 상장종목이다 (UTP/Tape-C 교차 통지).

⚠ to_minutes()는 "See Subsequent Halt" 문자열에서 깨진다 (h_* 에 39행 존재).
   현재 필터 조합에서는 그 행들이 걸리지 않아 우연히 통과할 뿐이다.

사용:  python analyze_halts.py
"""

import collections
import csv
import glob

SESSIONS = [
    ("00:00-04:00", 0, 4 * 60),
    ("04:00-09:30 프리마켓", 4 * 60, 9 * 60 + 30),
    ("09:30-16:00 정규장", 9 * 60 + 30, 16 * 60),
    ("16:00-20:00 애프터", 16 * 60, 20 * 60),
    ("20:00-24:00", 20 * 60, 24 * 60),
]


def load(pattern):
    """월별 CSV를 읽어 중복을 제거한다."""
    seen, rows = set(), []
    for path in sorted(glob.glob(pattern)):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                key = (r["Halt Date"], r["Halt Time"], r["Symbol"],
                       r["Exchange"], r["Reason"])
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
    return rows


def to_minutes(t):
    h, m, *_ = t.split(":")
    return int(h) * 60 + int(m)


def session_of(t):
    m = to_minutes(t)
    for name, lo, hi in SESSIONS:
        if lo <= m < hi:
            return name
    return None


def report(pattern, label):
    rows = load(pattern)
    news = [r for r in rows if "news" in r["Reason"].lower()]
    luld = [r for r in rows if "luld" in r["Reason"].lower()]
    n = len(news)

    print(f"\n=== {label} ===")
    print(f"전체 정지(중복제거): {len(rows):,}   LULD: {len(luld):,}   뉴스형: {n:,}")

    print("\n[뉴스형 정지의 시간대 분포]")
    by_sess = collections.Counter(session_of(r["Halt Time"]) for r in news)
    for name, _, _ in SESSIONS:
        c = by_sess.get(name, 0)
        print(f"  {name:22s} {c:5,}  {c / n * 100:5.1f}%")
    outside = n - by_sess.get("09:30-16:00 정규장", 0)
    print(f"  {'→ 정규장 밖':22s} {outside:5,}  {outside / n * 100:5.1f}%")

    print("\n[상장거래소별]")
    for exch, c in collections.Counter(r["Exchange"] for r in news).most_common():
        sub = [r for r in news if r["Exchange"] == exch]
        out = sum(1 for r in sub
                  if not (9 * 60 + 30 <= to_minutes(r["Halt Time"]) < 16 * 60))
        print(f"  {exch:16s} {c:5,}   정규장 밖 {out / c * 100:5.1f}%")

    # 나스닥 정지 구조 (§21-3)
    nas = [r for r in news if r["Exchange"] == "Nasdaq"]
    if not nas:
        return
    print("\n[나스닥 뉴스형 정지의 구조]")
    at1950 = [r for r in nas if r["Halt Time"].startswith("19:50")]
    resumed = [r for r in at1950 if r["NYSE Resume Time"].strip()]
    morning = [r for r in resumed
               if 9 * 60 <= to_minutes(r["NYSE Resume Time"]) <= 9 * 60 + 5]
    print(f"  19:50:00 정각 스탬프      : {len(at1950):4,}"
          f"  (재개시각 기록 {len(resumed)}건 중 {len(morning)}건이 익일 09:00~09:05 재개)")

    pre = [r for r in nas if 4 * 60 <= to_minutes(r["Halt Time"]) < 9 * 60 + 30]
    pre_back = [r for r in pre if r["NYSE Resume Time"].strip()
                and to_minutes(r["NYSE Resume Time"]) < 9 * 60 + 30]
    print(f"  프리마켓 중               : {len(pre):4,}"
          f"  (그중 {len(pre_back)}건이 09:30 이전에 재개 = 세션 안에서 실시간 집행)")

    post = [r for r in nas
            if 16 * 60 <= to_minutes(r["Halt Time"]) < 20 * 60
            and not r["Halt Time"].startswith("19:50")]
    reg = [r for r in nas if 9 * 60 + 30 <= to_minutes(r["Halt Time"]) < 16 * 60]
    print(f"  애프터 그 외              : {len(post):4,}")
    print(f"  정규장 중                 : {len(reg):4,}"
          f"  ({len(reg) / len(nas) * 100:.1f}%)")

    # 19:50 코호트를 빼도 결론이 유지되는가
    rest = [r for r in nas if not r["Halt Time"].startswith("19:50")]
    rest_out = sum(1 for r in rest
                   if not (9 * 60 + 30 <= to_minutes(r["Halt Time"]) < 16 * 60))
    print(f"\n  ※ 19:50 코호트 제외 시: {len(rest):,}건 중 정규장 밖 "
          f"{rest_out / len(rest) * 100:.1f}%  (결론 유지)")


if __name__ == "__main__":
    report("p_*.csv", "2024-07 ~ 2025-06")
    report("h_*.csv", "2025-07 ~ 2026-06")
