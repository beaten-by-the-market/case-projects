"""make_flow_svg — README 데이터 흐름 도식 docs/img/data-flow.svg

위에서 아래로: ① 출처·데이터·목적(용도별 대분류 A~D) → ② 업무 → ③ LLM → ④ 검증·합치기 → ⑤ 결과.
라이브러리 없이 SVG 를 손으로 짠다. 태그 건수·인용 대조는 data/final/charter_dividend_record_date{,_kosdaq,_absent}.json 에서 세고,
신고 대조 건수는 site/dividend.js, KIND 결과 판별 수는 data/interim/s09e_llm*.json 에서, 나머지 숫자는 아래 상수(README · docs/03 · docs/04 와 같은 값)다. 상자 안 글은 글자 폭 어림으로 줄바꿈하고, 넘치면 경고를 찍는다.

    python -X utf8 scripts/make_flow_svg.py
"""
from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / "data" / "final"
OUT = ROOT / "docs" / "img" / "data-flow.svg"

FONT = "'Pretendard','Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif"
MONO = "'Cascadia Mono',Consolas,'SFMono-Regular',Menlo,monospace"

INK, BODY, MUTED, LINE, PAPER = "#101828", "#344054", "#667085", "#d0d5dd", "#ffffff"
CAT = {
    "A": dict(name="A · 기준 설정", sub="누구의 · 어느 시점 정관을, 무슨 잣대로", c="#3b4f7a", tint="#f2f5fa", line="#cbd5e6"),
    "B": dict(name="B · 판별 원문", sub="LLM 이 읽을 정관 글을 회사마다 1부", c="#2c6e49", tint="#f0f7f2", line="#c3dfcc"),
    "C": dict(name="C · 변경 추적", sub="첨부 정관 뒤에 바뀐 조항", c="#8a5800", tint="#fbf6ea", line="#e9d7ae"),
    "D": dict(name="D · 확인 · 대조", sub="판별을 맞춰 보는 자료 (LLM 안 거침)", c="#9a2d5c", tint="#fbf1f5", line="#ecc9d8"),
}
LLM_C, LLM_TINT, LLM_LINE, LLM_BOX = "#6941c6", "#f6f2fe", "#dacff7", "#ffffff"
GRAY_TINT = "#f7f8fa"
TAGC = {"정관no": "#2a78d6", "정관yes": "#eb6834", "정관yesorno": "#1baf7a"}  # site 와 같은 색 (docs/04 '태그 색')
LBL = {"정관no": "N", "정관yes": "Y", "정관yesorno": "YorN"}  # 웹페이지 표기 (결과 파일 값은 그대로)

W = 1200
RAIL_X, RAIL_W = 24, 34
CX0, CX1 = 72, 1176
GAP = 20
COLW = (CX1 - CX0 - 3 * GAP) / 4
COLX = {k: CX0 + i * (COLW + GAP) for i, k in enumerate("ABCD")}
PAD = 10
BOXW = COLW - 2 * PAD
LH = 17
WARN: list[str] = []


# ── 글자 폭 어림 · 줄바꿈 ─────────────────────────────────────────────
def _cw(ch: str, mono: bool) -> float:
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or 0x2460 <= o <= 0x24FF:
        return 1.0
    if mono:
        return 0.6
    if ch == "·":
        return 0.42
    if ch == " ":
        return 0.30
    if ch in "→▸↓■~":
        return 0.9
    if ch.isdigit():
        return 0.57
    if ch.isupper():
        return 0.66
    if ch.islower():
        return 0.54
    if ch in ".,:;'\"`!|":
        return 0.30
    if ch in "()[]{}":
        return 0.36
    if ch in "-–/_":
        return 0.45
    return 0.62


def tw(s: str, size: float, bold: bool = False, mono: bool = False) -> float:
    return sum(_cw(c, mono) for c in s) * size * (1.06 if bold else 1.0)


def wrap(s: str, width: float, size: float, bold: bool = False, mono: bool = False) -> list[str]:
    lines, cur = [], ""
    for wd in s.split(" "):
        cand = wd if not cur else f"{cur} {wd}"
        if not cur or tw(cand, size, bold, mono) <= width:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    for ln in lines:
        if tw(ln, size, bold, mono) > width + 0.5:
            WARN.append(f"넘침 {tw(ln, size, bold, mono):.0f}>{width:.0f}: {ln}")
    return lines


# ── SVG 조각 ──────────────────────────────────────────────────────────
P: list[str] = []


def add(s: str) -> None:
    P.append(s)


def rect(x, y, w, h, fill="none", stroke=None, rx=6, sw=1.0, dash=None) -> None:
    a = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{sw}"'
    if dash:
        a += f' stroke-dasharray="{dash}"'
    add(a + "/>")


