"""s04b 스캔 정관(이미지) → OCR 글 — Windows 내장 OCR(Windows.Media.Ocr, 한국어 'ko')

왜: s04 가 내려받은 정관 가운데 content_type 이 image·mixed 인 문서는 본문이 스캔 이미지라서
    charter.txt 에는 '[이미지 001: …] → img/001.jpg' 표시 줄만 있고 조문 글자가 없다.
    정관 조항을 찾고 비교하려면 이 이미지들을 글로 바꿔야 한다.
    엔진은 Windows 에 들어 있는 OCR 이다 (파이썬 winocr 패키지로 부른다). 큰 OCR 모델(torch·paddle)이나
    Tesseract 를 따로 깔지 않아도 되고, 깔끔하게 렌더링된 A4 쪽은 잘 읽는다. 네트워크는 쓰지 않는다.

무엇을:
 1) 대상 — data/charter/{종목코드}_{회사명}/{첨부일자}_{dcmNo}/ 가운데 meta.json 이 있고
     content_type 이 image·mixed 인 문서 (meta.json 은 s04 가 마지막에 쓰므로 있으면 내려받기가 끝난 것)
 2) 쪽마다 전처리 → OCR → 줄 정리 (쪽은 2~4개를 동시에, 기본 3)
     전처리  흑백 → 긴 변 3000px 로 확대·축소(LANCZOS, 최대 4.5배) → autocontrast(1%)
             파일럿(문서마다 1쪽, 71쪽)에서 원본 크기·흑백·높이 1754/2339/2480/3000/3508·이진화·샤프닝을
             견줘 골랐다. 작은 스캔(높이 1300px 미만)은 원본 그대로면 크게 틀리고(예 '제자업 및 목자 가공 판매압'),
             키우면 바로잡힌다. 이진화는 오히려 나빠진다.
     줄 정리  엔진이 한 줄을 여러 '줄'로 나눠 내놓는 경우가 있다(목록 번호 '43.' 과 본문, 양쪽 정렬로 벌어진 낱말).
             세로로 절반 이상 겹치는 OCR 줄을 한 줄로 묶어 왼쪽부터 잇는다.
     원문자  엔진에 ①②③ 글자가 없어 '0', '(2)', '㉣', '(로' 처럼 읽거나 아예 빠뜨린다.
             줄 머리(그리고 '제N조(제목)' 바로 뒤)에서 동그라미를 영상으로 찾고(Hough 원 + 테두리 잉크 비율),
             찾으면 엉터리로 읽힌 낱말을 지우고 원문자를 넣는다. 동그라미를 못 찾아도 줄 머리가 '㉭'·'㉦'(원 자모)·
             '@'·'(7' 이면 원문자로 본다. 번호는 동그라미 안쪽만 잘라 따로 OCR 해서 읽고(3가지로 잘라 표결,
             파일럿 529개 중 92% 가 읽힘), 읽은 숫자가 앞 번호와 앞뒤가 맞으면 쓰고 아니면 앞 번호 + 1.
             '제N조(' 줄마다 0 으로 돌아간다. 저해상도 스캔에서 동그라미도 숫자도 놓치면 그 조의 뒤 번호가 밀릴 수 있다.
     글자    날짜에서 빠진 점 '2012.0323'·'2014.321'·'20193.22' → '2012.03.23'·'2014.3.21'·'2019.3.22'
             (텍스트 정관 277건에는 이런 꼴이 1번뿐이다. 3자리가 '1.23'·'12.3' 둘 다 될 수 있으면 두지 않는다),
             한글 사이 '•' → '·', 줄 머리 '재3조'·'케4조' 같은 '제' 오독 → '제',
             정관 핵심 낱말의 되풀이 오독 12가지(사재→사채, 종회→총회, 견우→경우 … TERM_FIXES — 틀린 꼴이
             텍스트 정관에 없는 것만)와 '주식?수선택권' → '주식매수선택권'. 그 밖의 오자는 고치지 않는다.
             띄어쓰기는 엔진이 낱말 상자마다 띄우는데 음절 사이에 끼우는 일은 거의 없어(17,000 간격 중 ~9) 손대지 않는다.
             '제 4 조'처럼 띄운 꼴도 원문(텍스트 정관의 약 20%)에 있으므로 그대로 둔다.
 3) 정리 — 문서 폴더에 (charter.txt·meta.json·이미지·html 은 건드리지 않는다)
     charter_ocr.txt  charter.txt 와 같은 틀. 이미지 표시 줄 바로 아래에 그 쪽의 OCR 글을 줄마다 넣는다.
                      이미지가 아닌 줄(mixed 문서의 본문)은 그대로 둔다. 같은 이미지가 두 번 나오면 처음 자리에만 넣고,
                      실패한 쪽은 '[OCR 실패: …]' 한 줄을 넣는다.
     ocr.json         엔진(이름·패키지 버전)·언어·만든 때·설정·쪽별 {file, sha256, lines, chars, seconds}·글자 수·오류
 4) 다시 돌리면 — 이미지 sha256 이 ocr.json 과 같고 오류가 없던 문서는 건너뛴다. 새 문서·바뀐 문서·실패가 있던 문서만 한다.
     설정(전처리·후처리)을 바꿨으면 --force 로 모두 다시 한다.

출력  data/charter/…/charter_ocr.txt, ocr.json
      data/interim/s04b_ocr.json   문서 폴더 → {pages, total_chars, errors, ocr_txt}

실행  python -X utf8 scripts/s04b_charter_ocr.py [--limit N] [--force] [--workers 3]
필요  Windows 10/11 + 한국어 OCR 언어팩(설정 → 언어에 한국어가 있으면 보통 들어 있다), winocr, opencv-python(-headless), numpy, pillow
"""
import asyncio
import hashlib
import json
import os
import platform
import re
import statistics
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
from _common import CHARTER, INTERIM, ROOT, now_iso, write_json  # noqa: E402

