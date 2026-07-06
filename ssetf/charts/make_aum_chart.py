"""
현재 기준 AUM 비교 (원화) + SEIBRO 한국인 보유분. 결과는 charts/aum_comparison.png.
- 한국 ETF + 홍콩 ETF stacked(조원). 홍콩 ETF는 [한국인 보유(SEIBRO 보관잔고)] + [기타]로 세분.
- 본주 시가총액은 90~200배 규모라 텍스트 비율로 보조 표기.
기준일: 한국/본주 07-03, 홍콩 AUM 07-02, SEIBRO 보관잔고 07-02(최신).
환율(Naver): USDKRW=1542.5, HKDKRW=196.68.
홍콩 AUM: SK하이닉스=US$8.18B(USD), 삼성=HK$20.81B(HKD). 9747은 동일펀드라 미포함.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
OUTDIR = os.path.dirname(os.path.abspath(__file__))
USDKRW, HKDKRW = 1542.5, 196.68
COL_KR, COL_HK, COL_HKKR = "#0072B2", "#E69F00", "#B36A00"   # 한국 / 홍콩기타 / 홍콩중 한국인
UNDERS = ["Samsung Electronics", "SK Hynix"]   # y축 위쪽이 SK하이닉스가 되도록(아래→위)
NAMES = {"SK Hynix": "SK하이닉스", "Samsung Electronics": "삼성전자"}
HK_AUM_JO = {"SK Hynix": 8.18 * USDKRW / 1000, "Samsung Electronics": 20.81 * HKDKRW / 1000}
ISIN = {"SK Hynix": "HK0001205258", "Samsung Electronics": "HK0001121349"}


def korea_aum_jo():
    d = pd.read_csv("data/krx_all.csv")
    tk = pd.read_csv("tickers.csv").set_index("Ticker")
    d["und"] = d["Symbol"].map(tk["Underlying"])
    lev = tk[tk["Leverage"] == "2x"].index
    d = d[d["Symbol"].isin(lev) & (d["NetAssets"] > 0)]
    latest = d.sort_values("Date").groupby("Symbol").tail(1)
    return (latest.groupby("und")["NetAssets"].sum() / 1e12).to_dict()


def seibro_hk_holdings_jo():
    """홍콩 ETF 중 한국인 보유(SEIBRO 보관잔고, USD) 최신 → 조원."""
    h = pd.read_csv("data/seibro_HK_holdings_leverage_daily.csv", parse_dates=["Date"])
    out = {}
    for u, isin in ISIN.items():
        g = h[h["ISIN"] == isin].sort_values("Date")
        out[u] = (g["보관잔고금액"].iloc[-1] * USDKRW / 1e12) if len(g) else 0.0
    return out


def underlying_jo():
    d = pd.read_csv("data/underlying_krx_mktcap.csv").set_index("Underlying")
    return (d["MktCap_KRW"] / 1e12).to_dict()


def main():
    kr, mc, hkkr = korea_aum_jo(), underlying_jo(), seibro_hk_holdings_jo()
    y = np.arange(len(UNDERS))
    fig, ax = plt.subplots(figsize=(12, 5.8))

    for i, u in enumerate(UNDERS):
        k = kr.get(u, 0)                 # 한국 ETF
        hk_all = HK_AUM_JO[u]            # 홍콩 ETF 총
        hk_kr = min(hkkr[u], hk_all)     # 홍콩 중 한국인 보유
        hk_etc = hk_all - hk_kr          # 홍콩 기타
        # 세그먼트: 한국 | 홍콩(한국인) | 홍콩(기타)
        ax.barh(i, k, color=COL_KR, height=0.5)
        ax.barh(i, hk_kr, left=k, color=COL_HKKR, height=0.5)
        ax.barh(i, hk_etc, left=k + hk_kr, color=COL_HK, height=0.5)
        ax.text(k / 2, i, f"{k:.1f}", va="center", ha="center", color="white",
                fontsize=10, fontweight="bold")
        ax.text(k + hk_kr + hk_etc / 2, i, f"{hk_etc:.1f}", va="center", ha="center",
                color="white", fontsize=10, fontweight="bold")
        tot = k + hk_all
        ax.text(tot + 0.25, i + 0.20, f"ETF 합 {tot:.1f}조  (본주 시총의 {tot/mc[u]*100:.2f}%)",
                va="center", ha="left", fontsize=9.5, fontweight="bold", color="#333")
        ax.text(tot + 0.25, i - 0.05,
                f"└ 홍콩 중 한국인 보유(SEIBRO) {hk_kr:.2f}조 = 홍콩의 {hk_kr/hk_all*100:.1f}%",
                va="center", ha="left", fontsize=9, color=COL_HKKR, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels([NAMES[u] for u in UNDERS], fontsize=13, fontweight="bold")
    ax.set_xlabel("ETF 순자산총액 AUM (조원)")
    ax.set_xlim(0, max(kr.get(u, 0) + HK_AUM_JO[u] for u in UNDERS) * 1.7)
    ax.set_title("삼성·SK하이닉스 레버리지 ETF AUM — 한국 vs 홍콩 (홍콩 중 한국인 보유 SEIBRO)",
                 fontsize=13.5, fontweight="bold", loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (COL_KR, COL_HKKR, COL_HK)]
    ax.legend(handles, ["한국 ETF (7종목 합산)", "홍콩 중 한국인 보유(SEIBRO)", "홍콩 ETF (기타)"],
              frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, axis="x", alpha=0.25, lw=0.6)
    fig.text(0.02, -0.03,
             "· 한국=KRX 순자산총액 합산(7종목, 07-03), 홍콩=HKEX 공식 AUM(07-02)  "
             "· 홍콩 중 한국인 보유=SEIBRO 보관잔고(07-02, USD)  · 본주 시총=005930·000660 KRX  "
             "· 인버스·런던 제외  · 환율 Naver  · 출처 KRX·HKEX·SEIBro·Naver",
             fontsize=7.5, color="#666")
    fig.tight_layout()
    out = os.path.join(OUTDIR, "aum_comparison.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"[완료] {out}")
    for u in UNDERS:
        tot = kr.get(u, 0) + HK_AUM_JO[u]
        print(f"  {NAMES[u]}: 한국 {kr.get(u,0):.1f} + 홍콩 {HK_AUM_JO[u]:.1f}(그중 한국인 {hkkr[u]:.2f}, "
              f"{hkkr[u]/HK_AUM_JO[u]*100:.1f}%) = {tot:.1f}조 | 본주시총의 {tot/mc[u]*100:.2f}%")


if __name__ == "__main__":
    main()