def text(x, y, s, size=12.5, weight=400, fill=BODY, anchor="start", mono=False, halo=None, rotate=None) -> None:
    a = f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}"'
    if weight != 400:
        a += f' font-weight="{weight}"'
    a += f' fill="{fill}"'
    if anchor != "start":
        a += f' text-anchor="{anchor}"'
    if mono:
        a += ' class="m"'
    if halo:
        a += f' stroke="{halo}" stroke-width="5" stroke-linejoin="round" paint-order="stroke"'
    if rotate is not None:
        a += f' transform="rotate({rotate} {x:.1f} {y:.1f})"'
    add(a + f">{escape(s, quote=False)}</text>")


MARK = {"g": "#98a2b3", "v": LLM_C, "k": INK}


def arrow(x1, y1, x2, y2, kind="g", dash=None, sw=1.5) -> None:
    a = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{MARK[kind]}" '
         f'stroke-width="{sw}" marker-end="url(#ah-{kind})"')
    if dash:
        a += f' stroke-dasharray="{dash}"'
    add(a + "/>")


def label(x, y, s, fill=MUTED, halo=PAPER, anchor="start", size=11.5, weight=500) -> None:
    text(x, y, s, size=size, weight=weight, fill=fill, anchor=anchor, halo=halo)


# ── 상자 ──────────────────────────────────────────────────────────────
def data_box(item: dict, cat: dict, x: float, w: float):
    """출처 · 데이터명 · 본문 · [기준/용도/확인/대조] 목적. (높이, 그리기) 를 돌려준다."""
    inner = w - 24
    body = [ln for b in item["body"] for ln in wrap(b, inner, 12.5)]
    chip_w = tw(item["tag"], 10.5, True) + 14
    pur = wrap(item["purpose"], inner - chip_w - 6, 12.5, bold=True)
    wrap(item["title"], inner, 13.5, bold=True)
    wrap(item["src"], inner - 12, 11, bold=True)
    y_body0 = 58
    y_p0 = y_body0 + len(body) * LH + 6
    h = y_p0 + (len(pur) - 1) * LH + 12

    def draw(y: float, hh: float) -> None:
        rect(x, y, w, hh, PAPER, cat["line"], rx=6)
        rect(x + 12, y + 11, 7, 7, cat["c"], rx=1.5)
        text(x + 24, y + 19, item["src"], 11, 600, cat["c"])
        text(x + 12, y + 38, item["title"], 13.5, 700, INK)
        for i, ln in enumerate(body):
            text(x + 12, y + y_body0 + i * LH, ln, 12.5, 400, BODY)
        cy = y + y_p0
        rect(x + 12, cy - 12.5, chip_w, 17, cat["c"], rx=8.5)
        text(x + 12 + chip_w / 2, cy, item["tag"], 10.5, 700, PAPER, anchor="middle")
        for j, ln in enumerate(pur):
            text(x + 12 + chip_w + 6, cy + j * LH, ln, 12.5, 700, cat["c"])

    return h, draw


def task_box(tasks: list[tuple[str, str]], cat: dict, x: float, w: float):
    idw = max(tw(i, 11.5, True, mono=True) for i, _ in tasks) + 10
    inner = w - 26 - idw
    rows = [(i, wrap(t, inner, 12.5)) for i, t in tasks]
    n = sum(len(l) for _, l in rows)
    h = 24 + (n - 1) * LH + (len(rows) - 1) * 5 + 13

    def draw(y: float, hh: float) -> None:
        rect(x, y, w, hh, PAPER, cat["line"], rx=6)
        rect(x, y + 8, 3.5, hh - 16, cat["c"], rx=1.5)
        yy = y + 24
        for i, lines in rows:
            text(x + 14, yy, i, 11.5, 700, cat["c"], mono=True)
            for k, ln in enumerate(lines):
                text(x + 14 + idw, yy + k * LH, ln, 12.5, 400, BODY)
            yy += len(lines) * LH + 5

    return h, draw


def note_box(title: str, lines: list[str], x: float, w: float, *, llm: bool, tsize=13.5, title_fill=None, mono_title=False):
    """LLM 상자(보라 테) 또는 LLM 아닌 준비 상자(회색 테)."""
    inner = w - 24
    tl = wrap(title, inner, tsize, bold=True)
    body = [ln for s in lines for ln in wrap(s, inner, 12.5)]
    h = 22 + (len(tl) - 1) * 18 + 8 + len(body) * LH + 6

    def draw(y: float, hh: float) -> None:
        rect(x, y, w, hh, LLM_BOX if llm else PAPER, LLM_C if llm else "#b8c0cc", rx=7, sw=1.6 if llm else 1.0,
             dash=None if llm else "4 3")
        yy = y + 22
        for ln in tl:
            text(x + 12, yy, ln, tsize, 700, title_fill or (LLM_C if llm else INK))
            yy += 18
        yy += 8 - 18 + LH
        for ln in body:
            text(x + 12, yy, ln, 12.5, 400, BODY)
            yy += LH

    return h, draw


