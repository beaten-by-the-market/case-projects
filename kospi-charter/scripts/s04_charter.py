"""s04 코스피 행의 정관 첨부 → 원문 내려받기 (텍스트 / 이미지)

1) 정관 고르기 — s03 의 첨부문서 목록(attach_docs 와 같은 목록)에서 제목이 '정관'인 것
     제목 형식: 'YYYY.MM.DD [정정] 정관' / 'YYYY.MM.DD 정관'
     여럿이면 날짜가 가장 늦은 것, 같은 날이면 [정정] 이 붙은 것을 대표로 쓰고 나머지 개수는 남긴다.
2) 내려받기 — 정관 문서(rcpNo·dcmNo) 마다 한 번만
     첨부 main.do(=attach_docs 의 url) → 목차 노드(sub_docs 와 같은 규칙) → viewer.do 원문 HTML
     원문 안 <img src="/report/download.do?dcmNo=…&flNm=…"> 는 스캔 이미지 → 하나씩 내려받는다
3) 정리 — data/charter/{종목코드}_{회사명}/{첨부일자}_{dcmNo}/
     viewer_01.html   DART 원문 HTML 그대로 (노드가 여럿이면 02, 03 …)
     charter.txt      본문 텍스트. 이미지 자리에는 '[이미지 001: 캡션] → img/001.jpg' 줄을 넣는다
     img/001.jpg …    스캔 이미지 (원래 순서)
     meta.json        출처 URL·종류(text/image/mixed/empty)·글자 수·이미지 목록(크기·sha256)·이 정관을 쓰는 접수번호

출력  data/interim/s04_charter.json   rcept_no → 대표 정관·후보 수·문서 폴더
      data/interim/s04_docs.json      문서(dcmNo) → meta (meta.json 과 같은 내용)
"""
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

sys.path.insert(0, str(Path(__file__).parent))
from _common import (CHARTER, DART_WEB, INTERIM, RAW, ROOT, Http, cached_text, now_iso, read_json,  # noqa: E402
                     safe_name, sub_docs_from_html, write_json)

_TITLE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})\s+((?:\[[^\]]*\]\s*)*)(.*)$")
MIN_TEXT = 200          # 이 글자 수(공백 제외) 미만이면 '텍스트 없음'으로 본다
# 이미지 파일 앞머리 (JPEG·PNG·GIF·BMP·TIFF). DART 가 이미지 대신 HTML 오류 쪽을 줄 때가 있다 —
# 그 쪽이 줄바꿈으로 시작하면 '<' 검사로는 못 거른다(케이탑리츠 img/021.jpg, 2026-11-16) → 앞머리로 판정한다
IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"BM", b"II*\x00", b"MM\x00*")
PDF_HREF = re.compile(r"""<a\s[^>]*href\s*=\s*['"][^'"]*download\.do[^'"]*\.pdf['"]""", re.I)


def is_image(b: bytes) -> bool:
    return b.startswith(IMG_MAGIC)


def parse_att_title(title: str) -> dict:
    m = _TITLE.match(title.strip())
    if not m:
        return {"att_date": "", "att_tags": "", "att_name": title.strip()}
    return {"att_date": f"{m[1]}{m[2]}{m[3]}", "att_tags": m[4].replace(" ", ""), "att_name": m[5].strip()}


def is_charter(name: str) -> bool:
    """첨부 이름이 정관인가. '정 관'·'정관(전문)' 처럼 띄어쓰기·괄호 설명은 허용한다."""
    n = re.sub(r"\s", "", name)
    return n == "정관" or bool(re.match(r"^정관[\(\[<（].*[\)\]>）]$", n))


def pick(cands: list[dict]) -> dict:
    return max(cands, key=lambda a: (a["att_date"], "[정정]" in a["att_tags"], -a["att_order"]))


# ── 원문 HTML → 텍스트 ─────────────────────────────────────────────────────
def _txt(el) -> str:
    return " ".join(el.get_text(" ", strip=True).replace("\xa0", " ").split())