LANG = "ko"
LONG_SIDE = 3000          # 전처리 후 긴 변 (A4 세로면 높이 3000 ≈ 256dpi, 본문 글자 높이 30~40px)
MAX_UP = 4.5              # 아주 작은 이미지는 이 배율까지만 키운다
AC_CUTOFF = 1             # autocontrast 양끝 잘라낼 비율(%)
ROW_OVERLAP = 0.5         # 세로 겹침이 작은 쪽 높이의 이 비율 이상이면 한 줄
RING = {"min_r": 0.34, "max_r": 0.62, "hough_param2": 14, "min_cover": 0.86, "min_outer_white": 0.70,
        "fill": (0.05, 0.80)}   # 반지름·문턱은 줄 글자 높이(H) 기준
DIGIT_TILES = ((0.72, True, 48), (0.72, False, 64), (0.72, False, 48))   # 동그라미 안 숫자 읽기: (안쪽 반지름 비율, 이진화, 높이 px)
# 엔진이 ㅊ 을 ㅈ 으로 읽는 등 정관 핵심 낱말에서 되풀이되는 오독. 왼쪽 꼴은 텍스트 정관 277건에 한 번도 없고
# (주주종회·종회 오타 1번), OCR 글에는 수십~천 번 나온다 (2026-11-16 66개 문서 기준 사재 1,137 · 종회 707 …).
# 한 음절 차이를 사전으로 자동 교정하지는 않는다 ('한화'→'한다' 같은 잘못 고침이 생긴다).
TERM_FIXES = (("사재", "사채"), ("종회", "총회"), ("발행주식종수", "발행주식총수"), ("액면종액", "액면총액"),
              ("서을특별시", "서울특별시"), ("대자대조표", "대차대조표"), ("견우", "경우"), ("개경", "개정"),
              ("성약", "청약"), ("절자", "절차"), ("저분", "처분"), ("저음", "처음"))
_OPTION = re.compile(r"주식[^\s매]{1,3}수선택권")         # '주식0H수선택권'·'주식마1수선택권'

SETTINGS = {
    "preprocess": f"grayscale → resize long side to {LONG_SIDE}px (LANCZOS, upscale ≤ {MAX_UP}x) "
                  f"→ autocontrast(cutoff={AC_CUTOFF}%) → Gray8 SoftwareBitmap",
    "long_side": LONG_SIDE, "max_upscale": MAX_UP, "autocontrast_cutoff": AC_CUTOFF,
    "row_merge": f"OCR lines overlapping vertically ≥ {ROW_OVERLAP} of the smaller height are one row, words left→right",
    "word_join": "engine words joined by one space (no re-spacing)",
    "circled_numbers": "ring found at row start (or right after '제N조(…)') by HoughCircles + ink coverage "
                       f"{RING}; garbled token ('0','㉣','@','(2)'…) removed; row-start circled jamo ㉠-㉭, "
                       "lone '@'/'Ø'/'(7' also taken as a marker; digit inside ring read by OCR of ring interiors "
                       f"{list(DIGIT_TILES)} (vote); number = consistent read (1 or prev+1..prev+3) else prev+1; "
                       "reset at each article row '제N조('",
    "ring_params": RING, "digit_tiles": DIGIT_TILES,
    "text_fixes": ["date dots: YYYY.MMDD / YYYY.MDD(unambiguous) / YYYYM.DD / YYYYMM.DD → YYYY.M.D",
                   "'•' between Hangul → '·'", "row-start 재/저/지/체/케/졔/져 + N조|장 → 제",
                   "term fixes (ㅊ read as ㅈ etc.): " + ", ".join(f"{a}→{b}" for a, b in TERM_FIXES)
                   + ", 주식?수선택권→주식매수선택권"],
}

