"""
거래대금 시계열 차트 (한국 vs 홍콩 ETF + 본주 기준선). 결과는 charts/.

- ETF 거래대금: 한국(KRX) vs 홍콩(HKEX). 홍콩은 Naver 매매기준율로 KRW 환산.
- 본주(삼성전자·SK하이닉스, KRX) 거래대금을 회색 점선 기준선으로 → "ETF가 본주에 육박/추월".
- 런던(LSE)은 상장 3주차 초소형 신상품(일 거래대금 ~수십억원)이라 규모가 4자릿수 배 작아
  메인 비교에서 제외(주석 명시). 원자료는 data/lse_all.csv에 있음.
- 세 계열이 모두 수조원 규모라 선형축(조원)으로 표시.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# 스크립트가 charts/ 안에 있어도 프로젝트 루트 기준으로 data/·tickers.csv 접근
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
COLOR = {"한국 ETF": "#0072B2", "홍콩 ETF": "#E69F00"}   # CVD-safe (Okabe-Ito)
UND_COLOR = "#888888"                                    # 본주 기준선(회색 점선)
EXCH2MKT = {"KRX": "한국 ETF", "HKEX": "홍콩 ETF"}
OUTDIR = "charts"


def load_fx():
    fx = {}
    for cur, f in [("HKD", "fx_HKDKRW_naver.csv"), ("USD", "fx_USDKRW_naver.csv")]:
        d = pd.read_csv(f"data/{f}")
        d["Date"] = pd.to_datetime(d["Date"])
        fx[cur] = d[["Date", "Rate"]].sort_values("Date")
    return fx


def build_etf():
    tk = pd.read_csv("tickers.csv").rename(columns={"Ticker": "Symbol"})
    und = tk.set_index("Symbol")["Underlying"].to_dict()
    exch = tk.set_index("Symbol")["Exchange"].to_dict()
    fx = load_fx()

    def read(path):
        d = pd.read_csv(path)[["Symbol", "Currency", "Date", "Turnover"]]
        d["Date"] = pd.to_datetime(d["Date"])
        return d.dropna(subset=["Turnover"])

    df = pd.concat([read("data/hkex_all.csv"), read("data/krx_all.csv")], ignore_index=True)
    out = []
    for cur, g in df.groupby("Currency"):
        g = g.sort_values("Date")
        if cur == "KRW":
            g["KRW"] = g["Turnover"]
        else:
            g = pd.merge_asof(g, fx[cur], on="Date", direction="backward")
            g["KRW"] = g["Turnover"] * g["Rate"]
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    df["Underlying"] = df["Symbol"].map(und)
    df["Market"] = df["Symbol"].map(lambda s: EXCH2MKT.get(exch.get(s)))
    return (df.groupby(["Underlying", "Market", "Date"])["KRW"].sum()
            .div(1e12).reset_index())            # 조원


def load_underlying():
    d = pd.read_csv("data/underlying_krx_turnover.csv")
    d["Date"] = pd.to_datetime(d["Date"])
    d["조"] = d["Turnover"] / 1e12
    return d


def plot(etf, und):
    os.makedirs(OUTDIR, exist_ok=True)
    unders = ["Samsung Electronics", "SK Hynix"]
    titles = {"Samsung Electronics": "삼성전자", "SK Hynix": "SK하이닉스"}
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    for ax, u in zip(axes, unders):
        # 본주 기준선 (회색 점선)
        us = und[und["Underlying"] == u].sort_values("Date")
        ax.plot(us["Date"], us["조"], color=UND_COLOR, lw=1.5, ls="--",
                label="본주 거래대금(KRX)", zorder=1)
        # ETF (한국/홍콩). 레전드에 구성종목 명시
        hk_compo = {"Samsung Electronics": "7747+9747", "SK Hynix": "7709"}[u]
        labels = {"한국 ETF": "한국 ETF (7종목 합산)", "홍콩 ETF": f"홍콩 ETF ({hk_compo})"}
        sub = etf[etf["Underlying"] == u]
        for mkt in ["한국 ETF", "홍콩 ETF"]:
            s = sub[sub["Market"] == mkt].sort_values("Date")
            if len(s):
                ax.plot(s["Date"], s["KRW"], color=COLOR[mkt], lw=2,
                        label=labels[mkt], zorder=3)
        ax.set_title(titles[u], fontsize=13, fontweight="bold", loc="left")
        ax.set_ylabel("일별 거래대금 (조원)")
        ax.grid(True, axis="y", alpha=0.25, lw=0.6)
        ax.legend(frameon=False, loc="upper left", ncol=3)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(bottom=0)

    fig.suptitle("삼성·SK하이닉스 레버리지 ETF 거래대금 vs 본주 (한국·홍콩)",
                 fontsize=15, fontweight="bold", x=0.09, ha="left")
    fig.text(0.09, 0.005,
             "· 레버리지 ETF 거래대금: 한국(KRX)·홍콩(HKEX, KRW환산). 본주=KRX 거래대금(회색 점선)  "
             "· 런던(LSE)은 초소형 신상품(일 수십억원)이라 규모 4자릿수배 차이로 제외  "
             "· 출처 KRX·HKEX·Naver",
             fontsize=8, color="#666")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    out = os.path.join(OUTDIR, "turnover_timeseries.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"[완료] {out}")
    # 요약: 최근일 ETF/본주 비율
    for u in unders:
        e = etf[etf.Underlying == u].groupby("Date")["KRW"].sum()
        b = und[und.Underlying == u].set_index("Date")["조"]
        last = e.index.max()
        print(f"{titles[u]} {last.date()}: ETF합 {e.loc[last]:.2f}조, 본주 {b.loc[last]:.2f}조, "
              f"ETF/본주 {e.loc[last]/b.loc[last]*100:.0f}%")


if __name__ == "__main__":
    plot(build_etf(), load_underlying())
