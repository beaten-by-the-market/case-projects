"""
블룸버그 스타일: 종목별로 [ETF AUM] 위 / [본주 일평균 거래대금] 아래.
- ETF AUM: 한국+홍콩 stacked (2색).
- 본주 거래대금: underlying 주식(005930·000660) KRX 일평균 → 시장구분 없어 단색(회색).
결과: charts/aum_vs_turnover.png. 단위 조원.
기준: AUM 07-02/03, 본주 거래대금 일평균 2026 연초~07-03. 환율(Naver) USDKRW=1542.5, HKDKRW=196.68.
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
WIN_START = "2026-01-01"   # 본주 거래대금 평균: 2026 연초~현재(YTD), Bloomberg "as of this year"에 근접
UNDERS = ["SK Hynix", "Samsung Electronics"]
NAMES = {"SK Hynix": "SK하이닉스", "Samsung Electronics": "삼성전자"}
COL_KR, COL_HK, COL_UND = "#0072B2", "#E69F00", "#888888"
HK_AUM_JO = {"SK Hynix": 8.18 * USDKRW / 1000, "Samsung Electronics": 20.81 * HKDKRW / 1000}


def aum():
    d = pd.read_csv("data/krx_all.csv")
    tk = pd.read_csv("tickers.csv").set_index("Ticker")
    d["und"] = d["Symbol"].map(tk["Underlying"])
    lev = tk[tk["Leverage"] == "2x"].index
    d = d[d["Symbol"].isin(lev) & (d["NetAssets"] > 0)]
    kr = (d.sort_values("Date").groupby("Symbol").tail(1)
          .groupby("und")["NetAssets"].sum() / 1e12).to_dict()
    return {u: {"kr": kr.get(u, 0), "hk": HK_AUM_JO[u]} for u in UNDERS}


def underlying_turnover():
    """본주 일평균 거래대금(조원), 공통기간."""
    d = pd.read_csv("data/underlying_krx_turnover.csv")
    d["Date"] = pd.to_datetime(d["Date"])
    d = d[d["Date"] >= WIN_START]
    return (d.groupby("Underlying")["Turnover"].mean() / 1e12).to_dict()


def main():
    A, T = aum(), underlying_turnover()
    fig, ax = plt.subplots(figsize=(12, 6))
    yt, yl = [], []
    y = 0
    for u in UNDERS:
        yA, yT = y + 0.28, y - 0.28
        # AUM: 한국+홍콩 stacked
        ax.barh(yA, A[u]["kr"], color=COL_KR, height=0.42)
        ax.barh(yA, A[u]["hk"], left=A[u]["kr"], color=COL_HK, height=0.42)
        if A[u]["kr"] > 0.4:
            ax.text(A[u]["kr"] / 2, yA, f"{A[u]['kr']:.1f}", va="center", ha="center",
                    color="white", fontsize=9, fontweight="bold")
        if A[u]["hk"] > 0.4:
            ax.text(A[u]["kr"] + A[u]["hk"] / 2, yA, f"{A[u]['hk']:.1f}", va="center",
                    ha="center", color="white", fontsize=9, fontweight="bold")
        tot = A[u]["kr"] + A[u]["hk"]
        ax.text(tot + 0.3, yA, f"AUM {tot:.1f}조", va="center", ha="left",
                fontsize=9.5, fontweight="bold", color="#333")
        # 본주 거래대금: 단색
        ax.barh(yT, T[u], color=COL_UND, height=0.42)
        ax.text(T[u] + 0.3, yT, f"본주 일거래 {T[u]:.1f}조", va="center", ha="left",
                fontsize=9.5, fontweight="bold", color="#333")
        yt += [yA, yT]
        yl += [f"{NAMES[u]}\nETF AUM", f"{NAMES[u]}\n본주 거래대금"]
        y -= 1.7

    ax.set_yticks(yt)
    ax.set_yticklabels(yl, fontsize=10)
    xmax = max(max(A[u]["kr"] + A[u]["hk"], T[u]) for u in UNDERS) * 1.35
    ax.set_xlim(0, xmax)
    ax.set_xlabel("조원  (ETF AUM=순자산총액 스냅샷 / 본주 거래대금=KRX 일평균 2026 연초~07-03)")
    ax.set_title("삼성·SK하이닉스 — 레버리지 ETF AUM(한국+홍콩) vs 본주 일평균 거래대금",
                 fontsize=13.5, fontweight="bold", loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (COL_KR, COL_HK, COL_UND)]
    ax.legend(handles, ["한국 ETF (7종목 합산)", "홍콩 ETF", "본주 거래대금(KRX)"],
              frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, axis="x", alpha=0.25, lw=0.6)
    fig.text(0.02, -0.02,
             "· 위=ETF AUM(한국+홍콩 stacked), 아래=본주(005930·000660) KRX 일평균 거래대금  "
             "· 홍콩 AUM 원화환산(SK하이닉스 US8.18B·삼성 HK20.81B)  "
             "· 인버스·런던 제외  · 출처 KRX·HKEX·Naver",
             fontsize=7.5, color="#666")
    fig.tight_layout()
    out = os.path.join(OUTDIR, "aum_vs_turnover.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"[완료] {out}")
    for u in UNDERS:
        a = A[u]["kr"] + A[u]["hk"]
        print(f"  {NAMES[u]}: ETF AUM {a:.1f}조 (한국 {A[u]['kr']:.1f}+홍콩 {A[u]['hk']:.1f}) | "
              f"본주 일평균 거래대금 {T[u]:.1f}조 | AUM/거래대금 {a/T[u]:.1f}배")


if __name__ == "__main__":
    main()