_MARK = re.compile(r"\[이미지 [^\n]*?\] → (img/[^\s|\]]+)")
# 조 제목 줄: '제3조 (', '제7조의2(', '제 4 조【' — 오독('재3조', '9 조의 3 (')도 받는다. '제12조의 규정에…' 같은 이어지는 줄은 아니다
_ART = re.compile(r"^\S{0,2}\s*\d+\s*조(?:\s*의\s*\d+)?\s*(?:[(\[（【〔<]|$)")
_HEAD_FIX = re.compile(r"^[재저지체케졔져](\s*\d+\s*(?:조|장))")
_CIRCLED = [chr(c) for c in range(0x2460, 0x2474)] + [chr(c) for c in range(0x3251, 0x3260)] + \
           [chr(c) for c in range(0x32B1, 0x32C0)]          # ①…⑳ ㉑…㉟ ㊱…㊿
_ANG = np.linspace(0, 2 * np.pi, 72, endpoint=False)
_COS, _SIN = np.cos(_ANG), np.sin(_ANG)

cv2.setNumThreads(1)      # 다른 작업이 도는 PC — OpenCV 가 코어를 다 쓰지 않게
_tls = threading.local()


# ── 엔진 ────────────────────────────────────────────────────────────────────
def engine_info() -> dict:
    def ver(p):
        try:
            return metadata.version(p)
        except metadata.PackageNotFoundError:
            return None
    return {"name": "Windows.Media.Ocr (Windows built-in OCR)", "package": f"winocr {ver('winocr')}",
            "winrt": f"winrt-Windows.Media.Ocr {ver('winrt-Windows.Media.Ocr')}",
            "opencv": ver("opencv-python-headless") or ver("opencv-python"), "pillow": ver("pillow"),
            "os": f"{platform.system()} {platform.version()}"}


def _engine():
    if getattr(_tls, "eng", None) is None:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
        if not OcrEngine.is_language_supported(Language(LANG)):
            raise SystemExit("Windows OCR 한국어(ko) 언어팩이 없습니다 — 설정 → 시간 및 언어 → 언어에서 한국어를 추가하세요.")
        _tls.eng = OcrEngine.try_create_from_language(Language(LANG))
    return _tls.eng


def recognize(img: Image.Image) -> list[list[tuple]]:
    """흑백 PIL 이미지 → OCR 줄 목록. 줄 = [(낱말, x, y, w, h), …] (전처리한 이미지 좌표)."""
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter

    w = DataWriter()
    w.write_bytes(img.tobytes())
    sb = SoftwareBitmap.create_copy_from_buffer(w.detach_buffer(), BitmapPixelFormat.GRAY8, img.width, img.height)
    eng = _engine()

    async def run():
        return await eng.recognize_async(sb)

    res = asyncio.run(run())
    out = []
    for ln in res.lines:
        ws = [(x.text, x.bounding_rect.x, x.bounding_rect.y, x.bounding_rect.width, x.bounding_rect.height)
              for x in ln.words]
        if ws:
            out.append(ws)
    return out


def preprocess(path: Path) -> Image.Image:
    with Image.open(path) as im:
        g = ImageOps.grayscale(im)
    s = min(MAX_UP, LONG_SIDE / max(g.size))
    if abs(s - 1) > 0.01:
        g = g.resize((max(1, round(g.width * s)), max(1, round(g.height * s))), Image.LANCZOS)
    return ImageOps.autocontrast(g, cutoff=AC_CUTOFF)


