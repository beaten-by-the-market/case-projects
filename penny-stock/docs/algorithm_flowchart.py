# -*- coding: utf-8 -*-
"""
KRX 관리종목 지정·상장폐지 판정 알고리즘 순서흐름도(flowchart) 생성 스크립트.

- Graphviz(dot) 미설치 환경이므로 matplotlib patches로 정통 순서흐름도를 직접 렌더링한다.
- 터미네이터(스타디움) = 시작/종료, 마름모 = 조건분기(Yes/No), 사각형 = 처리/상태.
- 공통 전처리(상단) + 시총 트랙(좌) / 동전주 트랙(우) 을 나란히 배치.
- 한글 폰트: Malgun Gothic. 고해상도 PNG(dpi=200) 저장.

재실행:  python algorithm_flowchart.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle

# ---------------------------------------------------------------- 한글 폰트
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 색상 팔레트
C_START   = "#CFE2F3"   # 시작/허브 (연파랑)
C_DECIDE  = "#ECECEC"   # 결정 마름모 (연회색)
C_PROC    = "#FFFFFF"   # 일반 처리 (흰색)
C_DESIG   = "#F6B26B"   # 지정 (주황)
C_HOLD    = "#FCE5CD"   # 지정 유지 (연주황)
C_DELIST  = "#EA9999"   # 상폐확정 (빨강)
C_RELEASE = "#B6D7A8"   # 해제/정상 (초록)
C_NORMAL  = "#D9EAD3"   # 정상 streak=0 (연초록)
C_WATCH   = "#FFF2CC"   # 관찰/임박 (연노랑)
C_EXCL    = "#D9D9D9"   # 제외/규칙미적용 (회색)
C_EDGE    = "#555555"
C_ARROW   = "#333333"
C_LOOP    = "#8E7CC3"   # 루프 화살표 (보라 점선)

# ---------------------------------------------------------------- 노드 저장소
NODES = {}
ax = None


def add_node(nid, x, y, w, h, text, kind="proc", fc=C_PROC, fs=11, weight="normal"):
    """kind: term(스타디움) / dec(마름모) / proc(사각형) / rproc(둥근사각)"""
    NODES[nid] = dict(x=x, y=y, w=w, h=h, kind=kind)
    if kind == "dec":
        pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
        ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=C_EDGE,
                             linewidth=1.4, zorder=3))
    elif kind == "term":
        r = h / 2.0
        ax.add_patch(FancyBboxPatch((x - w / 2 + r, y - h / 2), w - 2 * r, h,
                     boxstyle=f"round,pad=0,rounding_size={r}", mutation_aspect=1,
                     facecolor=fc, edgecolor=C_EDGE, linewidth=1.4, zorder=3))
    elif kind == "rproc":
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                     boxstyle="round,pad=0,rounding_size=0.35",
                     facecolor=fc, edgecolor=C_EDGE, linewidth=1.4, zorder=3))
    else:  # proc
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h,
                     facecolor=fc, edgecolor=C_EDGE, linewidth=1.4, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, weight=weight,
            zorder=4, linespacing=1.35)


def annot(x, y, text, fs=8.5, color="#666666"):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=color,
            style="italic", zorder=4, linespacing=1.2)


def anchor(nid, side):
    n = NODES[nid]
    x, y, w, h = n["x"], n["y"], n["w"], n["h"]
    if side == "top":
        return (x, y + h / 2)
    if side == "bottom":
        return (x, y - h / 2)
    if side == "left":
        return (x - w / 2, y)
    if side == "right":
        return (x + w / 2, y)
    return (x, y)


def connect(a, sa, b, sb, label=None, rad=0.0, dashed=False, color=None,
            lw=1.7, label_t=0.42, label_dx=0.0, label_dy=0.0, lfs=11):
    pA = anchor(a, sa)
    pB = anchor(b, sb)
    color = color or (C_LOOP if dashed else C_ARROW)
    style = "--" if dashed else "-"
    arr = FancyArrowPatch(pA, pB, arrowstyle="-|>", mutation_scale=17,
                          linewidth=lw, color=color, linestyle=style,
                          connectionstyle=f"arc3,rad={rad}", shrinkA=3, shrinkB=3,
                          zorder=5)
    ax.add_patch(arr)
    if label:
        lx = pA[0] + (pB[0] - pA[0]) * label_t + label_dx
        ly = pA[1] + (pB[1] - pA[1]) * label_t + label_dy
        ax.text(lx, ly, label, ha="center", va="center", fontsize=lfs,
                weight="bold", color="#222222", zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))


def cluster(x0, y0, x1, y1, title, fc, tc):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=fc, edgecolor=tc,
                 linewidth=1.6, linestyle=(0, (6, 4)), zorder=0, alpha=0.55))
    ax.text(x0 + 0.4, y1 - 0.9, title, ha="left", va="center", fontsize=15,
            weight="bold", color=tc, zorder=1)


# ================================================================ 캔버스
fig, ax = plt.subplots(figsize=(27, 33))
ax.set_xlim(-1, 53)
ax.set_ylim(-6, 61)
ax.set_aspect("equal")
ax.axis("off")

# 제목
ax.text(26, 60, "KRX 관리종목 지정·상장폐지 판정 알고리즘  순서흐름도",
        ha="center", va="center", fontsize=24, weight="bold")
ax.text(26, 58.3, "매 매매거래일 · 종목별 평가  |  시가총액 트랙 · 동전주(주가미달) 트랙 병행",
        ha="center", va="center", fontsize=13, color="#444444")

# 클러스터 배경
cluster(4.5, 38.2, 47.5, 56.8, "공통 전처리 (필터)", "#EAF3FB", "#3D85C6")
cluster(-1.0, -6.0, 19.2, 36.4, "시가총액 트랙", "#F1EAF7", "#7E57C2")
cluster(33.0, -6.0, 53.0, 36.4, "동전주(주가미달) 트랙", "#E7F4F1", "#1B998B")

# ================================================================ 공통 전처리
CX = 26
add_node("start", CX, 55.2, 12, 2.4, "시작\n종목 · 매 매매거래일 평가",
         kind="term", fc=C_START, fs=12, weight="bold")
add_node("uni", CX, 50.3, 10.5, 5.0, "대상 유니버스인가?\n(보통주·외국주·DR)", kind="dec", fc=C_DECIDE)
add_node("excl", 41.5, 50.3, 12, 3.0,
         "제외\n스팩·우선주·리츠·인프라펀드·코넥스\n(종료)", kind="term", fc=C_EXCL, fs=10)

add_node("clean", CX, 44.3, 10.5, 5.0, "정리매매기간인가?", kind="dec", fc=C_DECIDE)
add_node("skip", 41.5, 44.3, 12, 3.0,
         "규칙 미적용\n(세칙 제58조②) · 종료/스킵", kind="term", fc=C_EXCL, fs=10)

add_node("vol", CX, 40.3, 10.5, 5.0, "당일 거래량 = 0\n(매매거래정지)인가?", kind="dec", fc=C_DECIDE)
add_node("halt", 12.5, 40.3, 11, 3.0,
         "그 날은 카운트 제외\nstreak 유지 · 다음 거래일로", kind="rproc", fc=C_EXCL, fs=10)

add_node("hub", CX, 36.9, 12.5, 2.6, "두 트랙 병행 판정\n(시총 · 동전주 독립 평가)",
         kind="rproc", fc=C_START, fs=11, weight="bold")

connect("start", "bottom", "uni", "top")
connect("uni", "right", "excl", "left", "No")
connect("uni", "bottom", "clean", "top", "Yes")
connect("clean", "right", "skip", "left", "Yes")
connect("clean", "bottom", "vol", "top", "No")
connect("vol", "left", "halt", "right", "Yes")
connect("vol", "bottom", "hub", "top", "No")

# ================================================================ 좌: 시총 트랙
LX = 9.5           # 컬럼 중심
LS = 1.9           # 좌측 사이드박스 중심 x
Y = dict(r1=33.0, inc=27.6, r2=23.2, des=18.8, r3=14.4, r4=10.0, r5=5.6, hold=1.0)

add_node("a1", LX, Y["r1"], 9.0, 4.6, "시가총액 ≥ 기준액?", kind="dec", fc=C_DECIDE)
annot(LX, Y["r1"] - 2.55, "기준액 = 부칙 기간별 (공통 규칙 참조)", fs=8.0)
add_node("a1y", LS, Y["r1"], 6.4, 2.6, "미달 streak = 0\n→ 정상", kind="rproc", fc=C_NORMAL, fs=10)

add_node("ainc", LX, Y["inc"], 8.4, 2.2, "미달 streak += 1\n(매매거래일 연속)", kind="proc", fc=C_PROC, fs=10)

add_node("a2", LX, Y["r2"], 9.0, 4.6, "미달 streak = 30?", kind="dec", fc=C_DECIDE)
add_node("a2n", LS, Y["r2"], 6.4, 3.4, "1~19일 미달(관찰)\n20~29일 지정 임박\nD-(30-streak)",
         kind="rproc", fc=C_WATCH, fs=9.5)

add_node("ades", LX, Y["des"], 8.4, 2.4, "★ 지정 (익일 발효)", kind="proc", fc=C_DESIG, fs=12, weight="bold")

add_node("a3", LX, Y["r3"], 9.4, 4.8, "90일 내 '시총 ≥ 기준'\n연속 45일 달성?", kind="dec", fc=C_DECIDE)
add_node("a3y", LS, Y["r3"], 6.6, 3.0, "◎ 관리종목 해제\n→ 정상 복귀 (종료)", kind="term", fc=C_RELEASE, fs=10, weight="bold")

add_node("a4", LX, Y["r4"], 9.4, 4.8, "남은 일수로 연속45\n달성 불가능 확정?", kind="dec", fc=C_DECIDE)
add_node("a4y", LS, Y["r4"], 6.6, 3.0, "■ 조기상폐확정\n(세칙 제51조②) 종료", kind="term", fc=C_DELIST, fs=10, weight="bold")

add_node("a5", LX, Y["r5"], 9.4, 4.6, "90 매매거래일 경과?", kind="dec", fc=C_DECIDE)
add_node("a5y", LS, Y["r5"], 6.6, 2.6, "■ 상폐확정 (종료)", kind="term", fc=C_DELIST, fs=10, weight="bold")

add_node("ahold", LX, Y["hold"], 9.6, 3.4,
         "지정 유지 (회복 진행 중)\n연속≥30 해제임박\n잔여≤15일 상폐위험", kind="rproc", fc=C_HOLD, fs=9.5)

# 좌 트랙 연결
connect("hub", "left", "a1", "top", rad=0.15)
connect("a1", "left", "a1y", "right", "Yes")
connect("a1", "bottom", "ainc", "top", "No", label_t=0.62)
connect("ainc", "bottom", "a2", "top")
connect("a2", "left", "a2n", "right", "No")
connect("a2", "bottom", "ades", "top", "Yes")
connect("ades", "bottom", "a3", "top")
connect("a3", "left", "a3y", "right", "Yes")
connect("a3", "bottom", "a4", "top", "No")
connect("a4", "left", "a4y", "right", "Yes")
connect("a4", "bottom", "a5", "top", "No")
connect("a5", "left", "a5y", "right", "Yes")
connect("a5", "bottom", "ahold", "top", "No")
# 좌 루프백(점선)
connect("a1y", "top", "a1", "left", dashed=True, rad=-0.35, lw=1.4)
connect("a2n", "top", "a1", "bottom", dashed=True, rad=-0.42, lw=1.4,
        label="익일 재평가", lfs=8.5, label_t=0.5, label_dx=-1.4)
connect("ahold", "right", "a3", "bottom", dashed=True, rad=-0.6, lw=1.4,
        label="익일(회복창 내)", lfs=8.5, label_t=0.12, label_dx=1.4, label_dy=-0.5)

# ================================================================ 우: 동전주 트랙
RX = 38.0
RS = 47.6
YB = dict(r1=33.0, inc=27.6, r2=23.2, des=18.8, r3=14.4, r4=10.0, r5=5.6, r6=1.2, hold=-3.4)

add_node("b1", RX, YB["r1"], 9.0, 4.6, "종가 ≥ 1,000원?", kind="dec", fc=C_DECIDE)
annot(RX + 1.6, YB["r1"] - 2.55, "카운트 시작 2026.7.1", fs=8.0)
add_node("b1y", RS, YB["r1"], 6.6, 2.6, "미달 streak = 0\n→ 정상", kind="rproc", fc=C_NORMAL, fs=10)

add_node("binc", RX, YB["inc"], 8.4, 2.2, "미달 streak += 1", kind="proc", fc=C_PROC, fs=10)

add_node("b2", RX, YB["r2"], 9.0, 4.6, "미달 streak = 30?", kind="dec", fc=C_DECIDE)
add_node("b2n", RS, YB["r2"], 6.6, 2.8, "미달 / 지정 임박\n(시총 트랙과 동일)", kind="rproc", fc=C_WATCH, fs=9.5)

add_node("bdes", RX, YB["des"], 8.4, 2.4, "★ 지정 (익일 발효)", kind="proc", fc=C_DESIG, fs=12, weight="bold")

add_node("b3", RX, YB["r3"], 9.6, 4.8, "[가] 종가 ≥ 1,000원\n연속 45일 회복 달성?", kind="dec", fc=C_DECIDE)
add_node("b3y", RS, YB["r3"], 6.6, 3.0, "◎ 관리종목 해제\n→ 정상 (종료)", kind="term", fc=C_RELEASE, fs=10, weight="bold")

add_node("b4", RX, YB["r4"], 10.0, 5.2, "[나] 90일 내 병합·감자\n변경상장 & 과거1년내 이력?", kind="dec", fc=C_DECIDE)
annot(RX, YB["r4"] - 3.2, "변경상장일 2026.7.1 이전이면\n과거이력에서 제외")
add_node("b4y", RS, YB["r4"], 6.6, 2.8, "■ 상폐확정 (나)\n(종료)", kind="term", fc=C_DELIST, fs=10, weight="bold")

add_node("b5", RX, YB["r5"], 10.0, 4.8, "[다] 90일 내 병합·감자\n누적비율(곱) > 10 : 1?", kind="dec", fc=C_DECIDE)
add_node("b5y", RS, YB["r5"], 6.6, 2.8, "■ 상폐확정 (다)\n(종료)", kind="term", fc=C_DELIST, fs=10, weight="bold")

add_node("b6", RX, YB["r6"], 9.6, 4.6, "90 매매거래일 경과\n& [가] 미달성?", kind="dec", fc=C_DECIDE)
add_node("b6y", RS, YB["r6"], 6.6, 2.8, "■ 상폐확정 (가)\n(종료)", kind="term", fc=C_DELIST, fs=10, weight="bold")

add_node("bhold", RX, YB["hold"], 8.6, 2.4, "지정 유지 (루프)", kind="rproc", fc=C_HOLD, fs=10)

# 우 트랙 연결
connect("hub", "right", "b1", "top", rad=-0.15)
connect("b1", "right", "b1y", "left", "Yes")
connect("b1", "bottom", "binc", "top", "No", label_t=0.62, label_dx=-1.6)
connect("binc", "bottom", "b2", "top")
connect("b2", "right", "b2n", "left", "No")
connect("b2", "bottom", "bdes", "top", "Yes")
connect("bdes", "bottom", "b3", "top")
connect("b3", "right", "b3y", "left", "Yes")
connect("b3", "bottom", "b4", "top", "No")
connect("b4", "right", "b4y", "left", "Yes")
connect("b4", "bottom", "b5", "top", "No")
connect("b5", "right", "b5y", "left", "Yes")
connect("b5", "bottom", "b6", "top", "No")
connect("b6", "right", "b6y", "left", "Yes")
connect("b6", "bottom", "bhold", "top", "No")
# 우 루프백(점선)
connect("b1y", "top", "b1", "right", dashed=True, rad=0.35, lw=1.4)
connect("b2n", "top", "b1", "bottom", dashed=True, rad=0.42, lw=1.4,
        label="익일 재평가", lfs=8.5, label_t=0.5, label_dx=1.4)
connect("bhold", "left", "b3", "bottom", dashed=True, rad=0.6, lw=1.4,
        label="익일(회복창 내)", lfs=8.5, label_t=0.12, label_dx=-1.4, label_dy=-0.5)

# ================================================================ 공통 규칙 박스(중앙)
rx0, ry0, rx1, ry1 = 19.6, 8.0, 32.4, 31.0
ax.add_patch(FancyBboxPatch((rx0, ry0), rx1 - rx0, ry1 - ry0,
             boxstyle="round,pad=0,rounding_size=0.4", facecolor="#FBF7EF",
             edgecolor="#B08D57", linewidth=1.6, zorder=2))
ax.text((rx0 + rx1) / 2, ry1 - 1.2, "공통 규칙", ha="center", va="center",
        fontsize=15, weight="bold", color="#7A5C1E", zorder=3)
rules = (
    "· 지정 = 미달 연속 30 매매거래일 → 익일 발효\n"
    "· 해제 = 기준 이상 연속 45 매매거래일 → 익일\n"
    "· 회복창 = 지정 후 90 매매거래일\n"
    "· 모든 일수 = 해당 종목 매매거래일 기준\n"
    "   (매매거래정지일 제외)\n"
    "· 두 트랙 독립 병행 · 30/45/90 규칙 동일\n\n"
    "차이점\n"
    "· 미달 기준: 시총<기준액  vs  종가<1,000원\n"
    "   (시총 기준액=부칙 기간별:\n"
    "    코스닥 150→200→300억,\n"
    "    유가 200→300→500억)\n"
    "· 상폐 사유:\n"
    "   시총 = 회복실패 1가지\n"
    "   동전주 = [가]회복실패·[나]반복 병합감자·\n"
    "                [다]과도 병합감자 3가지\n\n"
    "종착 상태\n"
    "  ◎ 해제(정상복귀) / ■ 상폐확정 /\n"
    "  ■ 조기상폐확정 / 제외"
)
ax.text((rx0 + rx1) / 2, (ry0 + ry1) / 2 - 1.0, rules, ha="center", va="center",
        fontsize=10.2, color="#3B3B3B", zorder=3, linespacing=1.5)

# ================================================================ 색상 범례
legend = [("지정", C_DESIG), ("상폐확정", C_DELIST), ("해제/정상", C_RELEASE),
          ("결정(마름모)", C_DECIDE), ("제외/스킵", C_EXCL)]
lx0, ly = -0.2, 57.0
for i, (lab, col) in enumerate(legend):
    yy = ly - i * 1.5
    ax.add_patch(Rectangle((lx0, yy - 0.55), 1.1, 1.1, facecolor=col,
                 edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(lx0 + 1.5, yy, lab, ha="left", va="center", fontsize=10.5, zorder=3)

# ================================================================ 저장
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(OUT_DIR, "관리종목_알고리즘_순서흐름도.png")
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
sz = os.path.getsize(OUT_PNG)
print(f"saved: {OUT_PNG}")
print(f"size : {sz:,} bytes")
assert sz > 0, "PNG size is 0!"
