"""종목별·일자별 '애프터마켓 편입 불가' 상태를 공시에서 복원한다.

거래소는 애프터마켓에서 다음을 거래하지 않기로 했다:
    투자경고 · 투자위험 · 관리종목 · 투자주의환기 · 초저유동 · 투자유의

**종목 단위가 아니라 일자 단위로 판정해야 한다.** 투자경고·투자위험은 1~2주짜리 일시 지정이라,
종목을 통째로 빼면 유니버스가 과도하게 깎이고, 통째로 넣으면 지정 기간의 거래·공시가 섞여 든다.

## 실측으로 확인한 것

- **'지정예고'는 지정이 아니다.** 투자경고 관련 공시 2,802건 중 **2,059건이 예고**다.
  예고를 지정으로 세면 지정 종목이 442개 → 730개로 부풀어 오른다. 반드시 배제한다.
- 지정/해제 짝: 투자경고 지정 442종목 / 해제 437종목 (일시적, 짝이 맞음).
  관리종목 지정 214 / 해제 86 (지속적. 대개 해제 없이 상장폐지로 간다).
- **초저유동(저유동성종목 단일가매매)은 코스닥 보통주에 사실상 없다**. 4건·2종목이고 전부 우선주다.
- **투자유의종목은 코넥스 제도**로 코스닥엔 0건이다.
  → 즉 거래소가 정한 6개 유형 중 코스닥 보통주에 실제로 걸리는 것은 **넷뿐**이다.

## 효력 시점

시장경보류 공시는 **장 마감 후(20시경) 일괄 발표**된다(리포 실측). 따라서 지정 효력은 **다음 거래일**부터다.
→ 지정 구간 = [지정공시 다음 거래일, 해제공시 당일]. 해제도 마감 후 공시이므로 해제일까지는 지정 상태다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
END = "20260630"

TYPES = {
    "투자경고": "투자경고종목",
    "투자위험": "투자위험종목",
    "관리종목": "관리종목",
    "환기종목": "투자주의환기종목",
}
_SP = re.compile(r"\s+")


def halt_days(trading_days: list[str]) -> set[tuple[str, str]]:
    """매매거래정지. 공시로 구간을 잡고, **거래량으로 실제 정지일을 확정**한다.

    ## 공시 흐름 (실측)
        주권매매거래정지        919건 / 577종목   ← 정지 이벤트
        주권매매거래정지기간변경  521건 / 131종목   ← **새 정지가 아니다. 무시**
        주권매매거래정지해제     472건 / 357종목   ← 해제 이벤트

    ## 구간 [정지 공시일 … 해제 공시일] 을 그대로 빼면 안 된다
    해제 공시(472)가 정지(919)보다 적어 **짝이 안 맞는 구간이 기간 끝까지 늘어진다.**
    공시일 전구간을 빼면 **58,384 종목-일을 과다 제외**하는데, 그 **100%가 실제로 거래가 있던 날**이다.
    → **거래량이 진실이다.** 정지 중이면 거래량은 0이다.

    ## 규칙
    1. 구간 = [정지 공시일 … 해제 공시일] (해제 없으면 기간 끝까지). `기간변경`·`(정정)`은 무시.
    2. **정지 공시일은 무조건 제외**한다. 거래량이 있어도 그날 정지가 걸린 것이다(장중 정지).
       → 이것으로 **당일·장중 정지**(무상증자·자본감소·공급계약 조회 등, 153건)가 자동으로 잡힌다.
    3. 구간 안의 **무거래일**을 제외한다. 정지 중이면 거래량은 0이다.
    4. 구간 끝은 **해제 공시 이후 거래가 다시 붙는 첫날의 전날**이다.
       (해제 공시가 마감 후 나면 재개는 다음 거래일이다.)

    ## 왜 구간 전체를 통째로 빼지 않는가
    해제 공시(472건)가 정지(919건)보다 적어 **짝이 안 맞는 구간이 기간 끝까지 늘어진다.**
    구간 전체를 빼면 **58,384 종목-일을 과다 제외**하는데 그 **100%가 실제로 거래가 있던 날**이다.
    (원풍물산도 정지 공시 4/15 이후 4/16·17에 정상 거래가 있었고, 실제 정지는 4/20부터였다.)
    → 공시일은 빼되, 나머지는 **거래량으로 확정**한다.
    """
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["n"] = g.title.fillna("").map(lambda t: _SP.sub("", t))

    h = g[g.n.str.contains("주권매매거래정지", na=False)].copy()
    h = h[~h.n.str.contains(r"기간변경|\(정정\)", na=False)]   # 기간변경·정정은 새 정지가 아니다
    if h.empty:
        return set()
    h["release"] = h.n.str.contains("해제", na=False)
    h = h.sort_values(["code", "date", "time"])

    days_sorted = sorted(trading_days)
    start, end = days_sorted[0], days_sorted[-1]
    spans: list[tuple[str, str, str]] = []
    for c, x in h.groupby("code"):
        open_at = None
        for r in x.itertuples():
            if not r.release:
                if open_at is None:
                    open_at = r.date
            elif open_at is not None:
                spans.append((c, open_at, r.date))
                open_at = None
            else:
                # ⚠ 좌측 절단 보정 (규칙 A-9와 같은 논리).
                #    구간이 안 열린 상태에서 해제를 만났다 = **기간 이전부터 정지 중**이던 종목이다.
                #    상장폐지 절차 종목이 여기 걸린다. 우리 기간엔 `기간변경`(무시)과
                #    `주권매매거래정지해제(상장폐지에 따른 정리매매 개시)`만 보인다.
                #    (광림 014200: 462일 중 거래 7일 = 정리매매뿐. 이걸 놓치면 무거래일 97%짜리
                #     "저유동성 종목"으로 잘못 집계된다.)
                spans.append((c, start, r.date))
        if open_at is not None:
            spans.append((c, open_at, end))

    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    d = d[(d.fam == "m003") & d.code.isin({c for c, _, _ in spans})].copy()
    d["vol"] = d[["vol_sell", "vol_buy"]].fillna(0).max(axis=1)
    vol = {(r.code, r.date): r.vol for r in d.itertuples()}
    days = sorted(trading_days)

    bad: set[tuple[str, str]] = set()
    for c, s, e in spans:
        # 구간 끝 = 해제 공시 이후 '거래가 다시 붙는 첫날'의 전날.
        stop = end
        for x in days:
            if x >= e and vol.get((c, x), 0) > 0:
                stop = x
                break
        for x in days:
            if x < s or x > stop:
                continue
            # 정지 공시일은 무조건 제외(거래량이 있어도 그날 정지가 걸렸다) + 이후 무거래일
            if x == s or vol.get((c, x), 0) == 0:
                bad.add((c, x))
    return bad


def low_liquidity_days(trading_days: list[str]) -> set[tuple[str, str]]:
    """초저유동. `저유동성종목 단일가매매(30분단위) 적용`.

    ⚠ **공시의 종목코드(NCD)는 본주인데, 실제 지정 대상은 우선주다.**
        NCD 021040 (대호특수강)  →  대상 021045 (대호특수강**우**)
        NCD 032680 (소프트센)    →  대상 032685 (소프트센**우**)
    NCD로만 걸러내면 정작 지정된 우선주가 유니버스에 그대로 남는다.
    → KRX 코드 규약(본주 끝자리 0 → 우선주 5)으로 대상 코드를 만든다.

    해제 공시가 없고 매년 재지정된다(2024-12-30, 2025-12-30 실측) → **첫 공시 다음 거래일부터 끝까지.**
    """
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["n"] = g.title.fillna("").map(lambda t: _SP.sub("", t))
    ev = g[g.n.str.contains("저유동성종목", na=False)]
    days = sorted(trading_days)
    bad: set[tuple[str, str]] = set()
    for c, sub in ev.groupby("code"):
        target = c[:-1] + "5" if c[-1] == "0" else c      # 본주 → 우선주
        first = sub.date.min()
        bad |= {(target, d) for d in days if d > first}
    return bad


def spac_period_days(trading_days: list[str]) -> set[tuple[str, str]]:
    """스팩존속합병. **합병 전 '스팩이던 기간'** 을 제외한다.

    스팩 합병에는 두 가지가 있다:
      · **소멸합병**. 스팩이 사라지고 코드도 상장폐지된다. → 상폐 스팩으로 통째 제외(`analyze.py`).
      · **존속합병**. **스팩 코드가 그대로 유지되고 회사명만 바뀐다.**
        코드가 살아 있으므로 `F33792`는 이제 'N'(일반 기업)이다. 하지만 **합병 전 기간은 스팩**이었고,
        그때의 거래대금·공시가 그대로 섞여 든다. → **합병상장일 이전을 제외**한다.

    출처: KIND `SPAC 존속합병` 목록 (`data/spac소멸합병상장.xlsx`, 130건 / 2011~2025).
    **우리 기간(2024-01-01~)과 겹치는 건 2건뿐**이다:
        씨피시스템 (413630) 합병상장 2024-06-27
        지슨       (446840) 합병상장 2025-08-14
    나머지 128건은 합병이 2023년 이전이라 스팩 기간이 분석 기간 밖이다(무해).

    (공시 제목의 회사명으로 판정하는 휴리스틱도 **정확히 이 2종목**을 찾아냈다. 목록이 없으면 그걸 쓴다.)
    """
    days = sorted(trading_days)
    xls = DATA / "spac소멸합병상장.xlsx"
    if xls.exists():
        x = pd.read_excel(xls, dtype=str).dropna(subset=["종목코드"])
        x["합병상장일"] = pd.to_datetime(x["합병상장일"])
        bad: set[tuple[str, str]] = set()
        for r in x.itertuples():
            listed = r.합병상장일.strftime("%Y%m%d")
            bad |= {(r.종목코드, d) for d in days if d < listed}   # 합병상장일부터 일반 기업
        return bad

    # 폴백: 공시 제목 앞머리(회사명 위치)가 스팩이었다가 끊긴 종목
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["sp"] = g.title.fillna("").str.slice(0, 28).str.contains("기업인수목적|스팩", na=False)
    bad = set()
    for c, x in g.groupby("code"):
        sp = x[x.sp]
        # ⚠ 전체 공시 대비 비율로 봐야 한다(x.sp.mean()). sp.sp.mean()은 항상 1.0이다.
        if sp.empty or x.sp.mean() > 0.9:       # 끝까지 스팩인 종목은 analyze.py가 통째로 제외한다
            continue
        bad |= {(c, d) for d in days if d <= sp.date.max()}
    return bad


def ineligible_days(trading_days: list[str]) -> set[tuple[str, str]]:
    """애프터마켓 편입 불가 (종목코드, 일자) 쌍의 집합.

    두 축을 합친다:
      ① 지정(투자경고·투자위험·관리종목·투자주의환기). 공시에서 복원
      ② **매매거래정지**. KRX trading_halt 실측 (이전엔 '무거래일 90%' 휴리스틱이었다)
    """
    bad = (halt_days(trading_days)
           | low_liquidity_days(trading_days)
           | spac_period_days(trading_days))
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["n"] = g.title.fillna("").map(lambda t: _SP.sub("", t))

    days = sorted(trading_days)
    idx = {d: i for i, d in enumerate(days)}
    # (bad는 halt_days 로 이미 초기화됨)

    for _, kw in TYPES.items():
        sub = g[g.n.str.contains(kw, na=False)].copy()

        # ── 안내·우려 공시는 지정이 아니다 ──
        # "기타시장안내(관리종목지정우려종목)" · "내부결산시점 관리종목 지정ㆍ… 사유 발생" 같은 건
        # 지정 예고/우려 안내이지 지정이 아니다. (관리종목 관련 792건 중 상당수)
        sub = sub[~sub.n.str.contains("기타시장안내|우려", na=False)]

        # ── (정정) 공시는 새 구간을 열지 않는다 ──
        # 정정 공시의 본문 날짜는 **원래(과거) 지정·해제일**이라, 공시일 기준으로 새 이벤트를 만들면
        # 구간이 어긋난다. 원 공시가 이미 처리돼 있으므로 무시한다.
        sub = sub[~sub.n.str.contains(r"\(정정\)", na=False)]

        # ⚠ 판정 순서가 결정적이다. **해제를 먼저 보고, 그다음에 예고를 거른다.**
        #   해제 공시의 실제 제목이 "투자경고종목 지정해제 및 **재지정 예고**"다.
        #   예고를 먼저 걸러내면 해제 668건 중 667건이 통째로 사라지고, 지정 구간이 영영 닫히지 않는다.
        #
        # ⚠⚠ **'일부해제'는 해제가 아니다.** 관리종목·환기종목은
        #     지정 → 지정사유추가 → **일부해제** → (전체)해제 순으로 간다.
        #     "관리종목지정사유추가및일부해제(자본잠식률 50% 이상 등)" 는 사유 하나가 풀렸을 뿐
        #     **여전히 관리종목**이다. 이걸 해제로 처리하면 구간이 조기에 닫힌다.
        #     실측: 관리종목 해제 119건 중 47건(39%) · 환기종목 112건 중 24건(21%)이 일부해제다.
        sub["release"] = (sub.n.str.contains("해제", na=False)
                          & ~sub.n.str.contains("일부해제", na=False))
        sub["forecast"] = ~sub.release & sub.n.str.contains("예고", na=False)   # 순수 '지정예고'
        sub = sub[~sub.forecast].sort_values(["code", "date", "time"])

        for code, ev in sub.groupby("code"):
            open_at = None
            for _, r in ev.iterrows():
                if not r.release:
                    if open_at is None:
                        open_at = r.date          # 지정 (중복 '지정사유추가'는 무시)
                elif open_at is not None:
                    _mark(bad, code, open_at, r.date, days, idx)
                    open_at = None
                else:
                    # ⚠ 좌측 절단 보정: 구간이 안 열린 상태에서 해제를 만났다
                    #    = **분석 기간(2024-01-01) 이전부터 지정돼 있던 종목**이다.
                    #    지정 공시가 데이터 밖이라 구간을 못 열었을 뿐, 그 사이는 계속 지정 상태였다.
                    #    → **첫 거래일부터 해제 공시일까지** 제외한다.
                    #    31종목 전부 gongsi_jong 으로 과거 지정 공시를 확인했다(메디앙스 2020-03,
                    #    피엔티엠에스 2021-01, 포인트모바일 2022-03, 미코 2023-03 …).
                    bad |= {(code, d) for d in days if d <= r.date}
            if open_at is not None:               # 해제 없이 기간 종료 → 끝까지 지정 상태
                _mark(bad, code, open_at, END, days, idx)
    return bad


def _mark(bad, code, start, end, days, idx):
    """지정 효력은 공시 **다음 거래일**부터(마감 후 발표), 해제 공시 **당일**까지."""
    i = idx.get(start)
    if i is None:                                  # 휴장일 공시 → 다음 거래일 탐색
        i = next((k for k, d in enumerate(days) if d >= start), None)
        if i is None:
            return
        i -= 1
    j = idx.get(end, len(days) - 1)
    for d in days[i + 1: j + 1]:
        bad.add((code, d))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
    from _common import _force_utf8_stdout
    _force_utf8_stdout()

    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str}, usecols=["fam", "date"])
    days = sorted(d[d.fam == "m003"].date.unique())
    bad = ineligible_days(days)
    b = pd.DataFrame(list(bad), columns=["code", "date"])
    print(f"애프터 편입 불가 (종목,일자) 쌍: {len(b):,}")
    print(f"  영향 종목 {b.code.nunique():,}개 · 전체 종목-일의 "
          f"{len(b)/ (len(days)*1800) * 100:.2f}%")
    per = b.groupby("code").size().sort_values(ascending=False)
    print(f"  종목당 지정일수: 중앙 {per.median():.0f}일 · 평균 {per.mean():.0f}일 · 최대 {per.max()}일")
    print(f"  전 기간(606일) 내내 지정: {(per >= len(days) - 5).sum()}종목")
