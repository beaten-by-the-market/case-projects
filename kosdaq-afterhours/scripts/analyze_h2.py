"""H2. 저유동성 종목의 공시 부담.

핵심 지표는 **절대 건수가 아니라 '거래대금 단위당 공시 건수'** 다.
대형주가 공시를 더 내도 거래대금이 1000배면 단위당 부담은 무시할 만하다. 논증은 거기서 산다.

비용 산정 대상 = **수시공시(기업 제출 + 주요사항보고서)** 뿐. 시장조치·상장조치·통계는 거래소가
스스로 내는 것이므로 뺀다(서술 증거로만 병기).
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
pd.set_option("display.width", 220)

억 = 1e8
YEARS = 606 / 242          # 606 거래일 ≈ 2.50년


def main():
    liq = pd.read_csv(OUT / "h1_stock_liquidity.csv", dtype={"code": str}).set_index("code")

    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna() & (g.code.str.strip() != "")].copy()

    # 지정일(투자경고·위험·관리·환기)의 공시는 애프터 비용이 아니다. 그날 애프터 거래를 안 하므로.
    bad = pd.read_csv(DATA / "ineligible_days.csv", dtype={"code": str, "date": str})
    key = pd.MultiIndex.from_arrays([g.code, g.date])
    n0 = len(g)
    g = g[~key.isin(pd.MultiIndex.from_arrays([bad.code, bad.date]))]
    print(f"지정일 공시 제외: {n0-len(g):,}건 ({(n0-len(g))/n0*100:.1f}%)")
    g["bucket"] = g.title.map(C.bucket)
    g["after"] = g.time.map(C.is_after_hours)
    g["corr"] = g.title.map(C.is_correction)

    susi = g[g.bucket == "수시공시"]
    action = g[g.bucket == "시장조치"]
    print(f"코스닥 공시 {len(g):,} · 수시공시 {len(susi):,} · 시장조치 {len(action):,}")
    print(f"수시공시 중 애프터(15:40~20:00) {susi.after.sum():,} ({susi.after.mean()*100:.1f}%)\n")

    # ── 종목별 집계 ──
    per = pd.DataFrame({
        "susi": susi.groupby("code").size(),
        "susi_after": susi[susi.after].groupby("code").size(),
        "susi_corr": susi[susi["corr"]].groupby("code").size(),
        "action": action.groupby("code").size(),
    })
    df = liq.join(per, how="left").fillna({"susi": 0, "susi_after": 0, "susi_corr": 0, "action": 0})

    # ⚠ 연율화는 **종목별 관측기간**으로 한다. 전 종목을 같은 상수(2.5년)로 나누면,
    #    기간 일부만 상장된 종목의 공시 건수가 실제보다 적게 계산된다.
    df["susi_yr"] = df.susi / df.years
    df["susi_after_yr"] = df.susi_after / df.years
    df["action_yr"] = df.action / df.years

    # ── decile 표 ──
    t = df.groupby("decile", observed=True).apply(lambda x: pd.Series({
        "종목수": len(x),
        "일평균거래대금_억": x.amt_avg.mean() / 억,
        "종목당_연간수시공시": x.susi_yr.mean(),
        "종목당_연간애프터공시": x.susi_after_yr.mean(),
        "거래대금100억당_수시공시": x.susi.sum() / (x.amt_sum.sum() / 억 / 100),
        "애프터공시_점유pct": x.susi_after.sum(),
        "정정비율_pct": x.susi_corr.sum() / x.susi.sum() * 100 if x.susi.sum() else np.nan,
        "종목당_시장조치": x.action_yr.mean(),
        "공시0건_종목pct": (x.susi == 0).mean() * 100,
    }), include_groups=False)
    t["애프터공시_점유pct"] = t["애프터공시_점유pct"] / df.susi_after.sum() * 100

    print("=== H2. 유동성 decile × 공시 (D1=거래대금 상위 10%) ===")
    print(t.round(2).to_string())

    # ── 핵심 대비 ──
    d1, d10 = t.loc["D1"], t.loc["D10"]
    print(f"\n--- 핵심 대비 (D1 vs D10) ---")
    print(f"  일평균 거래대금      : {d1.일평균거래대금_억:>8.1f}억  vs {d10.일평균거래대금_억:>6.2f}억   "
          f"({d1.일평균거래대금_억/d10.일평균거래대금_억:,.0f}배)")
    print(f"  종목당 연간 수시공시 : {d1.종목당_연간수시공시:>8.1f}건  vs {d10.종목당_연간수시공시:>6.1f}건   "
          f"({d1.종목당_연간수시공시/d10.종목당_연간수시공시:.2f}배)")
    print(f"  거래대금 100억당 공시: {d1['거래대금100억당_수시공시']:>8.3f}건  vs "
          f"{d10['거래대금100억당_수시공시']:>6.2f}건   "
          f"(**{d10['거래대금100억당_수시공시']/d1['거래대금100억당_수시공시']:,.0f}배**)")

    # ── 하위 구간 요약 (배제 후보) ──
    print(f"\n--- 하위 구간이 지우는 부담 ---")
    for k in ["D8", "D9", "D10"]:
        pass
    for lo in [6, 8]:
        sub = df[df.decile.isin([f"D{i}" for i in range(lo, 11)])]
        print(f"  D{lo}~D10 ({len(sub):,}종목, 전체의 {len(sub)/len(df)*100:.0f}%): "
              f"거래대금 점유 {sub.amt_sum.sum()/df.amt_sum.sum()*100:4.1f}%  ·  "
              f"애프터 수시공시 점유 {sub.susi_after.sum()/df.susi_after.sum()*100:4.1f}%  ·  "
              f"담당자 {len(sub)/70:.1f}명")

    # ── 메인 차트용: 누적 곡선 ──
    s = df.sort_values("amt_avg", ascending=False)
    cum = pd.DataFrame({
        "n": range(1, len(s) + 1),
        "cum_amt_pct": s.amt_sum.cumsum() / s.amt_sum.sum() * 100,
        "cum_after_gongsi_pct": s.susi_after.cumsum() / s.susi_after.sum() * 100,
    })
    print(f"\n--- 누적 곡선 (거래대금 내림차순) ---")
    print(f"  {'상위N종목':>10} {'누적 거래대금':>12} {'누적 애프터공시':>14}   벌어짐")
    for k in [100, 300, 500, 700, 900, 1100, 1300, 1500]:
        if k <= len(s):
            a = cum.cum_amt_pct.iloc[k - 1]
            b = cum.cum_after_gongsi_pct.iloc[k - 1]
            print(f"  {k:>10,} {a:>11.1f}% {b:>13.1f}%   {a-b:>+6.1f}%p")

    df.to_csv(OUT / "h2_stock.csv", encoding="utf-8-sig")
    t.round(3).to_csv(OUT / "h2_decile.csv", encoding="utf-8-sig")
    cum.to_csv(OUT / "h2_cumulative.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장: {OUT}/h2_*.csv")


if __name__ == "__main__":
    main()