def html_to_text(html: str, img_files: dict[str, str]) -> tuple[str, int]:
    """viewer.do HTML → (텍스트, 본문 글자 수). 표는 행마다 ' | ' 로 칸을 잇는다."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    lines, n_chars = [], 0

    def walk(node):
        nonlocal n_chars
        for ch in node.children:
            if isinstance(ch, NavigableString):
                s = " ".join(str(ch).replace("\xa0", " ").split())
                if s:
                    lines.append(s)
                    n_chars += len(s.replace(" ", ""))
                continue
            if not isinstance(ch, Tag):
                continue
            name = ch.name.lower()
            if name in ("script", "style"):
                continue
            imgs = ch.find_all("img") if name != "img" else [ch]
            if name == "table" and imgs and _is_image_table(ch):
                for im in imgs:                         # 이미지 표: 이미지 + 캡션
                    f = img_files.get(im.get("src", ""), "")
                    cap = _caption_for(ch, im)
                    lines.append(f"[이미지 {Path(f).stem if f else '???'}: {cap}] → {f}")
                continue
            if name == "img":
                f = img_files.get(ch.get("src", ""), "")
                lines.append(f"[이미지 {Path(f).stem if f else '???'}: {ch.get('alt', '')}] → {f}")
                continue
            if name == "table":
                for tr in ch.find_all("tr"):
                    cells = [_txt(td) for td in tr.find_all(["td", "th", "te", "tu"])]
                    for im in tr.find_all("img"):
                        f = img_files.get(im.get("src", ""), "")
                        cells.append(f"[이미지 {Path(f).stem if f else '???'}] → {f}")
                    row = " | ".join(c for c in cells if c)
                    if row:
                        lines.append(row)
                        n_chars += len(re.sub(r"\[이미지[^\]]*\] → \S*", "", row).replace(" ", "").replace("|", ""))
                continue
            if name in ("p", "h1", "h2", "h3", "h4", "li", "title-1"):
                if "img-caption" in (ch.get("class") or []):
                    continue
                if ch.find("img"):
                    walk(ch)
                    continue
                s = _txt(ch)
                if s:
                    lines.append(s)
                    n_chars += len(s.replace(" ", ""))
                continue
            walk(ch)

    walk(body)
    return "\n".join(lines) + "\n", n_chars


def _is_image_table(table) -> bool:
    """표 안 글자가 이미지 캡션뿐이면 이미지 표 (DART 가 스캔 한 장마다 표 하나로 감싼다)."""
    body = _txt(table).replace(" ", "")
    for p in table.find_all("p", class_="img-caption"):
        body = body.replace(_txt(p).replace(" ", ""), "", 1)
    return body == ""


def _caption_for(table, im) -> str:
    caps = table.find_all("p", class_="img-caption")
    return _txt(caps[0]) if caps else (im.get("alt", "") or "").replace("이미지: ", "")


# ── 내려받기 ────────────────────────────────────────────────────────────────
def doc_dir(stock_code: str, corp_name: str, att_date: str, dcm_no: str) -> Path:
    return CHARTER / f"{stock_code or 'NOCODE'}_{safe_name(corp_name)}" / f"{att_date}_{dcm_no}"


def fetch_doc(http: Http, img_http: Http, doc: dict) -> dict:
    d = doc_dir(doc["stock_code"], doc["corp_name"], doc["att_date"], doc["dcmNo"])
    meta_f = d / "meta.json"
    if meta_f.exists():
        return read_json(meta_f)
    d.mkdir(parents=True, exist_ok=True)
    att_html = cached_text(RAW / "dart_att" / f"{doc['rcpNo']}_{doc['dcmNo']}.html",
                           lambda: http.get(doc["att_url"]).text)
    nodes = sub_docs_from_html(att_html)
    # 목차 노드가 겹치면(상위 절이 하위 절을 포함) 바깥 노드만 받는다
    nodes.sort(key=lambda n: (int(n["offset"]), -int(n["length"])))
    top, end = [], -1
    for n in nodes:
        if int(n["offset"]) >= end:
            top.append(n)
            end = int(n["offset"]) + int(n["length"])

    texts, n_chars, images, viewer_urls = [], 0, [], []
    has_pdf = False
    for k, n in enumerate(top, 1):
        vf = d / f"viewer_{k:02d}.html"
        html = cached_text(vf, lambda: http.get(n["url"]).text)
        viewer_urls.append(n["url"])
        soup = BeautifulSoup(html, "lxml")
        img_files = {}
        for im in soup.find_all("img"):
            src = im.get("src", "")
            if not src or src in img_files or "/images/common/" in src:
                continue
            idx = len(images) + 1
            q = parse_qs(urlparse(src).query)
            fl = unquote_plus(q.get("flNm", [""])[0])
            ext = (Path(fl).suffix or ".jpg").lower()
            rel = f"img/{idx:03d}{ext}"
            url = src if src.startswith("http") else DART_WEB + src
            rec = {"file": rel, "src_url": url, "flNm": fl, "alt": im.get("alt", "")}
            p = d / rel
            if not (p.exists() and is_image(p.read_bytes()[:16])):
                try:
                    img_http.s.headers["Referer"] = n["url"]
                    r = img_http.get(url)
                    if not is_image(r.content[:16]):
                        raise RuntimeError(f"이미지 아님 ({r.headers.get('Content-Type', '')}, {len(r.content)}B)")
                    p.parent.mkdir(exist_ok=True)
                    p.write_bytes(r.content)
                except RuntimeError as e:
                    rec["error"] = str(e)
            if p.exists():
                b = p.read_bytes()
                rec.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
                try:
                    from PIL import Image
                    with Image.open(p) as imo:
                        rec["width"], rec["height"] = imo.size
                except Exception:  # noqa: BLE001
                    pass
            images.append(rec)
            img_files[src] = rel
        t, c = html_to_text(html, img_files)
        has_pdf = has_pdf or bool(PDF_HREF.search(html))
        texts.append(t)
        n_chars += c

    (d / "charter.txt").write_text("".join(texts), encoding="utf-8")
    n_img = len(images)
    ctype = ("mixed" if n_img and n_chars >= MIN_TEXT else "image" if n_img
             else "text" if n_chars >= MIN_TEXT else "pdf" if has_pdf else "empty")   # pdf: 본문이 PDF 링크뿐 → s04c
    meta = {k: doc[k] for k in ("corp_code", "corp_name", "stock_code", "att_title", "att_date", "rcpNo", "dcmNo",
                                "att_url")}
    meta.update(viewer_urls=viewer_urls, n_nodes=len(top), content_type=ctype, text_chars=n_chars,
                n_images=n_img, n_image_errors=sum("error" in i for i in images), images=images,
                folder=d.relative_to(ROOT).as_posix(), fetched_at=now_iso())
    write_json(meta_f, meta)
    return meta


def main(limit: int = 0):
    reports = read_json(INTERIM / "s01_reports.json")
    market = read_json(INTERIM / "s02_market.json")
    main_pages = read_json(INTERIM / "s03_main.json")

    per_row, docs, names = {}, {}, Counter()
    for r in reports:
        if market[r["rcept_no"]]["market"] != "코스피":
            continue
        pg = main_pages.get(r["rcept_no"])
        if pg is None:
            per_row[r["rcept_no"]] = {"charter_status": "main_page_missing"}
            continue
        cands = []
        for i, a in enumerate(pg["att"]):
            a = dict(a, att_order=i, **parse_att_title(a["title"]))
            names[a["att_name"]] += 1
            if is_charter(a["att_name"]):
                cands.append(a)
        if not cands:
            per_row[r["rcept_no"]] = {"charter_status": "no_charter_attachment", "n_att": len(pg["att"])}
            continue
        a = pick(cands)
        code = r["stock_code"] or market[r["rcept_no"]]["kind_code"]
        key = f"{a['rcpNo']}_{a['dcmNo']}"
        docs.setdefault(key, {"corp_code": r["corp_code"], "corp_name": r["corp_name"], "stock_code": code,
                              "att_title": a["title"], "att_date": a["att_date"], "rcpNo": a["rcpNo"],
                              "dcmNo": a["dcmNo"], "att_url": a["url"], "used_by": []})
        docs[key]["used_by"].append(r["rcept_no"])
        per_row[r["rcept_no"]] = {"charter_status": "ok", "doc_key": key, "n_charter_att": len(cands),
                                  "charter_title": a["title"], "charter_url": a["url"]}

    print(f"코스피 행 {len(per_row)} · 정관 문서 {len(docs)}개 · 상태 {dict(Counter(v['charter_status'] for v in per_row.values()))}")
    print("  첨부 이름 상위:", names.most_common(14))
    print("  '정관' 이 들어간 첨부 이름:", sorted({n for n in names if "정관" in n.replace(' ', '')}))

    http, img_http = Http(delay=1.0), Http(delay=0.5)
    metas = {}
    items = sorted(docs.items(), key=lambda kv: kv[1]["stock_code"])
    if limit:
        items = items[:limit]                        # 파일럿
    for i, (key, doc) in enumerate(items, 1):
        try:
            m = fetch_doc(http, img_http, doc)
        except RuntimeError as e:
            print(f"  실패 {key} {doc['corp_name']}: {e}", flush=True)
            continue
        m["used_by_rcept_no"] = doc["used_by"]
        write_json(ROOT / m["folder"] / "meta.json", m)
        metas[key] = m
        if i % 25 == 0:
            print(f"  {i}/{len(docs)} {doc['corp_name']} {m['content_type']} img={m['n_images']}", flush=True)
            write_json(INTERIM / "s04_docs.json", metas)
    write_json(INTERIM / "s04_docs.json", metas)
    write_json(INTERIM / "s04_charter.json", per_row)
    print("정관 원문 종류:", dict(Counter(m["content_type"] for m in metas.values())),
          "· 이미지", sum(m["n_images"] for m in metas.values()), "장 · 이미지 오류",
          sum(m["n_image_errors"] for m in metas.values()))


def repair():
    """받아 둔 이미지 중 이미지가 아닌 파일(HTML 오류 쪽 등)만 다시 받아 meta.json 을 고친다."""
    from PIL import Image

    http = Http(delay=1.0)
    fixed = failed = 0
    for mf in sorted(CHARTER.glob("*/*/meta.json")):
        m = read_json(mf)
        changed = False
        for rec in m.get("images", []):
            p = mf.parent / rec["file"]
            if p.exists() and is_image(p.read_bytes()[:16]):
                continue
            http.s.headers["Referer"] = (m.get("viewer_urls") or [DART_WEB])[0]
            try:
                r = http.get(rec["src_url"])
                if not is_image(r.content[:16]):
                    raise RuntimeError(f"이미지 아님 ({r.headers.get('Content-Type', '')}, {len(r.content)}B)")
                p.write_bytes(r.content)
                rec.pop("error", None)
                rec.update(bytes=len(r.content), sha256=hashlib.sha256(r.content).hexdigest())
                with Image.open(p) as imo:
                    rec["width"], rec["height"] = imo.size
                fixed += 1
            except RuntimeError as e:
                rec["error"] = str(e)                      # 예: DART '이 파일은 서비스 하지 않습니다!' (HTML 안내 쪽)
                if p.exists() and not is_image(p.read_bytes()[:16]):
                    p.unlink()                             # 이미지인 척하는 HTML 은 남기지 않는다
                failed += 1
            changed = True
            print(f"  {m['corp_name']} {rec['file']}: {'고침' if 'error' not in rec else rec['error']}", flush=True)
        if changed:
            m["n_image_errors"] = sum("error" in i for i in m["images"])
            write_json(mf, m)
    print(f"이미지 다시 받기: 고침 {fixed} · 실패 {failed}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 앞 N개 문서만")
    ap.add_argument("--repair", action="store_true", help="받아 둔 이미지 중 깨진 것만 다시 받기")
    a = ap.parse_args()
    repair() if a.repair else main(a.limit)