# ── 내용 ──────────────────────────────────────────────────────────────
DATA = {
    "A": [
        dict(src="OpenDART API · list.json", title="사업보고서 최종본 목록",
             body=["A001 · 최종본만 · 1년 동안 접수분", "회사마다 최근 1건 → 3,349사"],
             tag="기준", purpose="대상 회사 · 판별 시점 (이 보고서의 첨부 정관)"),
        dict(src="KIND · 상장종목현황", title="기준일 현재 상장 목록",
             body=["코스피 829사 · 코스닥 1,833사"],
             tag="기준", purpose="소속시장 · 빠진 상장사 53사"),
        dict(src="금융위 · 상장협 · 원문 10건", title="배당절차 개선 규제 원문",
             body=["2023.1 배당절차 개선방안", "2023.2 표준정관 이익배당 조항 개정"],
             tag="기준", purpose="태그 3종의 정의 → 판별 지침"),
    ],
    "B": [
        dict(src="DART 공시 화면 · 첨부 목록", title="사업보고서 첨부 정관",
             body=["코스피 825 · 코스닥 1,784 = 2,609사", "텍스트 2,019 · 스캔 이미지 454", "PDF 124 · 혼합 12"],
             tag="용도", purpose="판별할 정관 원문"),
        dict(src="DART · KIND · 회사 홈페이지", title="사업보고서 없는 52사의 정관",
             body=["증권신고서 47 · 분할계획서 2", "KIND 기타신고사항 3"],
             tag="용도", purpose="빠진 상장사도 같은 판별"),
        dict(src="DART · OpenDART", title="읽을 수 없는 정관의 대체 자료",
             body=["잠긴 PDF · 끊긴 스캔 · 미서비스 7사", "전년도 정관 · 사업보고서 본문 표"],
             tag="용도", purpose="확인필요 7사를 0사로"),
    ],
    "C": [
        dict(src="OpenDART API · E006 document.xml", title="제출 뒤 주주총회소집공고",
             body=["원본 최초 접수일 ~ 기준일 접수분", "코스피 247건 · 코스닥 720건",
                   "그중 '정관의 변경' 절 146 · 464건"],
             tag="용도", purpose="첨부 정관 뒤에 바뀐 조항 찾기"),
        dict(src="OpenDART API · E006 document.xml", title="사업보고서보다 먼저 제출된 소집공고",
             body=["원본 접수일 전 90일 안 접수분", "코스피 769건 · 코스닥 1,712건",
                   "정기주총 공고(주총 2주 전)가 사업보고서(1주 전)보다 먼저 나온다"],
             tag="용도", purpose="주총 전 판인 첨부 정관에 그 주총 개정 반영"),
    ],
    "D": [
        dict(src="KIND · 주주총회결과", title="안건 세부내역 가결여부",
             body=["기준일 조항을 바꾸는 안건마다"],
             tag="확인", purpose="안건이 실제로 통과됐나"),
        dict(src="공시부 제출 · 상장공시시스템 엑셀 2개", title="회사가 낸 배당기준일 조건",
             body=["Y 특정일 · N 이사회 결의", "코스피 829 · 코스닥 1,840종목", "부정확한 경우가 많아 시장운영팀이", "정관과 눈으로 다시 검증해 왔다"],
             tag="대조", purpose="신고가 정관과 맞나"),
        dict(src="상장협·코스닥협 · KIND 상장법인목록", title="참고 자료",
             body=["2026.3 말 정관 정비 55.3% 집계", "지금 결산월 (제출 뒤 바뀐 3사)"],
             tag="용도", purpose="건수 대조 · 결산월 표시"),
    ],
}

TASKS = {
    "A": [("s01", "회사별 1건 · 결산월"), ("s02", "소속시장 붙이기"),
          ("s02b·c", "빠진 상장사와 이유"), ("스킬", "규제 원문 → tagging-guide.md")],
    "B": [("s03", "첨부 목록에서 정관 찾기"), ("s04", "정관 원문 · 쪽 그림 받기"),
          ("s04c", "PDF 글자층 뽑기"), ("s04e", "증권신고서 등에서 정관"), ("s09f", "전년도 정관 · 대체 자료")],
    "C": [("s05", "소집공고 목록 · 회사별 셈 기간"), ("s06", "XML → '정관의 변경' 절 txt"),
          ("s09i", "앞서 제출된 공고도 같은 절 뽑기")],
    "D": [("s09e", "KIND 결과 본문 → 안건별 가결"), ("s02e", "제출 엑셀 2개 읽기 (이름·연락처 칸 빼고)"),
          ("s10", "정관 태그와 신고 대조"), ("s02d", "KIND 지금 결산월")],
}