# ── 줄 정리 ─────────────────────────────────────────────────────────────────
def merge_rows(lines: list[list[tuple]]) -> list[list[tuple]]:
    """세로로 겹치는 OCR 줄을 한 줄로 묶고(위→아래), 줄 안 낱말은 왼→오."""
    items = []
    for ws in lines:
        y0, y1 = min(w[2] for w in ws), max(w[2] + w[4] for w in ws)
        items.append({"y0": y0, "y1": y1, "x0": min(w[1] for w in ws), "words": ws})
    items.sort(key=lambda it: (it["y0"] + it["y1"]) / 2)
    rows = []
    for it in items:
        hit = None
        for r in rows[-4:]:
            ov = min(r["y1"], it["y1"]) - max(r["y0"], it["y0"])
            if ov >= ROW_OVERLAP * min(r["y1"] - r["y0"], it["y1"] - it["y0"]):
                hit = r
        if hit:
            hit["parts"].append(it)
            hit["y0"], hit["y1"] = min(hit["y0"], it["y0"]), max(hit["y1"], it["y1"])
        else:
            rows.append({"y0": it["y0"], "y1": it["y1"], "parts": [it]})
    out = []
    for r in rows:
        r["parts"].sort(key=lambda it: it["x0"])
        out.append([w for it in r["parts"] for w in it["words"]])
    return out


def _ring_cover(b: np.ndarray, cx: float, cy: float, r: float, fs) -> float:
    """중심 (cx, cy) 반지름 r 의 원 위 72 방향 가운데, 반지름 배율 fs 어디엔가 잉크가 있는 방향의 비율."""
    h, w = b.shape
    n = 0
    for c, s in zip(_COS, _SIN):
        for f in fs:
            x, y = int(round(cx + f * r * c)), int(round(cy + f * r * s))
            if 0 <= x < w and 0 <= y < h and b[y, x]:
                n += 1
                break
    return n / len(_ANG)


def find_ring(gray: np.ndarray, ink: np.ndarray, x0, x1, y0, y1, H: float):
    """영역 안의 원문자 동그라미 → (왼쪽 x, 오른쪽 x, 중심 x, 중심 y, 반지름) 또는 None. 여럿이면 가장 왼쪽."""
    hh, ww = gray.shape
    X0, X1, Y0, Y1 = max(0, int(x0)), min(ww, int(x1)), max(0, int(y0)), min(hh, int(y1))
    if X1 - X0 < H or Y1 - Y0 < 0.8 * H:
        return None
    g = cv2.GaussianBlur(gray[Y0:Y1, X0:X1], (3, 3), 0)
    b = ink[Y0:Y1, X0:X1]
    cs = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=0.8 * H, param1=120, param2=RING["hough_param2"],
                          minRadius=int(RING["min_r"] * H), maxRadius=int(RING["max_r"] * H) + 1)
    if cs is None:
        return None
    best = None
    yy, xx = np.ogrid[:b.shape[0], :b.shape[1]]
    for cx, cy, r in cs[0]:
        if _ring_cover(b, cx, cy, r, (0.82, 0.9, 0.98, 1.06, 1.14)) < RING["min_cover"]:
            continue                                            # 테두리가 원으로 이어져 있어야
        if 1 - _ring_cover(b, cx, cy, r, (1.3, 1.4)) < RING["min_outer_white"]:
            continue                                            # 바깥은 비어 있어야 (굵은 한글 글자 배제)
        inner = (xx - cx) ** 2 + (yy - cy) ** 2 <= (0.5 * r) ** 2
        fill = b[inner].mean() / 255 if inner.any() else 0
        if not (RING["fill"][0] <= fill <= RING["fill"][1]):
            continue                                            # 안에 숫자가 있어야 (○·ㅇ 배제)
        cand = (X0 + cx - r, X0 + cx + r, X0 + cx, Y0 + cy, r)
        if best is None or cand[0] < best[0]:
            best = cand
    return best


# 엔진이 동그라미를 읽어 낸 엉터리 앞머리: '㉦'·'㉭'(원 자모)·'@'·'Ø'·'0'·'(0'·'(9' … 바로 뒤에 한글이 와야 한다
_GARB = re.compile(r"^(?:[(\[{][0-9OoØø@©®㉠-㉭①-⑳]?[)\]}]?|[0OoØø@©®㉠-㉭①-⑳][)\]}]?)(?=[가-힣(「“\"'‘])")
# 동그라미를 못 찾았어도 원문자로 보는 줄 머리 낱말: 낱말 전체가 '@'·'Ø'·'㉭'·'(7' 이거나, '㉭' 로 시작
_MARK_WHOLE = re.compile(r"[@Øø㉠-㉭]|[㉠-㉭][)\]}]|\(\d")
_MARK_HEAD = re.compile(r"[㉠-㉭][)\]}]?(?=\S)")


