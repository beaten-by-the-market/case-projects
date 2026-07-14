"""H4. 배제 기준 설계·평가. 이 연구의 최종 산출물.

규칙이 되려면 세 조건을 만족해야 한다.
  ① 사전 관측 가능. 직전 6개월 실적으로 다음 반기 편입 여부가 결정된다.
  ② 안정적. 종목이 기준선을 매 반기 넘나들면 운영 불가. turnover 로 실측한다.
  ③ 형평성 방어. 사전 공표 · 정기 리밸런싱 · 신규상장 유예.

포기 거래대금은 **NXT 기준**으로 잰다(= 애프터 수익의 상한). 여기서 "1%만 포기"가 나오면
실제 애프터에서는 그보다 더 적게 포기한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

import classify as C  # noqa: E402

_force_utf8_stdout()
ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"
pd.set_option("display.width", 250)

억 = 1e8
PER_HEAD = 70
HALVES = [("2024H1", "20240101", "20240630"), ("2024H2", "20240701", "20241231"),
          ("2025H1", "20250101", "20250630"), ("2025H2", "20250701", "20251231"),
          ("2026H1", "20260101", "20260630")]


def load():
    df = pd.read_csv(OUT / "h2_stock.csv", dtype={"code": str}).set_index("code")
    h5 = pd.read_csv(OUT / "h5_stock.csv", dtype={"code": str}).set_index("code")
    df = df.join(h5[["amihud"]])

    n = pd.read_csv(DATA / "daily_nxt.csv", dtype={"code": str, "date": str})
    n = n[n.fam == "m223"]
    df["nxt_amt"] = ((n.amt_sell.fillna(0) + n.amt_buy.fillna(0)) / 2).groupby(n.code).sum()
    df["nxt_amt"] = df.nxt_amt.fillna(0)

    # C5 질적 기준: 관리종목·투자주의환기·불성실공시법인 지정 이력
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna()]
    bad = g[g.title.str.contains("관리종목|투자주의환기|불성실공시법인", na=False)
            & ~g.title.str.contains("해제|해소", na=False)]
    df["flagged"] = df.index.isin(bad.code.unique())
    return df


def evaluate(df, mask, name):
    """mask = 배제할 종목."""
    keep, drop = df[~mask], df[mask]
    return {
        "기준": name,
        "제외종목": len(drop),
        "잔존종목": len(keep),
        "포기_NXT거래대금_pct": drop.nxt_amt.sum() / df.nxt_amt.sum() * 100,
        "포기_KRX거래대금_pct": drop.amt_sum.sum() / df.amt_sum.sum() * 100,
        "절감_애프터공시_pct": drop.susi_after.sum() / df.susi_after.sum() * 100,
        "필요담당자": np.ceil(len(keep) / PER_HEAD),
        "절감인건비_억": np.ceil(len(df) / PER_HEAD) - np.ceil(len(keep) / PER_HEAD),
        "제외종목_Amihud중앙": drop.amihud.median(),
    }


def half_avg(d):
    """반기별 종목 일평균 거래대금."""
    out = {}
    for name, s, e in HALVES:
        h = d[(d.date >= s) & (d.date <= e)]
        out[name] = h.groupby("code").amt.sum() / h.date.nunique()
    return out


def turnover(df):
    """반기 리밸런싱 시 제외 목록이 얼마나 물갈이되는가. 높으면 규칙으로 못 쓴다.

    두 지표를 함께 본다 (하나만 보면 오해한다):
      · 제외목록 turnover = |대칭차| / |합집합| . 제외 명단이 얼마나 뒤집히는가
      · 전체 대비 변경률  = |대칭차| / 전체종목수. 실제 운영 부담
    """
    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    d = d[d.fam == "m003"]
    d["amt"] = (d.amt_sell.fillna(0) + d.amt_buy.fillna(0)) / 2
    avgs = half_avg(d)
    N = len(df)

    print("\n=== 규칙 안정성 (반기 리밸런싱) ===")

    print("\n  [단순 기준] 직전 반기 일평균 거래대금 < X 면 제외")
    for cut, lab in [(1e8, "<1억"), (3e8, "<3억"), (5e8, "<5억")]:
        prev, a, b = None, [], []
        for name, _, _ in HALVES:
            cur = set(avgs[name][avgs[name] < cut].index)
            if prev is not None:
                ch = len(prev ^ cur)
                a.append(ch / len(prev | cur) * 100)
                b.append(ch / N * 100)
            prev = cur
        print(f"    {lab:6s} 제외목록 turnover {np.mean(a):5.1f}%  ·  전체 대비 변경 {np.mean(b):4.1f}%")

    print("\n  [히스테리시스] 제외는 < X, 재편입은 > 2X 를 넘어야 함 (경계 진동 차단)")
    for cut, lab in [(1e8, "<1억 / 재편입 >2억"), (3e8, "<3억 / 재편입 >6억"),
                     (5e8, "<5억 / 재편입 >10억")]:
        excluded, a, b = set(), [], []
        for i, (name, _, _) in enumerate(HALVES):
            av = avgs[name]
            newly = set(av[av < cut].index) - excluded          # 새로 제외
            back = {c for c in excluded if c in av.index and av[c] > 2 * cut}  # 재편입
            cur = (excluded | newly) - back
            if i > 0:
                ch = len(excluded ^ cur)
                a.append(ch / max(len(excluded | cur), 1) * 100)
                b.append(ch / N * 100)
            excluded = cur
        print(f"    {lab:18s} 제외목록 turnover {np.mean(a):5.1f}%  ·  전체 대비 변경 {np.mean(b):4.1f}%"
              f"  ·  최종 제외 {len(excluded):,}종목")


def main():
    df = load()
    N = len(df)
    heads_all = int(np.ceil(N / PER_HEAD))
    print(f"=== H4. 배제 기준 평가 ===")
    print(f"    코스닥 {N:,}종목 · 전종목 편입 시 담당자 {heads_all}명 = 연 {heads_all}억\n")

    rows = [{"기준": "없음 (거래소 안)", "제외종목": 0, "잔존종목": N,
             "포기_NXT거래대금_pct": 0.0, "포기_KRX거래대금_pct": 0.0,
             "절감_애프터공시_pct": 0.0, "필요담당자": heads_all, "절감인건비_억": 0,
             "제외종목_Amihud중앙": np.nan}]

    for cut, lab in [(1e8, "1억"), (3e8, "3억"), (5e8, "5억"), (10e8, "10억")]:
        rows.append(evaluate(df, df.amt_avg < cut, f"C1  일평균 거래대금 < {lab}"))
    rows.append(evaluate(df, df.no_trade_pct > 20, "C2  무거래일 > 20%"))
    for q, lab in [(0.30, "하위 30%"), (0.50, "하위 50%")]:
        rows.append(evaluate(df, df.amt_avg <= df.amt_avg.quantile(q), f"C3  거래대금 {lab}"))
    rows.append(evaluate(df, df.mktcap < 500 * 억, "C4  시가총액 < 500억"))
    rows.append(evaluate(df, df.flagged, "C5  관리·환기·불성실 지정"))
    rows.append(evaluate(df, (df.amt_avg < 3e8) | df.flagged, "C6  C1(<3억) OR C5"))
    rows.append(evaluate(df, df.amihud >= df.amihud.quantile(0.70), "C7  Amihud 상위 30%"))
    rows.append(evaluate(df, df.nxt_amt == 0, "참고: NXT 무거래 종목"))

    t = pd.DataFrame(rows)
    print(t.round(2).to_string(index=False))

    print("\n--- 효율: 담당자 1명(1억)을 줄이려고 포기하는 애프터 거래대금(NXT 상한 기준) ---")
    for _, r in t.iloc[1:].iterrows():
        if r.절감인건비_억 > 0:
            giveup = r.포기_NXT거래대금_pct / 100 * df.nxt_amt.sum() / (310 / 242)   # 연간
            print(f"  {r.기준:26s} 인건비 -{int(r.절감인건비_억):2d}억 · "
                  f"포기 NXT거래대금 {r.포기_NXT거래대금_pct:5.2f}% (연 {giveup/1e12:6.2f}조) · "
                  f"애프터공시 -{r.절감_애프터공시_pct:4.1f}%")

    turnover(df)

    # ── 권고안: 히스테리시스 규칙을 실제로 굴렸을 때의 최종 제외 집합으로 평가 ──
    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    d = d[d.fam == "m003"]
    d["amt"] = (d.amt_sell.fillna(0) + d.amt_buy.fillna(0)) / 2
    avgs = half_avg(d)

    print("\n\n=== 권고안 실측 (히스테리시스 규칙을 5개 반기 굴린 최종 상태) ===")
    rec = []
    for cut, lab in [(1e8, "1억"), (3e8, "3억"), (5e8, "5억"), (10e8, "10억")]:
        excluded = set()
        for name, _, _ in HALVES:
            av = avgs[name]
            excluded |= set(av[av < cut].index)
            excluded -= {c for c in excluded if c in av.index and av[c] > 2 * cut}
        mask = df.index.isin(excluded)
        r = evaluate(df, pd.Series(mask, index=df.index),
                     f"제외 <{lab} / 재편입 >{lab.replace('억','')}×2억")
        rec.append(r)
    rt = pd.DataFrame(rec)
    print(rt.round(2).to_string(index=False))

    rt.round(3).to_csv(OUT / "h4_recommended.csv", index=False, encoding="utf-8-sig")
    t.round(3).to_csv(OUT / "h4_rules.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장: {OUT}/h4_rules.csv · h4_recommended.csv")


if __name__ == "__main__":
    main()
