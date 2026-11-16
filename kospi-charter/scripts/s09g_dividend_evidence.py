"""s09g 배당기준일 태그의 근거 — 조항 단위 원문 · 스캔 쪽 잘라 낸 그림 · 소집공고 대비표 행 (웹페이지 s10 의 입력)

왜: 사용자 지시(2026-11-16) — 웹페이지 탭에 분류 근거가 된 문구를 **조항 단위**로 보인다. 텍스트 정관은 글을 그대로,
    스캔 정관은 그 쪽 그림의 해당 부분을, 주주총회소집공고가 근거면 그 공고의 '정관의 변경' 대비표를 보인다.

근거 조항 찾기 (정관)
  · s09b/s09c 의 인용(quotes)을 정관 전문(charter_fulltext_txt)에서 찾는다 — 공백을 지우고 비교(스캔 전사문 띄어쓰기 차이).
  · 인용이 든 **조**로 넓힌다: 앞쪽 가장 가까운 조 머리(`제N조`·`第N條`, 본문 속 참조가 아닌 것) ~ 다음 조 머리·장·부칙.
    조 머리를 못 찾는 서식(외국 법인 `16.11` 번호식 등)은 인용 앞뒤 600자를 줄 단위로 자른다. 한 조가 4,000자를 넘으면 인용 앞뒤 1,500자.
  · 인용이 여러 조에 걸치면(배당 조 + 참조한 기준일 조) 조마다 하나씩.
스캔 쪽 잘라 내기 (charter_llm.txt 의 `[이미지 NNN: …] → img/NNN.jpg` 표시로 쪽을 안다)
  · 그 쪽을 Windows 내장 OCR(s04b 의 preprocess·recognize)로 다시 읽어 줄 좌표를 얻고, 조항 글(Opus 전사)과 3글자 조각이
    절반 넘게 겹치는 줄이 이어진 구간을 찾아 위아래로 자른다(좌우는 쪽 전체). 못 찾으면 그 쪽 전체.
  · 저장 site/evidence/{종목코드}/{n}.jpg (긴 변 1,000px 이하, JPEG 75) — git 에 올려 GitHub Pages 에서도 보인다.
소집공고 ('정관의 변경' 절, s06 의 정관의변경.txt — 대비표 1행 = 1줄, 칸은 ' | ')
  · s09d 의 quotes_after 가 든 줄과 그 앞 머리줄('정관조항 | 변경전 내용 | 변경후 내용 | …')을 꺼낸다.

입력  data/final/charter_dividend_record_date.json (tag·quotes·charter_fulltext_txt) · s09_targets.json · 정관 meta.json
      data/interim/s09d_after_agm.jsonl · (있으면) s09f_prev.json (확인필요 3사의 전년도 정관)
출력  data/interim/s09g_evidence.json  종목코드 → {charter: {...}, notice: {...}, prev: {...}}
      site/evidence/…jpg

사용법
  python -X utf8 scripts/s09g_dividend_evidence.py                 # 전부 (스캔 쪽 OCR 은 이미 자른 그림이 있으면 건너뜀)
  python -X utf8 scripts/s09g_dividend_evidence.py --codes 499790  # 몇 곳만 (확인용)
  python -X utf8 scripts/s09g_dividend_evidence.py --no-ocr        # 그림 자르기 없이 글만
  python -X utf8 scripts/s09g_dividend_evidence.py --sfx kosdaq    # 코스닥 (charter_dividend_record_date_kosdaq.json 등)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, INTERIM, ROOT, now_iso, read_json, write_json  # noqa: E402
from s09a_dividend_excerpt import interim_of, paths  # noqa: E402
from s09b_dividend_tag_llm import read_results  # noqa: E402

OUT_F = INTERIM / "s09g_evidence.json"                # main() 의 --sfx 로 바뀐다 (코스닥: s09g_evidence_kosdaq.json)
EVI_DIR = ROOT / "site" / "evidence"
MAX_ART = 4000
WIN = 600

# 조 머리: 앞이 줄 머리·문장 끝이고, 뒤가 본문 속 참조('제1항', '에서', '의 규정' …)가 아닌 '제N조(의M)'
HEAD = re.compile(r"(?:제\s*(\d{1,3})\s*조|第\s*(\d{1,3})\s*條)(?:\s*의\s*(\d{1,2}))?")
NOT_HEAD_NEXT = re.compile(r"\s*(?:제\s*\d|第\s*\d|에|의\s*규정|의\s*\d|및|또는|부터|까지|와|과|를|을|은|는|이\s|가\s|로|으로|,|·|내지|"
                           r"\d|각\s*호|단서|본문|전단|후단|중|에\s*의|에\s*따)")
PREV_OK = set("\n.>])」다|*")
END_MARK = re.compile(r"(?:^|\n)\s*(?:제\s*\d+\s*장|第\s*\d+\s*章|<?\s*부\s*칙|附\s*則)")
IMG_MARK = re.compile(r"^\[이미지 (\d+)[^\n]*?\] → (img/\S+?)\s*$", re.M)
PDF_MARK = re.compile(r"^\[PDF (\d{3}): [^\n]*\] → (pdf/\S+)\s*$", re.M)
PDF_PAGE = re.compile(r"^\[쪽 (\d+)( · (?:OCR|Opus))?\]\s*$", re.M)


TITLE_NEXT = re.compile(r"\s*[|]?\s*[(（【\[〔<][^)）】\]〕>\n]{1,25}[)）】\]〕>]")


def is_head(t: str, m: re.Match) -> bool:
    if NOT_HEAD_NEXT.match(t, m.end()):
        return False
    if TITLE_NEXT.match(t, m.end()):            # 바로 뒤에 괄호 제목 — 줄바꿈 없는 한 줄 원문에서도 조 머리
        return True
    j = m.start() - 1
    while j >= 0 and t[j] in " \t":
        j -= 1
    return j < 0 or t[j] in PREV_OK


def heads(t: str) -> list[int]:
    return [m.start() for m in HEAD.finditer(t) if is_head(t, m)]


def squash_map(t: str) -> tuple[str, list[int]]:
    keep = [i for i, c in enumerate(t) if not (c.isspace() or ord(c) < 32)]      # 제어문자(\x01 등)도 공백처럼
    return "".join(t[i] for i in keep), keep


def find_quote(t: str, s: str, keep: list[int], q: str) -> tuple[int, int] | None:
    qs = re.sub(r"[\s\x00-\x1f]+", "", q.strip("「」\"' ").rstrip("…").strip())
    if not qs:
        return None
    for probe, mode in ((qs, "all"), (qs[:30], "head"), (qs[-30:], "tail")):
        if len(probe) < 8:
            continue
        p = s.find(probe)
        if p >= 0:
            if mode == "all":
                return keep[p], keep[p + len(probe) - 1] + 1
            if mode == "head":
                return keep[p], keep[min(len(keep) - 1, p + len(qs) - 1)] + 1
            st = max(0, p + len(probe) - len(qs))
            return keep[st], keep[p + len(probe) - 1] + 1
    return None


def loose_heads(t: str, lo: int, hi: int) -> list[int]:
    """앞 글자 조건 없이 본문 속 참조만 뺀 '제N조' 위치 — 괄호 제목 없는 조 머리('…처분액 제36조 이익배당금은')를 잡는다."""
    return [m.start() for m in HEAD.finditer(t, lo, hi) if not NOT_HEAD_NEXT.match(t, m.end())]


TITLE_RX = re.compile(r"\s*(?:제\s*\d{1,3}\s*조|第\s*\d{1,3}\s*條)(?:\s*의\s*\d{1,2})?\s*[|]?\s*"
                      r"(?:[(（【\[〔<][^)）】\]〕>\n]{1,25}[)）】\]〕>])?")


def art_title(text: str) -> str:
    m = TITLE_RX.match(text)
    if m and len(m.group(0).strip()) >= 3:
        return re.sub(r"\s+", " ", m.group(0)).strip(" |")
    return re.sub(r"\s+", " ", text.split("\n", 1)[0])[:40]


def article_span(t: str, hs: list[int], a: int, b: int) -> tuple[int, int, str]:
    before = [h for h in hs if h <= a]
    after = [h for h in hs if h >= b]
    if before and before[-1] > a - MAX_ART:
        s = before[-1]
        lh = [h for h in loose_heads(t, s + 1, a) if h > s]
        if lh:                                   # 그 사이에 괄호 제목 없는 조 머리가 있으면 거기서 시작
            s = lh[-1]
        e = after[0] if after else len(t)
        m = END_MARK.search(t, b, e)
        if m:
            e = m.start()
        if e - s <= MAX_ART:
            return s, e, "article"
    # 조 머리를 못 찾거나 너무 긴 조 — 인용 앞뒤를 줄 단위로
    w = WIN if not before else 1500
    s = t.rfind("\n", 0, max(0, a - w)) + 1
    e = t.find("\n", min(len(t), b + w))
    return s, (len(t) if e < 0 else e), "window"


def clean(txt: str) -> str:
    """보여 줄 글 — 쪽 표시 줄을 빼고 빈 줄을 줄인다."""
    txt = IMG_MARK.sub("", txt)
    txt = PDF_MARK.sub("", txt)
    txt = PDF_PAGE.sub("", txt)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def pages_of(t: str, s: int, e: int) -> list[dict]:
    """[s,e) 가 걸친 스캔 쪽 — 각 쪽에서 그 구간에 해당하는 전사 글도 함께."""
    marks = [(m.start(), m.end(), int(m.group(1)), m.group(2)) for m in IMG_MARK.finditer(t)]
    out = []
    for i, (ms, me, no, f) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        lo, hi = max(s, me), min(e, nxt)
        if lo < hi and t[lo:hi].strip():
            out.append({"page": no, "file": f, "text": t[lo:hi]})
    return out


def pdf_pages_of(t: str, s: int, e: int) -> list[dict]:
    out, pdf = [], None
    marks = sorted([(m.start(), "pdf", m) for m in PDF_MARK.finditer(t)] + [(m.start(), "pg", m) for m in PDF_PAGE.finditer(t)])
    spans = []
    for k, (pos, kind, m) in enumerate(marks):
        if kind == "pdf":
            pdf = (m.group(1), m.group(2))
            continue
        nxt = next((p for p, _, _ in marks[k + 1:]), len(t))
        spans.append((m.end(), nxt, pdf, int(m.group(1)), bool(m.group(2))))
    for lo0, hi0, pdf, pg, ocr in spans:
        lo, hi = max(s, lo0), min(e, hi0)
        if pdf and lo < hi and t[lo:hi].strip():
            out.append({"pdf": pdf[1], "pdf_no": pdf[0], "page": pg, "scanned": ocr, "text": t[lo:hi]})
    return out


# ── 스캔 쪽 잘라 내기 ────────────────────────────────────────────────────────
def grams(s: str) -> set[str]:
    s = re.sub(r"[\s\W_]+", "", s)
    return {s[i:i + 3] for i in range(len(s) - 2)}


def crop_page(img_path: Path, page_text: str, out: Path) -> dict:
    from PIL import Image
    import s04b_charter_ocr as O
    g = O.preprocess(img_path)
    with Image.open(img_path) as im:
        W, H = im.size
        scale = g.width / W
        lines = O.recognize(g)
        target = grams(page_text)
        rows = []
        for ws in lines:
            txt = "".join(w[0] for w in ws)
            y0 = min(w[2] for w in ws) / scale
            y1 = max(w[2] + w[4] for w in ws) / scale
            gs = grams(txt)
            hit = len(gs) >= 2 and len(gs & target) / len(gs) >= 0.5
            rows.append((y0, y1, hit))
        rows.sort()
        hits = [i for i, r in enumerate(rows) if r[2]]
        how = "lines"
        if not hits:
            y0, y1, how = 0, H, "page"
        else:
            # 맞는 줄이 가장 많이 이어진 구간 (사이에 안 맞는 줄 2개까지 허용)
            best, cur = (hits[0], hits[0]), [hits[0], hits[0]]
            n_best, n_cur = 1, 1
            for i in hits[1:]:
                if i - cur[1] <= 3:
                    cur[1] = i
                    n_cur += 1
                else:
                    cur, n_cur = [i, i], 1
                if n_cur > n_best:
                    best, n_best = (cur[0], cur[1]), n_cur
            y0 = max(0, rows[best[0]][0] - 18)
            y1 = min(H, rows[best[1]][1] + 18)
        box = (0, int(y0), W, int(y1))
        c = im.crop(box).convert("RGB")
        if max(c.size) > 1000:
            r = 1000 / max(c.size)
            c = c.resize((max(1, round(c.width * r)), max(1, round(c.height * r))), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        c.save(out, "JPEG", quality=75, optimize=True)
    return {"box": list(box), "size": [W, H], "how": how, "n_lines": len(rows), "n_hit": len(hits)}


# ── 한 회사 ─────────────────────────────────────────────────────────────────
def charter_evidence(code: str, src: str, quotes: list[str], meta: dict | None, ocr: bool, tag_key: str = "") -> dict:
    p = ROOT / src
    if not p.exists() or not quotes:
        return {"articles": [], "note": "원문 또는 인용 없음"}
    t = p.read_text(encoding="utf-8")
    s, keep = squash_map(t)
    hs = heads(t)
    spans = []
    for q in quotes:
        hit = find_quote(t, s, keep, q)
        if hit:
            a, b = hit
            spans.append((a, b, *article_span(t, hs, a, b), q))
    if not spans:
        return {"articles": [], "note": "인용을 원문에서 찾지 못함"}
    # 같은 조에 든 인용은 하나로
    arts = []
    for a, b, st, en, how, q in sorted(spans, key=lambda x: x[2]):
        if arts and st < arts[-1]["end"]:
            arts[-1]["end"] = max(arts[-1]["end"], en)
            arts[-1]["quotes"].append([a, b])
            continue
        arts.append({"start": st, "end": en, "how": how, "quotes": [[a, b]]})
    src_by_file = {im["file"]: im.get("src_url") for im in (meta or {}).get("images", [])}
    base = p.parent
    for k, art in enumerate(arts, 1):
        raw = t[art["start"]:art["end"]]
        art["text"] = clean(raw)
        art["title"] = art_title(art["text"])
        # 인용 위치 → 보여 줄 글(clean) 안의 위치: 인용 글 자체로 다시 찾는다
        art["marks"] = [re.sub(r"\s+", " ", t[a:b]).strip() for a, b in art["quotes"]]
        pgs = pages_of(t, art["start"], art["end"])
        art["images"] = []
        for i, pg in enumerate(pgs, 1):
            item = {"page": pg["page"], "file": pg["file"], "src_url": src_by_file.get(pg["file"])}
            out = EVI_DIR / f"{code}{tag_key}" / f"a{k}_p{pg['page']:03d}.jpg"
            if ocr and (base / pg["file"]).exists():
                side = out.with_suffix(".json")          # 자르기 정보(줄 단위/쪽 전체·상자) — 다시 돌릴 때 그림과 함께 재사용
                if not out.exists():
                    try:
                        cm = crop_page(base / pg["file"], pg["text"], out)
                        item.update(cm)
                        write_json(side, cm)
                    except Exception as ex:      # OCR 실패 — 쪽 전체 원본 주소만 남긴다
                        item["error"] = repr(ex)[:200]
                elif side.exists():
                    item.update(read_json(side))
                if out.exists():
                    item["crop"] = out.relative_to(ROOT).as_posix()
            art["images"].append(item)
        art["pdf_pages"] = [{k2: v for k2, v in x.items() if k2 != "text"} for x in pdf_pages_of(t, art["start"], art["end"])]
    return {"src": src, "articles": arts}


def notice_evidence(t: dict, quotes_after: list[str]) -> dict:
    out = []
    for p in t.get("agm_charter_amend_txt") or []:
        f = ROOT / p
        if not f.exists():
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        sq = [re.sub(r"\s+", "", ln) for ln in lines]
        pick = set()
        for q in quotes_after:
            qs = re.sub(r"\s+", "", q)[:40]
            for i, s in enumerate(sq):
                if qs and qs in s:
                    pick.add(i)
        if not pick:
            continue
        # 인용 앞부분이 여러 행에 걸리면 조 머리(행 앞 40자)에 '배당'이 든 행만 — 없으면 그대로
        div = [i for i in pick if re.search(r"배\s*당|配\s*當", lines[i][:40])]
        rows = []
        for i in sorted(div or pick):
            hdr = next((lines[j] for j in range(i - 1, max(-1, i - 6), -1) if "변경전" in sq[j] or "변경 전" in lines[j]), None)
            rows.append({"header": hdr, "line": lines[i]})
        rc = Path(p).parent.name                     # {접수일}_{rcept_no}
        out.append({"txt": p, "rcept_no": rc.split("_", 1)[-1], "rcept_dt": rc.split("_", 1)[0], "rows": rows})
    return {"tables": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--sfx", default="", help="코스닥 등 다른 표 (그림은 같은 site/evidence/{종목코드}/ — 코드가 겹치지 않는다)")
    a = ap.parse_args()
    global OUT_F
    OUT_F = interim_of(a.sfx, "s09g_evidence.json")
    only = {c.strip() for c in a.codes.split(",") if c.strip()}
    rows = read_json(paths(a.sfx)["out_json"])
    tg = {t["stock_code"]: t for t in read_json(paths(a.sfx)["targets"])}     # agm_charter_amend_txt 는 대상 표에
    after = {r["stock_code"]: r for r in read_results(interim_of(a.sfx, "s09d_after_agm.jsonl")).values() if r.get("output")}
    pre = {r["stock_code"]: r for r in read_results(interim_of(a.sfx, "s09i_pre_agm.jsonl")).values() if r.get("output")}
    pf = interim_of(a.sfx, "s09f_prev.json")
    prev = read_json(pf) if pf.exists() else {}
    old = read_json(OUT_F) if OUT_F.exists() else {}
    out = dict(old)
    n_img = 0
    for r in rows:
        code = r["stock_code"]
        if only and code not in only:
            continue
        if r["charter_fulltext_txt"]:
            meta_p = ROOT / Path(r["charter_fulltext_txt"]).parent / "meta.json"
            meta = read_json(meta_p) if meta_p.exists() else None
            ev = {"charter": charter_evidence(code, r["charter_fulltext_txt"], r["quotes"], meta, not a.no_ocr)}
        else:                                   # 정관 원문 없음 (코스닥 PDF 미판독 4사 등)
            ev = {"charter": {"articles": [], "missing": "정관 원문 없음"}}
        if code in after:
            ev["notice"] = notice_evidence(tg[code], after[code]["output"].get("quotes_after") or [])
        if code in pre and (pre[code]["output"] or {}).get("changes_record_date"):   # s09i — 사업보고서보다 먼저 접수된 소집공고
            txts = [p for p in (ROOT / "data").glob(f"agm{'_' + a.sfx if a.sfx else ''}_pre/{code}_*/*/정관의변경.txt")
                    if p.parent.name.split("_", 1)[-1] in pre[code]["rcept_nos"]]
            nv = notice_evidence({"agm_charter_amend_txt": [p.relative_to(ROOT).as_posix() for p in txts]},
                                 pre[code]["output"].get("quotes_after") or [])
            ev["notice"] = {"tables": ((ev.get("notice") or {}).get("tables") or []) + nv["tables"]}
        if code in prev and prev[code].get("quotes"):
            pv = prev[code]
            ntxt = [n["txt"] for n in pv.get("notices") or [] if n.get("txt")]
            if pv.get("charter_fulltext_txt"):           # 전년도 사업보고서 첨부 정관
                pmeta_p = ROOT / Path(pv["charter_fulltext_txt"]).parent / "meta.json"
                ev["prev"] = charter_evidence(code, pv["charter_fulltext_txt"], pv["quotes"],
                                              read_json(pmeta_p) if pmeta_p.exists() else None, not a.no_ocr, "_prev")
                ev["prev"]["notice"] = notice_evidence({"agm_charter_amend_txt": ntxt},
                                                       [q for n in pv.get("notices") or []
                                                        for q in (n.get("output") or {}).get("quotes_after") or []])
            else:                                        # 정관 원문 없음 (OCI) — 소집공고 안건 + 사업보고서 본문
                ev["prev"] = {"articles": [], "notice": notice_evidence({"agm_charter_amend_txt": ntxt}, pv["quotes"]),
                              "report_section": pv.get("report_dividend_section")}
        n_img += sum(1 for art in ev["charter"].get("articles", []) for im in art["images"] if im.get("crop"))
        out[code] = ev
        if len(out) % 50 == 0:
            write_json(OUT_F, out)
    write_json(OUT_F, out)
    arts = [art for v in out.values() for art in v["charter"].get("articles", [])]
    miss = [c for c, v in out.items() if not v["charter"].get("articles")]
    print(f"{now_iso()} 근거 {len(out)}사 · 조항 {len(arts)}개(조 단위 {sum(x['how'] == 'article' for x in arts)} · "
          f"창 {sum(x['how'] == 'window' for x in arts)}) · 잘라 낸 그림 {sum(1 for x in arts for im in x['images'] if im.get('crop'))}"
          f" · 근거 없음 {len(miss)} {miss[:10]}")


if __name__ == "__main__":
    main()
