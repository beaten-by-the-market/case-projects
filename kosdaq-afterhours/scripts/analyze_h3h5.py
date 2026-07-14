"""H3. 인력 단위 손익(수수료율 역산) · H5. 가격충격(투자자 보호).

H3: 종목을 KRX 거래대금 내림차순으로 70종목씩(= 담당자 1인 = 연봉 1억) 끊고,
    **1억을 회수하는 데 필요한 수수료율**을 역산한다. 수수료율을 가정하지 않는다.
    분모는 NXT 거래대금(프리+메인+애프터 합) = **애프터 수익의 후한 상한** → 필요 수수료율의 하한.

H5: Amihud 비유동성 = mean(|일간수익률%| / 일간거래대금(억)) = "1억 거래가 가격을 몇 % 움직이는가".
    애프터는 정규장보다 유동성이 얇으므로, 정규장 측정치는 애프터 위험의 **하한**이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"
pd.set_option("display.width", 240)

억 = 1e8
조 = 1e12
YRS_KRX = 606 / 242        # KRX·공시 기간 (년)
YRS_NXT = 310 / 242        # NXT 기간 (년)
PER_HEAD = 70              # 담당자 1인당 종목수 (운영 기준)
SALARY = 1e8               # 연봉 1억


def h3(df, nxt):
    s = df.sort_values("amt_avg", ascending=False).copy()
    s["head"] = np.arange(len(s)) // PER_HEAD + 1
    s["nxt_amt"] = nxt.reindex(s.index).fillna(0)

    g = s.groupby("head").apply(lambda x: pd.Series({
        "종목수": len(x),
        "순위": f"{(x.head_rank.min()):,}~{(x.head_rank.max()):,}",
        "연KRX거래대금_조": x.amt_sum.sum() / YRS_KRX / 조,
        "연NXT거래대금_조": x.nxt_amt.sum() / YRS_NXT / 조,
        "NXT거래종목": int((x.nxt_amt > 0).sum()),
        "연애프터공시": x.susi_after.sum() / YRS_KRX,
    }), include_groups=False)

    # 필요 수수료율 = 연봉 1억 ÷ 그 묶음의 연간 NXT 거래대금  (bp = 1/10,000)
    g["필요수수료율_bp"] = SALARY / (g.연NXT거래대금_조 * 조) * 10000
    g["필요수수료율_pct"] = SALARY / (g.연NXT거래대금_조 * 조) * 100
    return g


def h5(ohlc, deciles):
    """⚠ 무거래일을 섞으면 안 된다.

    저유동성 종목은 체결이 없는 날이 많고(D10은 30%), 그런 날은 변동폭이 0이라 평균을 희석한다.
    무거래일을 포함해 평균내면 "D10이 D1보다 덜 움직인다"는 거꾸로 된 결과가 나온다.
    → **거래가 있었던 날(거래량>0)만으로 계산한다.**

    Amihud 는 **중앙값**을 쓴다. 평균은 거래대금이 극히 작은 하루에 폭발한다.
    """
    o = ohlc.sort_values(["code", "date"]).copy()
    o["prev"] = o.groupby("code").close.shift(1)
    o = o[(o.prev > 0) & (o.close > 0) & (o.vol > 0)]       # 거래일만
    o["ret"] = (o.close / o.prev - 1) * 100                 # %
    o["intraday"] = (o.high - o.low) / o.prev * 100         # %
    o["illiq"] = o.ret.abs() / (o.amt / 억)                 # % per 억원

    per = pd.DataFrame({
        "amihud": o.groupby("code").illiq.median(),
        "intraday": o.groupby("code").intraday.mean(),
        "ext15": o.groupby("code").apply(lambda x: (x.ret.abs() >= 15).mean() * 100,
                                         include_groups=False),
        "vol": o.groupby("code").ret.std(),
    })
    per = per.join(deciles, how="inner")
    # 애프터 세션의 전형적 소액 주문이 주가를 얼마나 움직이는가
    per["충격_5천만원_pct"] = per.amihud * 0.5
    per["충격_1억원_pct"] = per.amihud * 1.0

    t = per.groupby("decile", observed=True).agg(
        종목수=("amihud", "size"),
        Amihud_중앙=("amihud", "median"),
        일중변동폭_pct=("intraday", "median"),
        일간변동성_pct=("vol", "median"),
        극단15pct_일비율=("ext15", "median"),
        충격_5천만원_pct=("충격_5천만원_pct", "median"),
        충격_1억원_pct=("충격_1억원_pct", "median"),
    )
    return per, t


def main():
    df = pd.read_csv(OUT / "h2_stock.csv", dtype={"code": str}).set_index("code")

    n = pd.read_csv(DATA / "daily_nxt.csv", dtype={"code": str, "date": str})
    n = n[n.fam == "m223"]
    nxt = ((n.amt_sell.fillna(0) + n.amt_buy.fillna(0)) / 2).groupby(n.code).sum()

    # ── H3 ──
    df = df.sort_values("amt_avg", ascending=False)
    df["head_rank"] = np.arange(1, len(df) + 1)
    g = h3(df, nxt)

    print(f"=== H3. 담당자 1인(70종목·연 1억) 단위 손익. 수수료율 역산 ===")
    print(f"    코스닥 {len(df):,}종목 → 담당자 {len(g)}명 = 연 {len(g)}억\n")
    show = g[["순위", "연KRX거래대금_조", "연NXT거래대금_조", "NXT거래종목",
              "연애프터공시", "필요수수료율_pct"]].copy()
    show.columns = ["담당종목 순위", "연 KRX거래대금(조)", "연 NXT거래대금(조)",
                    "NXT거래 종목수", "연 애프터공시", "1억 회수 필요 수수료율(%)"]
    print(show.round(3).to_string())

    print(f"\n--- 읽는 법 ---")
    print(f"  NXT 거래대금은 프리+메인+애프터 합 = **애프터 수익의 상한**.")
    print(f"  따라서 위 '필요 수수료율'은 가장 후한 값(하한)이다. 실제 애프터에선 더 높아야 한다.")
    nxt_zero = g[g.연NXT거래대금_조 == 0]
    print(f"\n  NXT 거래대금이 **0**인 담당자: {len(nxt_zero)}명 "
          f"(담당 {int(nxt_zero.종목수.sum()):,}종목) → 애프터 수수료 수익 0. 회수 불가능.")
    tiny = g[(g.연NXT거래대금_조 > 0) & (g.필요수수료율_pct > 0.1)]
    print(f"  필요 수수료율이 0.1%(10bp)를 넘는 담당자: {len(tiny)}명")

    # ── H5 ──
    o = pd.read_csv(DATA / "ohlc_kosdaq.csv", dtype={"code": str, "date": str})
    per, t = h5(o, df[["decile"]])
    print(f"\n\n=== H5. 가격충격 (투자자 보호) ===")
    print("  Amihud = 1억원 거래가 주가를 몇 % 움직이는가.  숫자가 클수록 얇고 위험하다.\n")
    print(t.round(3).to_string())

    d1, d10 = t.loc["D1"], t.loc["D10"]
    print(f"\n--- D1 vs D10 (거래일만) ---")
    print(f"  Amihud(중앙)      : {d1.Amihud_중앙:.4f}  vs  {d10.Amihud_중앙:.4f}  "
          f"(**{d10.Amihud_중앙/d1.Amihud_중앙:,.0f}배**)")
    print(f"  5천만원 주문 충격 : {d1.충격_5천만원_pct:.3f}%  vs  {d10.충격_5천만원_pct:.2f}%")
    print(f"  일중 변동폭       : {d1.일중변동폭_pct:.2f}%  vs  {d10.일중변동폭_pct:.2f}%")
    print(f"  |수익률|≥15% 일   : {d1.극단15pct_일비율:.2f}%  vs  {d10.극단15pct_일비율:.2f}%")

    print(f"\n  → 정규장에서조차 D10은 1억원 거래로 주가가 {d10.Amihud_중앙:.2f}% 움직인다.")
    print(f"    애프터는 정규장보다 유동성이 얇다 → 이 값은 애프터 위험의 **하한**이다.")
    print(f"\n  ⚠ 정직하게: 일간 변동성·극단수익률 자체는 D1(코스닥 대형 테마·바이오주)이 더 클 수 있다.")
    print(f"    H5의 논거는 '많이 움직인다'가 아니라 **'적은 돈으로 움직인다'(Amihud)** 이다.")

    g.round(4).to_csv(OUT / "h3_heads.csv", encoding="utf-8-sig")
    per.round(4).to_csv(OUT / "h5_stock.csv", encoding="utf-8-sig")
    t.round(4).to_csv(OUT / "h5_decile.csv", encoding="utf-8-sig")
    print(f"\n저장: {OUT}/h3_*.csv · h5_*.csv")


if __name__ == "__main__":
    main()
