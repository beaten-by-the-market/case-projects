"""FINDINGS 용 차트 3장.

  1. 메인. 누적 거래대금 vs 누적 애프터 수시공시 (두 곡선의 벌어짐 = 전종목 편입의 순손실)
  2. decile별 Amihud 가격충격 (투자자 보호 근거)
  3. 규칙별 효율 프론티어 (포기 거래대금 vs 절감 인력)

팔레트는 검증된 값(validate_palette.js PASS): blue #2a78d6 · red #e34948, surface #fcfcfb.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
OUT = Path(__file__).resolve().parent.parent / "output"

BLUE, RED = "#2a78d6", "#e34948"
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8985"
GRID = "#e6e5e1"

plt.rcParams.update({
    "font.family": ["Malgun Gothic", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.linewidth": 1,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.8,
})
pct = FuncFormatter(lambda v, _: f"{v:.0f}%")


def titled(fig, ax, title, sub):
    """제목/부제를 축 밖에 배치한다 (tight_layout 과 겹치지 않게 상단 여백을 명시적으로 준다)."""
    fig.subplots_adjust(top=0.82)
    ax.text(0, 1.13, title, transform=ax.transAxes, fontsize=15.5, fontweight="bold", color=INK)
    ax.text(0, 1.055, sub, transform=ax.transAxes, fontsize=10, color=INK2)


def chart1():
    """수익 곡선 vs 비용 계단. 종목을 늘릴수록 어디서 적자로 도는가.

    ⚠ **이전 버전은 누적 % 곡선 두 개**여서 양 끝점이 필연적으로 만났다(0%→100%).
    그건 로렌츠 곡선이지 손익 곡선이 아니다. 여기서는 **원(억원) 단위**로 그린다.

      수익 = 누적 NXT 애프터 거래대금(연) × 수수료율 r   ← 상한(프리+메인+애프터 합계)
      비용 = ceil(n/70) × 1억                          ← 담당자 1인 = 70종목 = 연 1억

    **수수료율 r 은 가정하지 않고 역산한다**: BEP(수익=비용)가 **누적 거래대금 96%** 지점에
    오도록 맞춘다. 그림의 요지는 r 값 자체가 아니라 **곡선의 모양**이다.
    수익선은 상위 1,000종목에서 이미 평평해지는데 비용선은 70종목마다 1억씩 계속 올라간다.
    r 을 어떻게 잡든 **BEP 오른쪽은 적자**이며, 그 폭만 달라진다.
    """
    liq = pd.read_csv(OUT / "h1_stock_liquidity.csv", dtype={"code": str})
    liq = liq.sort_values("amt_avg", ascending=False)
    nx = pd.read_csv(OUT.parent / "data/daily_nxt.csv", dtype={"code": str, "date": str})
    nx = nx[nx.fam == "m223"].copy()
    nx["amt"] = nx[["amt_sell", "amt_buy"]].fillna(0).max(axis=1)
    nxt_yr = nx.groupby("code").amt.sum() / (nx.date.nunique() / 242)   # 연환산

    liq["nxt"] = liq.code.map(nxt_yr).fillna(0)
    liq["krx"] = liq.amt_sum / (606 / 242)
    n = np.arange(1, len(liq) + 1)
    cum_krx_pct = (liq.krx.cumsum() / liq.krx.sum() * 100).values
    cum_nxt = liq.nxt.cumsum().values

    cost = np.ceil(n / 70) * 1e8                    # 원/년
    n96 = int(np.searchsorted(cum_krx_pct, 96.0) + 1)
    r = cost[n96 - 1] / cum_nxt[n96 - 1]            # ← BEP가 96%에 오도록 역산
    rev = cum_nxt * r

    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    e = 1e8                                          # 억원
    ax.fill_between(n, rev / e, cost / e, where=(cost >= rev), color=RED, alpha=0.10, lw=0)
    ax.fill_between(n, rev / e, cost / e, where=(rev > cost), color=BLUE, alpha=0.08, lw=0)
    ax.plot(n, rev / e, color=BLUE, lw=2.2, zorder=3)
    ax.step(n, cost / e, where="post", color=RED, lw=2.2, zorder=3)

    ax.axvline(n96, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.plot([n96], [cost[n96 - 1] / e], "o", ms=9, color=INK, mec=SURFACE, mew=2, zorder=5)
    ax.annotate(f"손익분기: {n96:,}번째 종목\n(누적 거래대금 96%)",
                (n96, cost[n96 - 1] / e), xytext=(-16, 30), textcoords="offset points",
                ha="right", fontsize=11.5, fontweight="bold", color=INK, linespacing=1.4)

    loss = (cost[-1] - rev[-1]) / e
    ax.annotate(f"여기서부터 적자\n"
                f"마지막 {len(liq) - n96:,}종목이 비용을 {loss:.0f}억 더 쓰는데\n"
                f"수익은 늘지 않는다",
                xy=(1560, (cost[-1] / e + rev[-1] / e) / 2), xytext=(1180, 6.5),
                ha="center", va="center", fontsize=11, fontweight="bold", color=RED,
                linespacing=1.5,
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.4,
                                connectionstyle="arc3,rad=-0.25", shrinkA=8, shrinkB=4))

    ax.text(150, 20.5, "수익: 누적 애프터 거래대금 × 수수료율\n(NXT 기준 = 상한)",
            color=BLUE, fontsize=10.5, fontweight="bold", ha="left", va="center", linespacing=1.4)
    ax.text(560, 4.0, "비용: 공시담당자\n(70종목당 연 1억)",
            color=RED, fontsize=10.5, fontweight="bold", ha="center", va="center", linespacing=1.4)

    ax.set_xlim(0, len(liq)); ax.set_ylim(0, cost[-1] / e * 1.13)
    ax.set_xlabel("거래대금 내림차순 누적 종목수", fontsize=10.5)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}억"))
    ax.grid(axis="y", zorder=0)
    titled(fig, ax, "종목을 늘릴수록, 수익은 멈추고 비용만 오른다",
           f"코스닥 {len(liq):,}종목 · 연 환산 · 수수료율은 BEP가 96%에 오도록 역산({r * 1e4:.3f}bp) · 간이 예시")
    fig.savefig(OUT / "fig1_cumulative.png", dpi=170, bbox_inches="tight")
    print(f"  fig1_cumulative.png  (BEP {n96}번째 · r={r * 1e4:.3f}bp · 전종목 순손실 {loss:.1f}억)")


def chart2():
    t = pd.read_csv(OUT / "h5_decile.csv").set_index("decile")
    t = t.loc[[f"D{i}" for i in range(1, 11)]]
    ramp = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
            "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

    fig, ax = plt.subplots(figsize=(10, 5.6))
    b = ax.bar(t.index, t.Amihud_중앙, color=ramp, width=0.68, zorder=3)
    for r, v in zip(b, t.Amihud_중앙):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.05, f"{v:.2f}",
                ha="center", fontsize=10, color=INK2, fontweight="bold")

    ax.set_ylim(0, t.Amihud_중앙.max() * 1.18)
    ax.set_xlabel("유동성 decile  (D1 = 거래대금 상위 10%)", fontsize=10.5)
    ax.set_ylabel("1억원 거래 시 주가 변동 (%)", fontsize=10.5)
    ax.grid(axis="y", zorder=0)
    titled(fig, ax, "저유동성 종목은 1억원 주문에도 주가가 크게 튄다",
           "Amihud 비유동성(중앙값) · 거래일만 · D10은 D1의 59배. 애프터는 정규장보다 얇으므로 이 값은 하한")
    fig.savefig(OUT / "fig2_amihud.png", dpi=170, bbox_inches="tight")
    print("  fig2_amihud.png")


def chart3():
    r = pd.read_csv(OUT / "h4_recommended.csv")
    r["절감인력_pct"] = r.절감인건비_억 / 26 * 100
    fig, ax = plt.subplots(figsize=(9.4, 5.8))

    ax.plot(r.포기_NXT거래대금_pct, r.절감인력_pct, color=BLUE, lw=2, zorder=2)
    ax.scatter(r.포기_NXT거래대금_pct, r.절감인력_pct, s=90, color=BLUE,
               edgecolor=SURFACE, lw=2, zorder=3)

    labels = ["일평균 <1억 배제", "<3억", "<5억  ← 권고", "<10억"]
    for (x, y), lab in zip(zip(r.포기_NXT거래대금_pct, r.절감인력_pct), labels):
        bold = "권고" in lab
        ax.annotate(lab, (x, y), xytext=(10, -4), textcoords="offset points",
                    fontsize=11 if bold else 10,
                    fontweight="bold" if bold else "normal",
                    color=RED if bold else INK2)

    ax.set_xlim(-0.06, 1.55); ax.set_ylim(0, 66)
    ax.set_xlabel("포기하는 애프터 거래대금 (NXT 기준 = 상한)", fontsize=10.5)
    ax.set_ylabel("절감되는 공시 인력", fontsize=10.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ax.yaxis.set_major_formatter(pct)
    ax.grid(zorder=0)
    titled(fig, ax, "거래대금은 거의 잃지 않고 인력은 크게 준다",
           "히스테리시스 규칙(제외 <X / 재편입 >2X)을 5개 반기 굴린 최종 상태 기준")
    fig.savefig(OUT / "fig3_frontier.png", dpi=170, bbox_inches="tight")
    print("  fig3_frontier.png")


if __name__ == "__main__":
    chart1(); chart2(); chart3()
    print(f"\n저장 위치: {OUT}")
