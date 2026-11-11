"""README 데이터 흐름도 — docs/img/pipeline.svg 와 pipeline.png 를 만든다.

    python scripts/make_pipeline_diagram.py            # SVG
    .venv/Scripts/python scripts/make_pipeline_diagram.py --png   # SVG + PNG(2배, Playwright)

네 칸: 원천 → 수집·저장(스크립트) → 가공·판정(규칙) → 결과·대조. 숫자는 2026-11-11 실행 기준.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
W, H = 1480, 880
FONT = "'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif"

SRC = {  # 원천 색
    "check": ("#1b8fd6", "#e8f4fc", "CHECK API 게이트웨이 (KOSCOM)"),
    "dart": ("#d9690b", "#fdf1e6", "OpenDART · DART 웹"),
    "kind": ("#1aa6bf", "#e6f7fa", "KIND (한국거래소 상장공시시스템)"),
    "krx": ("#225287", "#e9eef6", "KRX 정보데이터시스템"),
    "pdf": ("#6b7280", "#f1f2f4", "보도자료 PDF (2026.10.30)"),
}
NAVY, TEXT, MUTED, LINE = "#225287", "#1f2937", "#5b6470", "#9aa4ae"

parts: list[str] = []


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=13, weight=400, color=TEXT, anchor="start"):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" '
                 f'text-anchor="{anchor}">{esc(s)}</text>')


def box(x, y, w, h, title, lines, key=None, fill="#ffffff", stroke="#cfd6dc", bar=None, tsize=14):
    if key:
        bar, fill = SRC[key][0], SRC[key][1]
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}"/>')
    if bar:
        parts.append(f'<rect x="{x}" y="{y}" width="5" height="{h}" rx="2" fill="{bar}"/>')
    text(x + 14, y + 22, title, tsize, 700, NAVY)
    for i, ln in enumerate(lines):
        text(x + 14, y + 42 + i * 18, ln, 12, 400, MUTED if ln.startswith("·") else TEXT)
    return (x, y, w, h)


def arrow(x1, y1, x2, y2, color=LINE, dash=False):
    mx = (x1 + x2) / 2
    d = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2 - 6},{y2}"
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" '
                 f'{"stroke-dasharray=\"4 3\"" if dash else ""} marker-end="url(#ah)"/>')


def down(x, y1, y2):
    parts.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 6}" stroke="{NAVY}" stroke-width="1.8" marker-end="url(#ahn)"/>')


def chip(x, y, label, color):
    w = 14 + len(label) * 13
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="11" fill="{color}"/>')
    text(x + w / 2, y + 15, label, 12, 700, "#fff", "middle")
    return w


def band(y, label, sub):
    parts.append(f'<rect x="30" y="{y}" width="{W - 60}" height="34" rx="4" fill="{NAVY}"/>')
    text(46, y + 23, label, 16, 700, "#fff")
    text(W - 46, y + 23, sub, 13, 400, "#dbe6f3", "end")


def big_arrow(y, label):
    cx = W / 2
    parts.append(f'<path d="M{cx - 22},{y} L{cx + 22},{y} L{cx + 22},{y + 14} L{cx + 38},{y + 14} L{cx},{y + 40} '
                 f'L{cx - 38},{y + 14} L{cx - 22},{y + 14} z" fill="#c9d6e3"/>')
    text(cx + 52, y + 26, label, 13, 700, MUTED)


TAG = {"주가": SRC["check"][0], "재무": SRC["dart"][0], "KIND": SRC["kind"][0], "업종": "#7c5cbf", "정답지": SRC["pdf"][0]}


def build() -> str:
    parts.clear()
    text(30, 44, "거래소가 고른 저PBR 151사, 공개 데이터로 똑같이 골라 볼 수 있을까?", 24, 700, NAVY)
    text(30, 72, "재료를 모으고 → 거래소 규칙대로 고르고 → 거래소가 실제로 발표한 결과와 맞춰 봤다", 14, 400, MUTED)

    # ── 1. 어디서 가져왔나
    band(96, "1  어디서 가져왔나", "색 = 데이터 출처 (아래 단계의 꼬리표와 같은 색)")
    cards = [
        ("주가", "주가 · 시가총액", "CHECK API (코스콤)", ["매일의 시가총액 6년치 · 거래일 달력", "2,843종목 · 우선주 포함"]),
        ("재무", "재무제표 (지배주주 자본)", "CHECK API(IFRS) + DART 공시", ["계산: CHECK IFRS, 전 기업 2,715사", "DART: 기준 보고서 결정 · 원문 · 캡처"]),
        ("KIND", "상장 · 공시 현황", "KIND · KRX 정보데이터시스템", ["그날 상장된 회사 · 관리종목 · 우선주", "밸류업 공시 · 실제 공표 명단"]),
        ("업종", "업종 분류 (GICS)", "KRX 지수 사이트", ["반기마다 그날의 GICS 11개 업종", "없는 회사만 CHECK 업종으로 보완"]),
        ("정답지", "정답지", "거래소 보도자료", ["2,431 → 185 → 151", "업종별 표 · 151사 명단"]),
    ]
    cw, gap = 276, 10
    for i, (tag, title, src, lines) in enumerate(cards):
        x = 30 + i * (cw + gap)
        col = TAG[tag]
        parts.append(f'<rect x="{x}" y="142" width="{cw}" height="118" rx="8" fill="#fff" stroke="{col}" stroke-width="1.5"/>')
        parts.append(f'<rect x="{x}" y="142" width="{cw}" height="8" rx="4" fill="{col}"/>')
        text(x + 16, 176, title, 17, 700, NAVY)
        text(x + 16, 197, src, 12, 700, col)
        for j, ln in enumerate(lines):
            text(x + 16, 222 + j * 19, ln, 13, 400, TEXT)

    big_arrow(270, "모아서 계산")

    # ── 2. 어떻게 골랐나
    band(318, "2  어떻게 골랐나 — 거래소 규칙 그대로", "큰 숫자 = 보도자료 · 2020.11 ~ 2026.11 반기마다 13번 반복 계산")
    steps = [
        ("대상 회사", "2,431", ["그날 상장된 회사에서", "관리종목 · 거래정지 빼기"], ["KIND", "주가"]),
        ("PBR 계산", "", ["20일 평균 시가총액", "÷ 지배주주 자본"], ["주가", "재무"]),
        ("업종 안 순위", "", ["같은 업종 하위", "25%(유가)·10%(코스닥)"], ["업종"]),
        ("3년 내내 낮았나", "185", ["최근 반기 6번 모두", "하위권이어야 선정"], []),
        ("개선계획 낸 곳 빼기", "−34", ["10.22까지 PBR 개선계획", "공시하면 제외*"], ["KIND"]),
        ("최종 공표", "151", ["유가 96 · 코스닥 55", "MTS·HTS에 '저PBR' 표시"], []),
    ]
    sw, sg, sy, sh = 220, 20, 366, 176
    for i, (title, num, lines, tags) in enumerate(steps):
        x = 30 + i * (sw + sg)
        last = i == len(steps) - 1
        fill = "#e6f6f9" if last else "#f7fafc"
        parts.append(f'<rect x="{x}" y="{sy}" width="{sw}" height="{sh}" rx="8" fill="{fill}" stroke="#cfd6dc"/>')
        parts.append(f'<circle cx="{x + 24}" cy="{sy + 26}" r="14" fill="{NAVY}"/>')
        text(x + 24, sy + 31, str(i + 1), 14, 700, "#fff", "middle")
        text(x + 46, sy + 31, title, 15, 700, NAVY)
        if num:
            text(x + sw - 14, sy + 76, num, 30, 700, SRC["dart"][0] if num.startswith("−") else NAVY, "end")
        for j, ln in enumerate(lines):
            text(x + 14, sy + 108 + j * 20, ln, 13, 400, TEXT)
        cx = x + 14
        for t in tags:
            cx += chip(cx, sy + sh - 32, t, TAG[t]) + 6
        if not last:
            ax = x + sw + 2
            parts.append(f'<path d="M{ax},{sy + sh / 2 - 9} L{ax + 15},{sy + sh / 2} L{ax},{sy + sh / 2 + 9} z" fill="{NAVY}"/>')
    text(30, sy + sh + 24, "* 단, 6년(13번 중 12번) 내내 하위권이었던 회사는 계획을 내도 공표된다.  "
         "  PBR이 1보다 작을수록 회사 가치가 장부상 자본보다 낮게 평가된다는 뜻이다.", 12, 400, MUTED)

    big_arrow(578, "맞는지 확인")

    # ── 3. 맞게 골랐나
    band(626, "3  맞게 골랐나 — 거래소가 실제로 발표한 결과와 비교", "")
    checks = [
        ("PBR 숫자", "151 / 151 일치", ["공표 151사 PBR, 소수 둘째 자리까지 같다",
                                      "CHECK 값 · DART 원문 값 둘 다 일치",
                                      "→ 분모는 '자본총계'가 아니라 지배주주 자본"], SRC["kind"][0]),
        ("개선계획 낸 회사", "62사 · 15사 일치", ["KIND 공시 제목으로 62사를 찾았고", "그중 그래도 공표된 15사(장기 저PBR)",
                                          "까지 보도자료 숫자와 같다"], SRC["kind"][0]),
        ("최종 명단", "151 / 151 재현", ["거래소 공표 151사를 모두 골라냈다",
                                     "대상 779·1,652 · 업종 기준선 22/22 일치",
                                     "재현은 경계선 7사를 더 골랐다"], SRC["kind"][0]),
        ("결과물", "웹페이지", ["단계별 화면 · 회사 추적 (전 기업)", "원문 링크 · 캡처 362장 (공표·계획 198사)",
                             "GitHub Pages로 공개"], NAVY),
    ]
    kw, kg = 345, 13
    for i, (t, big, lines, col) in enumerate(checks):
        x = 30 + i * (kw + kg)
        parts.append(f'<rect x="{x}" y="672" width="{kw}" height="150" rx="8" fill="#fff" stroke="#cfd6dc"/>')
        parts.append(f'<rect x="{x}" y="672" width="6" height="150" rx="3" fill="{col}"/>')
        text(x + 20, 700, t, 14, 700, MUTED)
        text(x + 20, 734, big, 24, 700, col)
        for j, ln in enumerate(lines):
            text(x + 20, 762 + j * 19, ln, 13, 400, TEXT)

    text(30, 856, "숫자는 2026-11-11 실행 기준. 코스콤 CHECK 원자료는 재배포하지 않아 레포에 없고, 웹페이지는 가공한 값만 쓴다.", 12, 400, MUTED)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'font-family="{FONT}"><rect width="{W}" height="{H}" fill="#ffffff"/>{"".join(parts)}</svg>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build()
    (OUT / "pipeline.svg").write_text(svg, encoding="utf-8")
    print("docs/img/pipeline.svg")
    if args.png:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            pg.set_content(f'<html><body style="margin:0">{svg}</body></html>')
            pg.screenshot(path=str(OUT / "pipeline.png"), clip={"x": 0, "y": 0, "width": W, "height": H})
            b.close()
        print("docs/img/pipeline.png")


if __name__ == "__main__":
    main()