# 건수 상수 (README · docs/04)
SCAN_PAGES, SCAN_DOCS, SCAN_USD = "9,242", "551", "$149"      # 코스피 3,225쪽/181 + 코스닥 6,017쪽/370, $51 + $98
CHANGED = {"s09i": 148, "s09d": 25, "s09f": 7}                 # tag → tag_current 가 바뀐 회사 (코스피+코스닥)
AGM_PASS = "212건 중 209건 가결"                                    # 기준일을 바꾸는 안건의 KIND 가결 (코스피 79/79 · 코스닥 130/133, docs/04)


def kind_llm_count() -> int:
    """s09e 서브에이전트가 판별한 KIND 주총 결과 수 — data/interim/s09e_llm{,_kosdaq}.json 항목 수."""
    n = 0
    for sfx in ("", "_kosdaq"):
        f = ROOT / "data" / "interim" / f"s09e_llm{sfx}.json"
        if f.exists():
            n += len(json.loads(f.read_text("utf-8")))
    return n


def filed_counts() -> dict:
    """웹페이지 데이터(site/dividend.js) stats_by_market 의 상장공시시스템 신고 대조(filed_cmp) — 시장별."""
    txt = (ROOT / "site" / "dividend.js").read_text("utf-8")
    sbm = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])["stats_by_market"]
    return {m: Counter(sbm[m].get("filed_cmp") or {}) for m in ("코스피", "코스닥")}


def tag_counts():
    by_mkt = {"코스피": Counter(), "코스닥": Counter()}
    first, n, qok = Counter(), 0, 0
    for sfx in ("", "_kosdaq", "_absent"):
        rows = json.loads((FINAL / f"charter_dividend_record_date{sfx}.json").read_text("utf-8"))
        for r in rows:
            by_mkt[r["market"]][r["tag_current"]] += 1
            first[r["tag"]] += 1
            n += 1
            qok += bool(r.get("quote_ok"))
    return by_mkt, first, n, qok