def _apply_ring(ws: list[tuple], i: int, ring) -> tuple[list[tuple], str | None]:
    """동그라미가 낱말 i 에 걸치면 엉터리로 읽힌 그 낱말(또는 앞머리 '㉦'·'(0'·'@')을 지운다.

    돌려주는 값: (낱말 목록, 지운 글자) — 지운 글자가 None 이면 동그라미가 아니라고 본 것, '' 이면 지운 것 없이 넣기만.
    """
    if ring is None:
        return ws, None
    rx0, rx1 = ring[:2]
    w = ws[i]
    ov = min(rx1, w[1] + w[3]) - max(rx0, w[1])
    if ov <= 0.15 * (rx1 - rx0):
        return ws, ""                                            # 엔진이 동그라미를 빠뜨림 → 넣기만
    if re.match(r"[가-힣A-Za-z]", w[0]):
        return ws, None                                          # 글자로 읽힌 낱말과 겹침 = 굵은 글자를 잘못 본 것
    if ov >= 0.6 * w[3] and len(w[0]) <= 4 and not re.fullmatch(r"\d{2,}\.?", w[0]):
        return ws[:i] + ws[i + 1:], w[0]                         # 낱말 전체가 동그라미 ('0', '㉣', '(로', '(2)')
    m = _GARB.match(w[0])
    if not m:
        return ws, None                                          # '1956.03.05' 의 '9' 같은 숫자 고리, '(16)' 의 '(1'
    return ws[:i] + [(w[0][m.end():],) + w[1:]] + ws[i + 1:], m.group(0)


_DIGIT_LOOKALIKE = str.maketrans({"l": "1", "I": "1", "|": "1", "i": "1", "!": "1", "O": "0", "o": "0",
                                  "S": "5", "s": "5", "Z": "2", "z": "2", "B": "8", "q": "9", "g": "9",
                                  "(": None, ")": None, ".": None, ",": None, "'": None, " ": None})




