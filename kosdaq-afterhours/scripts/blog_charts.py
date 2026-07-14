"""블로그용 차트 5장. beaten-by-the-market 스타일(Malgun Gothic · 150dpi · 스틸블루).

REPORT.md의 수치와 **같은 CSV**에서 그린다. 손으로 숫자를 옮기지 않는다.
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

mpl.rcParams["font.family"] = "Malgun Gothic"
mpl.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r"C:\Users\Peter\github\beaten-by-the-market.github.io\assets\images\2026-07-12-kosdaq-afterhours-cut")
OUT.mkdir(parents=True, exist_ok=True)

BLUE, RED, GRAY = "#4682B4", "#e34948", "#b8c4d0"
D = [f"D{i}" for i in range(1, 11)]


def _bar(vals, title, ylab, fname, fmt, log=False, hi_last=True):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    colors = [BLUE] * 10
    if hi_last:
        colors[-1] = RED
    b = ax.bar(D, vals, color=colors, width=0.68, zorder=3)
    for r, v in zip(b, vals):
        ax.annotate(fmt(v), (r.get_x() + r.get_width() / 2, r.get_height()),
                    ha="center", va="bottom", fontsize=8.5, xytext=(0, 2),
                    textcoords="offset points", color="#333")
    if log:
        ax.set_yscale("log")
    ax.set_title(title, fontsize=13, weight="bold", pad=12)
    ax.set_ylabel(ylab, fontsize=10)
    ax.set_xlabel("거래대금 십분위 (D1 = 상위 10%, D10 = 하위 10%)", fontsize=9.5, color="#555")
    ax.grid(axis="y", alpha=0.25, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.margins(y=0.18)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=150)
    plt.close(fig)
    print(f"  {fname}")


h2 = pd.read_csv(ROOT / "output/h2_decile.csv").set_index("decile").reindex(D)
h5 = pd.read_csv(ROOT / "output/h5_decile.csv").set_index("decile").reindex(D)
nxt = pd.read_csv(ROOT / "output/h1_nxt_penetration.csv").set_index("decile").reindex(D)

print("차트 저장:", OUT)
# ⚠ 레이블은 로그값이 아니라 **실제 억원 값**이다(로그는 막대 높이에만 적용).
#    작은 값을 1자리로 자르면 본문 배수가 재현되지 않는다(D10 1.448 → "1.4" → 341÷1.4 = 243배).
_bar(h2["일평균거래대금_억"], "코스닥 십분위별 일평균 거래대금", "억원", "amt.png",
     lambda v: f"{v:,.0f}" if v >= 10 else (f"{v:.1f}" if v >= 2 else f"{v:.2f}"), log=True)

_bar(h2["종목당_연간수시공시"], "십분위별 종목당 연간 수시공시. 막대가 평평하다", "건",
     "gongsi.png", lambda v: f"{v:.1f}")

_bar(h2["거래대금100억당_수시공시"], "거래대금 100억원당 수시공시. 부담은 아래로 갈수록 커진다", "건",
     "per100.png", lambda v: f"{v:.2f}" if v >= 0.1 else f"{v:.3f}")

amihud_col = [c for c in h5.columns if "amihud" in c.lower() or "가격충격" in c or "비유동성" in c][0]
# ⚠ D1은 0.0269 다. 2자리로 자르면 "0.03"이 되어 61배(1.65÷0.027)가 재현되지 않는다.
_bar(h5[amihud_col], "Amihud 비유동성. 1억원 거래가 주가를 몇 % 움직이는가", "%",
     "amihud.png", lambda v: f"{v:.2f}" if v >= 0.1 else f"{v:.3f}")

# NXT: 거래된 종목 수 + 구간 내 전체 종목 수(선)
fig, ax = plt.subplots(figsize=(9, 4.6))
b = ax.bar(D, nxt["NXT거래종목수"], color=[BLUE] * 7 + [RED] * 3, width=0.68, zorder=3)
for r, v in zip(b, nxt["NXT거래종목수"]):
    ax.annotate(f"{int(v)}", (r.get_x() + r.get_width() / 2, r.get_height()),
                ha="center", va="bottom", fontsize=9, xytext=(0, 2), textcoords="offset points")
ax.plot(D, nxt["종목수"], "--", color=GRAY, lw=1.6, zorder=2, label="구간 내 전체 종목 수")
ax.set_title("NXT에서 실제로 거래되는 코스닥 종목 수. 영리 사업자는 이미 선별했다",
             fontsize=13, weight="bold", pad=12)
ax.set_ylabel("종목 수", fontsize=10)
ax.set_xlabel("거래대금 십분위 (D1 = 상위 10%, D10 = 하위 10%)", fontsize=9.5, color="#555")
ax.legend(frameon=False, fontsize=9)
ax.grid(axis="y", alpha=0.25, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.margins(y=0.18)
fig.tight_layout()
fig.savefig(OUT / "nxt.png", dpi=150)
plt.close(fig)
print("  nxt.png")
