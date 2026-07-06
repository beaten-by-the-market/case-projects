"""
한국인의 홍콩 상장 삼성·SK하이닉스 레버리지 ETF 보유금액(SEIBRO 보관잔고) 추이
 + 아래 패널: 홍콩 대표 ETF 종가(≈NAV) 추이 → 보유금액 감소가 '가격 급락'탓인지 '수량'탓인지 구별.
결과: charts/seibro_hk_holdings.png.

- 위: 보관잔고(억원, 원화환산). SEIBRO는 종가로 평가.
- 아래: 홍콩 대표 ETF(SK하이닉스 7709 / 삼성 7747) 종가, 2025-11-03=100 지수.
  두 패널의 급락이 같은 시점이면 → 보유금액 감소는 '가격'탓(수량 아님).
주의(top50 절단): 잔고는 순위 진입 시점부터(SK하이닉스 2025-11-03~, 삼성 2025-11-26~).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
OUTDIR = os.path.dirname(os.path.abspath(__file__))
COLOR = {"SK하이닉스 2x (7709)": "#0072B2", "삼성 2x (7747/9747)": "#D55E00"}
LABEL = {"SK하이닉스 2x (7709)": "SK하이닉스 (7709)", "삼성 2x (7747/9747)": "삼성 (7747/9747)"}
PRICE_SYM = {"SK하이닉스 2x (7709)": "7709.HK", "삼성 2x (7747/9747)": "7747.HK"}
BASE = "2025-11-03"   # 지수 기준일


def main():
    h = pd.read_csv("data/seibro_HK_holdings_leverage_daily.csv", parse_dates=["Date"])
    fx = pd.read_csv("data/fx_USDKRW_naver.csv"); fx["Date"] = pd.to_datetime(fx["Date"])
    h = pd.merge_asof(h.sort_values("Date"), fx.sort_values("Date"), on="Date", direction="backward")
    h["억원"] = h["보관잔고금액"] * h["Rate"] / 1e8

    px = pd.read_csv("data/hkex_all.csv"); px["Date"] = pd.to_datetime(px["Date"])
    kr_listing = pd.to_datetime(pd.read_csv("data/krx_all.csv")["Date"].min())

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})

    # --- 위: 보관잔고 ---
    for key, col in COLOR.items():
        g = h[h["종목구분"] == key].sort_values("Date")
        ax1.plot(g["Date"], g["억원"], color=col, lw=2, label=LABEL[key])
        if len(g):
            last = g.iloc[-1]
            ax1.annotate(f"{last['억원']:,.0f}억", (last["Date"], last["억원"]),
                         textcoords="offset points", xytext=(8, 0), va="center",
                         fontsize=10, fontweight="bold", color=col)
    ax1.set_ylabel("한국인 보유금액 (억원)")
    ax1.set_ylim(bottom=0)
    ax1.set_title("한국인의 홍콩상장 삼성·SK하이닉스 레버리지 ETF 보유금액 vs 종가(NAV 근사)",
                  fontsize=14, fontweight="bold", loc="left")
    ax1.legend(frameon=False, loc="upper left")

    # --- 아래: 대표 ETF 종가 지수(=100) ---
    for key, col in COLOR.items():
        g = px[px["Symbol"] == PRICE_SYM[key]].sort_values("Date")
        g = g[g["Date"] >= BASE]
        if len(g):
            idx = g["Close"] / g["Close"].iloc[0] * 100
            ax2.plot(g["Date"], idx, color=col, lw=2, label=f"{LABEL[key]} 종가")
            ax2.annotate(f"{idx.iloc[-1]:.0f}", (g['Date'].iloc[-1], idx.iloc[-1]),
                         textcoords="offset points", xytext=(8, 0), va="center",
                         fontsize=10, fontweight="bold", color=col)
    ax2.axhline(100, color="#bbb", lw=0.8, ls=":")
    ax2.set_ylabel(f"홍콩 ETF 종가 지수\n({BASE}=100)")
    ax2.set_ylim(bottom=0)

    # 국내 ETF 상장 수직선 (양 패널)
    for ax in (ax1, ax2):
        ax.axvline(kr_listing, color="#444", ls="--", lw=1.3, zorder=1)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, axis="y", alpha=0.25, lw=0.6)
    ax1.annotate(f"국내 ETF 상장\n({kr_listing.date()})", (kr_listing, ax1.get_ylim()[1]),
                 textcoords="offset points", xytext=(6, -6), va="top", ha="left",
                 fontsize=9.5, fontweight="bold", color="#444")

    fig.text(0.02, 0.005,
             "· 위=SEIBRO 보관잔고(HK, USD→원)  · 아래=홍콩 대표 ETF 종가 지수  "
             "· SEIBRO는 보유를 '종가'로 평가 → 두 패널 급락 동조 시 감소는 '가격'탓  "
             "· 잔고 top50 진입시점부터(SKH 11-03·삼성 11-26)  · 출처 SEIBro·HKEX·Naver",
             fontsize=7.5, color="#666")
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    out = os.path.join(OUTDIR, "seibro_hk_holdings.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"[완료] {out}")
    for key in COLOR:
        g = h[h["종목구분"] == key].sort_values("Date")
        p = px[px["Symbol"] == PRICE_SYM[key]].sort_values("Date")
        p = p[p["Date"] >= BASE]
        pk_h = g["억원"].max(); last_h = g["억원"].iloc[-1]
        pk_p = (p["Close"]/p["Close"].iloc[0]*100).max(); last_p = p["Close"].iloc[-1]/p["Close"].iloc[0]*100
        print(f"  {LABEL[key]}: 보유 정점 {pk_h:,.0f}→최근 {last_h:,.0f}억({last_h/pk_h*100:.0f}%) | "
              f"종가지수 정점 {pk_p:.0f}→최근 {last_p:.0f}({last_p/pk_p*100:.0f}%)")


if __name__ == "__main__":
    main()