def _digit_strip(gray: np.ndarray, rings: list[tuple], k_ratio: float, binar: bool, size: int) -> list[int | None]:
    """동그라미 안쪽(반지름 k_ratio·r, 테두리 바깥은 흰색)을 잘라 한 줄로 늘어놓고 OCR 한 번 → 동그라미마다 숫자."""
    tiles = []
    for (_, _, cx, cy, r) in rings:
        k = k_ratio * r
        x0, y0 = max(0, int(round(cx - k))), max(0, int(round(cy - k)))
        c = gray[y0:int(round(cy + k)), x0:int(round(cx + k))].copy()
        if c.size == 0:
            tiles.append(None)
            continue
        yy, xx = np.ogrid[:c.shape[0], :c.shape[1]]
        c[(xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2 > k * k] = 255
        c = cv2.resize(c, (max(1, round(c.shape[1] * size / c.shape[0])), size), interpolation=cv2.INTER_CUBIC)
        if binar:
            _, c = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        tiles.append(c)
    gap, pad = 70, 40
    canvas = np.full((size + 2 * pad, pad * 2 + sum((t.shape[1] if t is not None else 0) + gap for t in tiles)),
                     255, np.uint8)
    spans, x = [], pad
    for t in tiles:
        if t is None:
            spans.append(None)
            continue
        canvas[pad:pad + size, x:x + t.shape[1]] = t
        spans.append((x, x + t.shape[1]))
        x += t.shape[1] + gap
    got = [""] * len(tiles)
    for ln in recognize(Image.fromarray(canvas)):
        for (txt, wx, _, ww, _) in ln:
            mid = wx + ww / 2
            for j, sp in enumerate(spans):
                if sp and sp[0] - gap / 2 <= mid <= sp[1] + gap / 2:
                    got[j] += txt
    out = []
    for t in got:
        t = t.translate(_DIGIT_LOOKALIKE)
        out.append(int(t) if t.isdigit() and 1 <= int(t) <= 50 else None)
    return out


def _read_digits(gray: np.ndarray, rings: list[tuple]) -> list[list[int]]:
    """동그라미마다 읽은 숫자 후보 (잘라 내는 방식 3가지 × OCR — 파일럿 529개 중 92% 가 하나 이상 읽힘)."""
    if not rings:
        return []
    votes = [[] for _ in rings]
    for args in DIGIT_TILES:
        for v, d in zip(votes, _digit_strip(gray, rings, *args)):
            if d is not None:
                v.append(d)
    return votes


def page_rows(gray_img: Image.Image, lines: list[list[tuple]]) -> list[dict]:
    """줄 → [{'words': [...], 'ring': 원문자를 넣을 낱말 위치 또는 None, 'garbled': 지운 글자, 'digits': 읽은 숫자 후보}]."""
    a = np.asarray(gray_img)
    _, ink = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    out, found = [], []
    for ws in merge_rows(lines):
        H = statistics.median(w[4] for w in ws)
        y0, y1 = min(w[2] for w in ws), max(w[2] + w[4] for w in ws)
        row = {"words": ws, "ring": None, "garbled": None, "digits": []}
        if not is_article(" ".join(w[0] for w in ws)):
            w0 = ws[0]
            rg = find_ring(a, ink, w0[1] - 2.6 * H, w0[1] + max(w0[3], 1.6 * H) + 0.2 * H,
                           y0 - 0.45 * H, y1 + 0.45 * H, H)
            ws2, g = _apply_ring(ws, 0, rg)
            if g is not None:
                row.update(words=ws2, ring=0, garbled=g, box=rg)
                found.append(row)
            elif len(ws) > 1 and _MARK_WHOLE.fullmatch(w0[0]):   # 동그라미는 못 찾았지만 '㉭'·'@'·'(7' 로 읽힌 줄 머리
                row.update(words=ws[1:], ring=0, garbled=w0[0])
            elif (m := _MARK_HEAD.match(w0[0])):                 # '㉭이사는' → '이사는'
                row.update(words=[(w0[0][m.end():],) + w0[1:]] + ws[1:], ring=0, garbled=m.group(0))
        else:                                                    # '제3조(목적) ① …' 처럼 제목 뒤에 바로 오는 원문자
            for i in range(1, min(len(ws), 12)):
                if ws[i - 1][0].endswith(")"):
                    p, w = ws[i - 1], ws[i]
                    rg = find_ring(a, ink, p[1] + p[3] + 0.05 * H, w[1] + max(w[3], 1.6 * H) + 0.2 * H,
                                   y0 - 0.45 * H, y1 + 0.45 * H, H)
                    ws2, g = _apply_ring(ws, i, rg)
                    if g is not None:
                        row.update(words=ws2, ring=i, garbled=g, box=rg)
                        found.append(row)
                    break
        out.append(row)
    for row, v in zip(found, _read_digits(a, [r["box"] for r in found])):
        row["digits"] = v
    return out


_D4 = re.compile(r"(?<![\d.])((?:19|20)\d\d)\.(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")
_D3 = re.compile(r"(?<![\d.])((?:19|20)\d\d)\.(\d)(\d)(\d)(?![\d])")
_DY = re.compile(r"(?<![\d.])((?:19|20)\d\d)([1-9]|0[1-9]|1[0-2])\.(0?[1-9]|[12]\d|3[01])(?![\d])")


def _d3(m):
    y, a, b, c = m.groups()
    one = a != "0" and 1 <= int(b + c) <= 31            # a.bc
    two = 10 <= int(a + b) <= 12 and c != "0"           # ab.c
    if one and not two:
        return f"{y}.{a}.{b}{c}"
    if two and not one:
        return f"{y}.{a}{b}.{c}"
    return m.group(0)


def fix_text(s: str) -> str:
    s = _HEAD_FIX.sub(r"제\1", s)
    s = re.sub(r"(?<=[가-힣])\s?•\s?(?=[가-힣])", "·", s)
    s = _D4.sub(r"\1.\2.\3", s)
    s = _D3.sub(_d3, s)
    s = _DY.sub(r"\1.\2.\3", s)
    for a, b in TERM_FIXES:
        s = s.replace(a, b)
    return _OPTION.sub("주식매수선택권", s)


def is_article(text: str) -> bool:
    return bool(_ART.match(text))


def circled(n: int) -> str:
    return _CIRCLED[n - 1] if 1 <= n <= len(_CIRCLED) else f"({n})"


# ── 쪽 하나 ─────────────────────────────────────────────────────────────────
def ocr_page(path: Path) -> dict:
    t = time.time()
    b = path.read_bytes()
    img = preprocess(path)
    rows = page_rows(img, recognize(img))
    return {"sha256": hashlib.sha256(b).hexdigest(), "rows": rows, "seconds": round(time.time() - t, 3)}


def number_rows(pages: list[dict]) -> None:
    """문서 전체를 쪽 차례로 훑으며 원문자 번호를 매기고 각 쪽의 'lines'(글 줄 목록)를 만든다.

    번호 = 동그라미 안에서 읽은 숫자 후보 가운데 앞 번호와 앞뒤가 맞는 것(1, 또는 앞 번호보다 1~3 큼)이 있으면
    표가 가장 많은 것(같으면 앞 번호 + 1 → 1 순), 없으면 앞 번호 + 1. 조 제목 줄('제N조(')에서 0 으로 돌아간다.
    """
    k = 0
    for pg in pages:
        lines = []
        for row in pg.get("rows", []):
            ws = [w[0] for w in row["words"]]
            if is_article(" ".join(ws)):
                k = 0
            if row["ring"] is not None:
                votes = Counter(row.get("digits") or [])
                ok = [d for d in votes if d == 1 or k < d <= k + 3]
                k = max(ok, key=lambda d: (votes[d], d == k + 1, d == 1, -d)) if ok else k + 1
                row["num"] = k
                ws = ws[:row["ring"]] + [circled(k)] + ws[row["ring"]:]
            s = fix_text(" ".join(ws).strip())
            if s:
                lines.append(s)
        pg["lines"] = lines


# ── 문서 하나 ───────────────────────────────────────────────────────────────
def _read_meta(d: Path):
    for _ in range(3):                    # s04 가 meta.json 을 다시 쓰는 중이면 잠깐 기다린다
        try:
            return json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            time.sleep(0.5)
    return None


def is_done(d: Path, meta: dict) -> bool:
    f, t = d / "ocr.json", d / "charter_ocr.txt"
    if not (f.exists() and t.exists()):
        return False
    try:
        o = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    want = [(i["file"], i.get("sha256")) for i in meta["images"]]
    have = [(p["file"], p.get("sha256")) for p in o.get("pages", [])]
    return want == have and not o.get("errors")


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def assemble(d: Path, meta: dict, pages: list[dict]) -> tuple[str, list[str]]:
    """charter.txt 의 이미지 표시 줄 아래에 그 쪽 OCR 글을 넣는다. 자리가 없는 쪽은 끝에 붙인다."""
    by_file = {p["file"]: p for p in pages}
    used, out = set(), []
    for line in (d / "charter.txt").read_text(encoding="utf-8").splitlines():
        out.append(line)
        for f in _MARK.findall(line):
            if f in by_file and f not in used:
                used.add(f)
                p = by_file[f]
                out.extend(p["lines"] if "error" not in p else [f"[OCR 실패: {p['error']}]"])
    unplaced = [p["file"] for p in pages if p["file"] not in used]
    for f in unplaced:
        p = by_file[f]
        out.append(f"[이미지 {Path(f).stem}: charter.txt 에 표시 줄 없음] → {f}")
        out.extend(p["lines"] if "error" not in p else [f"[OCR 실패: {p['error']}]"])
    return "\n".join(out) + "\n", unplaced


def run_doc(ex: ThreadPoolExecutor, d: Path, meta: dict, workers: int) -> dict:
    t0 = time.time()
    pages, futs = [], []
    for im in meta["images"]:
        p = {"file": im["file"]}
        pages.append(p)
        f = d / im["file"]
        if not (f.exists() and f.stat().st_size > 0):
            p["error"] = "이미지 파일 없음" + (f" (s04: {im['error']})" if im.get("error") else "")
            futs.append(None)
        else:
            futs.append(ex.submit(ocr_page, f))
    for p, fu in zip(pages, futs):
        if fu is None:
            continue
        try:
            p.update(fu.result())
        except Exception as e:  # noqa: BLE001 — 한 쪽 실패가 문서 전체를 멈추지 않게
            p["error"] = f"{type(e).__name__}: {e}"
    number_rows(pages)
    for p, im in zip(pages, meta["images"]):
        p.setdefault("lines", [])
        if "sha256" in p and im.get("sha256") and p["sha256"] != im["sha256"]:
            p["warning"] = "meta.json 의 sha256 과 다름 (이미지가 바뀜)"
    text, unplaced = assemble(d, meta, pages)
    errors = [{"file": p["file"], "error": p["error"]} for p in pages if "error" in p]
    rec_pages = []
    for p in pages:
        r = {"file": p["file"], "sha256": p.get("sha256"), "lines": len(p["lines"]),
             "chars": sum(len(s.replace(" ", "")) for s in p["lines"]), "seconds": p.get("seconds"),
             "circled": sum(1 for row in p.get("rows", []) if row["ring"] is not None)}
        if "warning" in p:
            r["warning"] = p["warning"]
        rec_pages.append(r)
    ocr = {"engine": engine_info(), "lang": LANG, "created_at": now_iso(),
           "settings": dict(SETTINGS, workers=workers),
           "content_type": meta["content_type"], "pages": rec_pages,
           "total_chars": sum(r["chars"] for r in rec_pages), "errors": errors,
           "unplaced_images": unplaced, "doc_seconds": round(time.time() - t0, 2)}
    _write(d / "charter_ocr.txt", text)
    _write(d / "ocr.json", json.dumps(ocr, ensure_ascii=False, indent=1))   # 마지막에 쓴다 = 끝났다는 표시
    return ocr


def index_entry(d: Path, o: dict) -> dict:
    return {"pages": len(o["pages"]), "total_chars": o["total_chars"], "errors": o["errors"],
            "ocr_txt": (d / "charter_ocr.txt").relative_to(ROOT).as_posix()}


def main(limit: int = 0, force: bool = False, workers: int = 3):
    workers = max(1, min(4, workers))
    t0 = time.time()
    targets, n_meta, n_wait = [], 0, 0
    for d in sorted(p.parent for p in CHARTER.glob("*/*/meta.json")):
        meta = _read_meta(d)
        if meta is None:
            n_wait += 1
            continue
        n_meta += 1
        if meta.get("content_type") in ("image", "mixed"):
            targets.append((d, meta))
    todo = [(d, m) for d, m in targets if force or not is_done(d, m)]
    print(f"meta.json {n_meta}개 (읽기 실패 {n_wait}) · OCR 대상(image/mixed) {len(targets)}개 · "
          f"할 일 {len(todo)}개 · 이미 끝남 {len(targets) - len(todo)}개", flush=True)
    if limit:
        todo = todo[:limit]                                   # 파일럿
    _engine()                                                 # 언어팩이 없으면 여기서 멈춘다

    n_pages = n_chars = n_fail = n_circ = 0
    ocr_sec = 0.0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (d, meta) in enumerate(todo, 1):
            o = run_doc(ex, d, meta, workers)
            n_pages += len(o["pages"])
            n_chars += o["total_chars"]
            n_fail += len(o["errors"])
            n_circ += sum(p["circled"] for p in o["pages"])
            ocr_sec += sum(p["seconds"] or 0 for p in o["pages"])
            print(f"  {i}/{len(todo)} {d.parent.name}/{d.name} {meta['content_type']} 쪽 {len(o['pages'])} "
                  f"글자 {o['total_chars']:,} 원문자 {sum(p['circled'] for p in o['pages'])} "
                  f"실패 {len(o['errors'])} {o['doc_seconds']}초", flush=True)

    index = {}
    for d, _ in targets:
        f = d / "ocr.json"
        if f.exists():
            try:
                index[d.relative_to(ROOT).as_posix()] = index_entry(d, json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
    write_json(INTERIM / "s04b_ocr.json", index)

    el = time.time() - t0
    print(f"끝 — 이번에 OCR 한 문서 {len(todo)}개 · 쪽 {n_pages} · 글자 {n_chars:,} · 원문자 {n_circ} · "
          f"실패 쪽 {n_fail} · 걸린 시간 {el:.0f}초"
          + (f" (쪽당 벽시계 {el / n_pages:.2f}초, 쪽당 처리 {ocr_sec / n_pages:.2f}초 × 동시 {workers})" if n_pages else ""))
    print(f"  색인 data/interim/s04b_ocr.json — 문서 {len(index)}개 · 쪽 {sum(v['pages'] for v in index.values())} · "
          f"글자 {sum(v['total_chars'] for v in index.values()):,} · 실패 쪽 {sum(len(v['errors']) for v in index.values())}"
          f" · 아직 안 한 문서 {len(targets) - len(index)}개")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 할 일 가운데 앞 N개 문서만")
    ap.add_argument("--force", action="store_true", help="끝난 문서도 다시 OCR")
    ap.add_argument("--workers", type=int, default=3, help="동시에 OCR 할 쪽 수 (1~4)")
    a = ap.parse_args()
    main(a.limit, a.force, a.workers)