# ── 그리기 ────────────────────────────────────────────────────────────
def build() -> tuple[str, int]:
    by_mkt, first, n_all, qok = tag_counts()
    filed = filed_counts()
    kind_llm = kind_llm_count()
    now = by_mkt["코스피"] + by_mkt["코스닥"]

    # 제목 · 기준 띠
    text(24, 44, "kospi-charter 데이터 흐름", 24, 700, INK)
    text(24, 68, "정관의 결산배당 기준일 태그가 나오기까지 — 어디서 받아, 무엇을 기준으로 정하고, LLM 을 어디에 넣어, 무엇이 나오나",
         13, 400, MUTED)
    rect(24, 84, CX1 - 24, 32, "#f2f4f7", LINE, rx=6)
    xx = 38
    for k, v in [("기준일", "2026-11-16"), ("조회기간", "2025-11-16 ~ 2026-11-16 (접수일)"),
                 ("소속시장", "기준일 현재 KIND 목록"), ("판별 정관", "사업보고서 첨부본 → 그 뒤 주총 반영"),
                 ("대상", f"상장사 {n_all:,}사")]:
        text(xx, 105, k, 12.5, 700, INK)
        xx += tw(k, 12.5, True) + 7
        text(xx, 105, v, 12.5, 400, BODY)
        xx += tw(v, 12.5) + 24
    if xx > CX1:
        WARN.append(f"기준 띠 넘침 {xx:.0f}")

    # ① 데이터 · ② 업무 (대분류 칸)
    S1 = 136
    HEAD = 52
    top1 = S1 + HEAD + 10
    boxes = {k: [data_box(it, CAT[k], COLX[k] + PAD, BOXW) for it in DATA[k]] for k in "ABCD"}
    H1 = max(sum(h for h, _ in v) + 10 * (len(v) - 1) for v in boxes.values())
    bot1 = top1 + H1
    top2 = bot1 + 28
    tasks = {k: task_box(TASKS[k], CAT[k], COLX[k] + PAD, BOXW) for k in "ABCD"}
    H2 = max(h for h, _ in tasks.values())
    bot2 = top2 + H2
    panel_bot = bot2 + 10

    for k in "ABCD":
        c, x = CAT[k], COLX[k]
        rect(x, S1, COLW, panel_bot - S1, c["tint"], c["line"], rx=10)
        rect(x, S1, COLW, HEAD, c["c"], rx=10)
        rect(x, S1 + HEAD - 12, COLW, 12, c["c"], rx=0)
        text(x + 14, S1 + 23, c["name"], 15, 700, PAPER)
        text(x + 14, S1 + 42, c["sub"], 12, 500, "#ffffffdd")
        wrap(c["sub"], COLW - 28, 12)
        v = boxes[k]
        extra = (H1 - sum(h for h, _ in v) - 10 * (len(v) - 1)) / len(v)
        y = top1
        for h, draw in v:
            draw(y, h + extra)
            y += h + extra + 10
        arrow(x + COLW / 2, bot1 + 2, x + COLW / 2, top2 - 3, "g")
        tasks[k][1](top2, H2)

    # A → B : 대상
    ya = top2 + 22
    arrow(COLX["A"] + PAD + BOXW + 2, ya, COLX["B"] + PAD - 3, ya, "g")
    label((COLX["A"] + PAD + BOXW + COLX["B"] + PAD) / 2, ya - 6, "대상", anchor="middle", size=11, halo=None)

    # ③ LLM 띠
    S3 = panel_bot + 40
    xa, xb, xc, xd = (COLX[k] + PAD for k in "ABCD")
    cxa, cxb, cxc, cxd = (COLX[k] + COLW / 2 for k in "ABCD")
    t3 = S3 + 42

    hA, dA = note_box("시스템 프롬프트 (LLM 아님)",
                      ["tagging-guide.md 판별 구간 그대로", "해시 f3cf17… 고정 (모든 판별 같음)",
                       "pilot 21사 손 판단과 21/21"], xa, BOXW, llm=False)
    L1W = BOXW - 34
    hL1, dL1 = note_box("LLM① 스캔 쪽 전사",
                        ["Opus 5.5 가 쪽 그림을 직접 읽음", f"{SCAN_PAGES}쪽 · {SCAN_DOCS}개 정관 · 실패 0",
                         f"Batches API 약 {SCAN_USD}", "52사는 서브에이전트"], xb, L1W, llm=True)
    hEx, dEx = note_box("키워드 발췌 · s09a (LLM 아님)",
                        ["정관 전체 대신 기준일 조항 앞뒤만", "전문의 33~38% 분량", "코스피 결정 문구 2,699곳 전부 포함"],
                        xb, BOXW, llm=False)
    hC, dC = note_box("안건 고르기 (LLM 아님)",
                      ["기준일 문구가 든 '정관의 변경' 절만", "+ 그 회사 첨부 정관 발췌",
                       "제출 뒤 공고 27 · 95사", "앞서 제출된 공고 171 · 398사"], xc, BOXW, llm=False)
    gapB = 34
    H3a = max(hA, hL1 + gapB + hEx, hC)
    t3b = t3 + H3a + 34

    l2x, l2w = xa, (xb + BOXW) - xa
    L2_ROWS = [("입력", "키워드 발췌 + 시스템 프롬프트, 회사마다 1건"),
               ("출력", "JSON 스키마 — 태그 · 근거 조·항 · 인용 1~3 · 중간·분기배당 · 확신도"),
               ("코스피", "825사 — Claude Opus 5.5 · Batches API · 약 $16"),
               ("코스닥 · 52사", "1,836사 — Claude Code 서브에이전트 약 140개 · API 0원")]
    lab_w = max(tw(a, 12.5, True) for a, _ in L2_ROWS) + 16
    l2_lines = [(a, wrap(b, l2w - 24 - lab_w, 12.5)) for a, b in L2_ROWS]
    hL2 = 22 + 10 + sum(len(l) for _, l in l2_lines) * LH + (len(l2_lines) - 1) * 4 + 4
    hL3, dL3 = note_box("LLM③ 주총 안건·결과 판별",
                        ["“원안대로 가결되면 태그는?” (s09d · s09i)", "바꾸는 안건: 제출 뒤 공고 10 · 23사", "앞서 제출된 공고 69 · 109사",
                         f"KIND 결과 {kind_llm}건 가결 판별 (s09e)", "서브에이전트 (코스피 제출 뒤만 API)"], xc, BOXW, llm=True)
    H3b = max(hL2, hL3)
    S3b = t3b + H3b + 18
    rect(CX0, S3, CX1 - CX0, S3b - S3, LLM_TINT, LLM_LINE, rx=12)
    text(CX0 + 14, S3 + 26, "LLM 은 세 곳에만 — ① 스캔 쪽 전사  ② 결산배당 기준일 판별  ③ 주총 안건·결과 판별", 13.5, 700, LLM_C)

    dA(t3, hA)
    dL1(t3, hL1)
    dEx(t3 + hL1 + gapB, hEx)
    dC(t3, hC)
    # ② → ③ 화살표
    arrow(cxa, bot2 + 2, cxa, t3 - 3, "g")
    label(cxa + 7, S3 - 12, "지침", halo=PAPER)
    lx1 = xb + L1W / 2
    arrow(lx1, bot2 + 2, lx1, t3 - 3, "v")
    label(lx1 + 7, S3 - 12, "스캔 쪽 그림", fill=LLM_C)
    bx_lane = xb + L1W + (BOXW - L1W) / 2
    arrow(bx_lane, bot2 + 2, bx_lane, t3 + hL1 + gapB - 3, "g")
    label(bx_lane + 7, S3 - 12, "텍스트 · PDF 글자층")
    arrow(lx1, t3 + hL1 + 2, lx1, t3 + hL1 + gapB - 3, "v")
    label(lx1 + 7, t3 + hL1 + gapB / 2 + 4, "전사 글", fill=LLM_C, halo=LLM_TINT)
    arrow(cxc, bot2 + 2, cxc, t3 - 3, "g")
    label(cxc + 7, S3 - 12, "'정관의 변경' 절")
    # ③a → ③b
    arrow(cxa, t3 + hA + 2, cxa, t3b - 3, "v")
    label(cxa + 7, t3b - 12, "시스템 프롬프트", fill=LLM_C, halo=LLM_TINT)
    arrow(cxb, t3 + hL1 + gapB + hEx + 2, cxb, t3b - 3, "v")
    label(cxb + 7, t3b - 12, "발췌", fill=LLM_C, halo=LLM_TINT)
    arrow(cxc, t3 + hC + 2, cxc, t3b - 3, "v")
    label(cxc + 7, t3b - 12, "안건 + 정관 발췌", fill=LLM_C, halo=LLM_TINT)

    # LLM②
    rect(l2x, t3b, l2w, H3b, LLM_BOX, LLM_C, rx=7, sw=1.6)
    text(l2x + 12, t3b + 22, "LLM② 결산배당 기준일 판별 · s09b", 13.5, 700, LLM_C)
    yy = t3b + 22 + 10 + LH - 2
    for a, lines in l2_lines:
        text(l2x + 12, yy, a, 12.5, 700, INK)
        for k, ln in enumerate(lines):
            text(l2x + 12 + lab_w, yy + k * LH, ln, 12.5, 400, BODY)
        yy += len(lines) * LH + 4
    dL3(t3b, H3b)

    # D 레인: LLM 을 거치지 않음
    S4 = S3b + 40
    arrow(cxd, bot2 + 2, cxd, S4 + 40 - 3, "g", dash="5 4")
    mid = (S3 + S3b) / 2
    pill = "LLM 을 거치지 않고 검증으로"
    pw = tw(pill, 12, True) + 20
    rect(cxd - pw / 2, mid - 13, pw, 24, PAPER, CAT["D"]["line"], rx=12)
    text(cxd, mid + 4, pill, 12, 700, CAT["D"]["c"], anchor="middle")
    label(cxd + 7, S4 - 12, "가결여부 · 집계")
    text(CX1 - 14, S3 + 26, "2026-11-17 부터 API 대신 서브에이전트", 12, 500, MUTED,
         anchor="end", halo=LLM_TINT)

    # ④ 검증 · 합치기
    arrow((l2x + l2w / 2), t3b + H3b + 2, (l2x + l2w / 2), S4 - 3, "v")
    label(l2x + l2w / 2 + 7, S4 - 12, f"태그 JSON {n_all:,}건", fill=LLM_C)
    arrow(cxc, t3b + H3b + 2, cxc, S4 - 3, "v")
    label(cxc + 7, S4 - 12, "가결되면 태그", fill=LLM_C)

    CHECKS = [
        ("A", "인용 대조", ["인용이 원문에 글자 그대로 있나", f"{qok:,} / {n_all:,} 일치"]),
        ("B", "독립 규칙 판별", ["정규식으로 따로 판별해 맞대 봄", "코스피 불일치 10건 = 규칙 쪽 오류"]),
        ("C", "재검토 · 서식 판정", ["확신도 낮음 · 규칙 불일치 · 갈린 서식", "Claude 세션이 원문과 다시 대조", "코스피 41건 → 3건 고침", "코스닥 서식 259건 → 39건 고침"]),
        ("D", "가결 확인 · 신고 대조", ["KIND 에서 가결된 안건만 반영", f"안건 {AGM_PASS}",
                                   "신고 대조 — 일치 · 불일치 · 미입력",
                                   *[f"{m} {filed[m]['일치']:,} · {filed[m]['불일치']:,} · {filed[m]['미입력']:,}" for m in ("코스피", "코스닥")]]),
    ]
    t4 = S4 + 40
    chk = {k: note_box(t, ls, COLX[k] + PAD, BOXW, llm=False, tsize=13.5) for k, t, ls in CHECKS}
    H4a = max(h for h, _ in chk.values())
    t4b = t4 + H4a + 36
    NODES = [
        ("tag · 첨부 정관", [f"N {first['정관no']:,} · Y {first['정관yes']:,}",
                          f"YorN {first['정관yesorno']:,} · 확인필요 {first['확인필요']:,}"], False),
        ("+ 앞서 제출된 공고 안건", [f"s09i → {CHANGED['s09i']}사 바뀜 (가결만)", "주총 전 판 첨부 정관 보정"], False),
        ("+ 제출 뒤 공고 안건", [f"s09d → {CHANGED['s09d']}사 바뀜 (가결만)", "사업보고서 뒤 제출된 공고"], False),
        ("+ 확인필요 대체 자료", [f"s09f → {CHANGED['s09f']}사", "전년도 정관 · 본문 표"], False),
        ("tag_current · 지금", [f"N {now['정관no']:,} · Y {now['정관yes']:,}",
                              f"YorN {now['정관yesorno']:,} · 확인필요 {now['확인필요']:,}"], True),
    ]
    nx0, nx1, ngap = CX0 + 14, CX1 - 14, 26
    nw = (nx1 - nx0 - ngap * (len(NODES) - 1)) / len(NODES)
    nh = 22 + 8 + 2 * LH + 6
    for t, ls, _ in NODES:
        wrap(t, nw - 24, 13.5, bold=True)
        for s in ls:
            wrap(s, nw - 24, 12.5)
    S4b = t4b + nh + 16
    rect(CX0, S4, CX1 - CX0, S4b - S4, GRAY_TINT, LINE, rx=12)
    text(CX0 + 14, S4 + 26, "LLM 결과를 그대로 쓰지 않는다", 13.5, 700, INK)
    text(CX0 + 14 + tw("LLM 결과를 그대로 쓰지 않는다", 13.5, True) + 10, S4 + 26,
         "네 가지로 검사하고, 시점 순으로 합친다 (s09c)", 12.5, 400, MUTED)
    for k, (h, draw) in chk.items():
        draw(t4, H4a)
    gx = (COLX["B"] + COLW + COLX["C"]) / 2
    arrow(gx, t4 + H4a + 2, gx, t4b - 3, "g")
    label(gx + 7, t4b - 13, "검사를 통과한 태그", halo=GRAY_TINT)
    for i, (t, ls, hi) in enumerate(NODES):
        x = nx0 + i * (nw + ngap)
        rect(x, t4b, nw, nh, INK if hi else PAPER, INK if hi else "#98a2b3", rx=7, sw=1.2)
        text(x + 12, t4b + 22, t, 13.5, 700, PAPER if hi else INK)
        for k, s in enumerate(ls):
            text(x + 12, t4b + 22 + 8 + LH + k * LH - 2, s, 12.5, 400, "#e4e7ec" if hi else BODY)
        if i:
            arrow(x - ngap + 3, t4b + nh / 2, x - 3, t4b + nh / 2, "k", sw=1.6)

    # ⑤ 결과
    S5 = S4b + 40
    rw = (CX1 - CX0 - 2 * 20) / 3
    rx_ = [CX0 + i * (rw + 20) for i in range(3)]
    R1 = [("annual_reports", "사업보고서 최종본 3,349사 · 시장 · 사업연도"),
          ("kospi_ · kosdaq_ · absent_charter", "정관 원문 위치 · 원문 종류 · 소집공고 수"),
          ("agm_notices", "소집공고와 '정관의 변경' 절 txt 위치"),
          ("charter_dividend_record_date", "태그 · 근거 조·항 · 인용 · 근거 문서 URL"),
          ("data/charter* · data/agm*", "정관 · 소집공고 원문, 회사·문서별 폴더")]
    R3 = [("근거문서 표", "회사 1행 — 정관 원문 · 소집공고 '정관의 변경' 미리보기"),
          ("배당기준일", f"{n_all:,}행 — 태그 · 신고 대조(불일치 빨강) · 근거 문구 · 근거 그림"),
          ("배당기준일 취합", "시장별 태그 구성 · 신고 × 정관 교차표 · 분기·중간배당 교차"),
          ("배당 특이사항", "대체 자료 · 오기재 · 주총으로 바뀐 회사 등 286건")]
    HEADR = 32

    def list_h(items, mono):
        n = 0
        for a, b in items:
            n += len(wrap(a, rw - 24, 12 if mono else 12.5, bold=True, mono=mono)) + len(wrap(b, rw - 24, 12))
        return HEADR + 18 + n * 16 + (len(items) - 1) * 6 + 6

    h_r1, h_r3 = list_h(R1, True), list_h(R3, False)
    h_r2 = HEADR + 18 + 3 * 30 + 6 + 3 * LH + 10
    H5 = max(h_r1, h_r2, h_r3)

    for i, (ttl, sub) in enumerate([("data/final — 결과 파일", "s07 · s07k · s07e · s09c"),
                                    (f"지금 태그 {n_all:,}사 · tag_current", ""),
                                    ("site/ — 웹페이지", "s08 → data.js · s10 → dividend.js")]):
        x = rx_[i]
        rect(x, S5, rw, H5, PAPER, INK, rx=8, sw=1.3)
        rect(x, S5, rw, HEADR, INK, rx=8)
        rect(x, S5 + HEADR - 10, rw, 10, INK, rx=0)
        text(x + 12, S5 + 21, ttl, 13.5, 700, PAPER)
        if sub:
            text(x + rw - 12, S5 + 21, sub, 11, 500, "#d0d5dd", anchor="end", mono=True)
    for i, items, mono in ((0, R1, True), (2, R3, False)):
        x = rx_[i]
        yy = S5 + HEADR + 22
        for a, b in items:
            for ln in wrap(a, rw - 24, 12 if mono else 12.5, bold=True, mono=mono):
                text(x + 12, yy, ln, 12 if mono else 12.5, 700, INK, mono=mono)
                yy += 16
            for ln in wrap(b, rw - 24, 12):
                text(x + 12, yy, ln, 12, 400, MUTED)
                yy += 16
            yy += 6
    # 막대
    x = rx_[1]
    bar_l = x + 12 + 92
    bar_w = rw - 24 - 92
    yy = S5 + HEADR + 16
    order = ["정관no", "정관yes", "정관yesorno"]
    for name, cnt in (("코스피", by_mkt["코스피"]), ("코스닥", by_mkt["코스닥"]), ("합계", now)):
        tot = sum(cnt.values())
        text(x + 12, yy + 14, f"{name} {tot:,}", 12.5, 700, INK)
        sx = bar_l
        for tg in order:
            sw_ = bar_w * cnt[tg] / tot
            rect(sx, yy, max(sw_ - 1.5, 0.8), 20, TAGC[tg], rx=2)
            s = f"{cnt[tg]:,}"
            if sw_ - 1.5 >= tw(s, 11, True) + 8:
                text(sx + 5, yy + 14.5, s, 11, 700, PAPER if tg != "정관yesorno" else INK)
            sx += sw_
        yy += 30
    yy += 8
    for tg, mean in (("정관no", "이사회가 기준일을 정함 (정관no)"), ("정관yes", "정관상 결산일로 고정 (정관yes)"),
                     ("정관yesorno", "결산일 원칙 + 이사회 (정관yesorno)")):
        rect(x + 12, yy - 10, 11, 11, TAGC[tg], rx=2)
        s = f"{LBL[tg]} {now[tg]:,}"
        text(x + 30, yy, s, 12.5, 700, INK)
        text(x + 30 + tw(s, 12.5, True) + 8, yy, mean, 12, 400, MUTED)
        wrap(f"{s} {mean}", rw - 42, 12.5)
        yy += LH
    # ④ → ⑤
    for i, lab in enumerate(["결과표", "tag_current", "웹페이지 데이터"]):
        cx = rx_[i] + rw / 2
        arrow(cx, S4b + 2, cx, S5 - 3, "k", sw=1.6)
        label(cx + 8, S5 - 13, lab, fill=INK)

    # 단계 레일
    stages = [("① 출처 · 데이터 · 목적", S1, bot1 + 14), ("② 업무", bot1 + 20, panel_bot),
              ("③ LLM", S3, S3b), ("④ 검증 · 합치기", S4, S4b), ("⑤ 결과", S5, S5 + H5)]
    for name, a, b in stages:
        fill = LLM_TINT if "LLM" in name else "#eef1f5"
        rect(RAIL_X, a, RAIL_W, b - a, fill, LLM_LINE if "LLM" in name else LINE, rx=7)
        text(RAIL_X + RAIL_W / 2 + 4.5, (a + b) / 2, name, 13, 700, LLM_C if "LLM" in name else BODY,
             anchor="middle", rotate=-90)

    foot = S5 + H5 + 30
    text(24, foot, "숫자는 data/final 기준(2026-11-17 반영본). 규칙 docs/01 · 열 docs/02 · 검증 docs/03 · 태깅 docs/04. "
         "다시 그리기: python -X utf8 scripts/make_flow_svg.py", 11.5, 400, MUTED)
    return "\n".join(P), int(foot + 18)


def main() -> None:
    body, H = build()
    defs = "".join(
        f'<marker id="ah-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
        for k, c in MARK.items())
    aria = ("kospi-charter 데이터 흐름: OpenDART·DART 공시 화면·KIND·규제 원문에서 받은 자료를 기준 설정·판별 원문·변경 추적·확인 대조 "
            "네 갈래로 묶고, 스캔 전사·기준일 판별·주총 안건·결과 판별 세 곳에만 LLM 을 넣은 뒤, 인용 대조·규칙 판별·재검토(Claude 원문 대조)·KIND 가결로 "
            "검사해 지금 태그(tag_current, 화면 표기 N·Y·YorN)를 만들고, 회사가 공시부에 낸 배당기준일 조건과 대조해 결과 파일·웹페이지를 만든다.")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{escape(aria)}">\n<title>kospi-charter 데이터 흐름</title>\n'
           f'<style>text{{font-family:{FONT}}} .m{{font-family:{MONO}}}</style>\n'
           f'<defs>{defs}</defs>\n<rect width="{W}" height="{H}" fill="{PAPER}"/>\n{body}\n</svg>\n')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {W}×{H}")
    for w in WARN:
        print("  !", w)


if __name__ == "__main__":
    main()
