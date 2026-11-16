"""s04c PDF 로 첨부된 정관 → PDF 내려받기·글자 뽑기 (글자층이 없으면 글자 인식)

왜: s04 에서 '빈 문서'(content_type=empty)로 나온 정관 31개는 본문이 없고, DART 원문 화면에 PDF 파일 링크만 있다.
    예: CJ대한통운 — <A href='/report/download.do?dcmNo=11128857&flNm=씨제이대한통운_정관.pdf'>.
    정관이 텍스트·스캔 이미지 말고 PDF 로도 온다. 이 PDF 를 받아 글로 바꿔야 정관을 읽고 찾을 수 있다.

무엇을:
 1) 대상 — 정관 폴더의 viewer_*.html 에 download.do …flNm=*.pdf 링크가 있는 문서 (meta.json 이 있는 것만)
 2) 받기 — 링크 순서대로 data/charter/…/pdf/001.pdf … (Referer = viewer 주소, '%PDF' 로 시작하는지 확인)
          DART 웹이므로 _common.Http 의 호스트 단위 분당 80건 상한을 따른다
 3) 글자 — PyMuPDF(fitz)로 쪽마다 글자층을 읽는다. 공백 뺀 글자가 30자 미만인 쪽은 스캔으로 보고
          긴 변 3,000px 로 그려(data/raw/pdf_pages/, git 제외) s04b 와 같은 Windows 내장 OCR·후처리로 읽는다
 4) 정리 — 문서 폴더에
     pdf/001.pdf …     받은 PDF (git 제외 — 웹페이지는 DART 원본 주소로 연다)
     charter_pdf.txt   '[PDF 001: 파일명] → pdf/001.pdf' 아래 쪽마다 '[쪽 N]'(글자 인식한 쪽은 '[쪽 N · OCR]') + 글 줄
     pdf.json          PDF 목록(file·src_url·flNm·bytes·sha256·pages·text_pages·ocr_pages)·글자 수·엔진·만든 때
     meta.json         content_type 을 'pdf' 로 바꾸고 pdfs·n_pdfs 를 더한다 (s04 도 같은 규칙으로 'pdf' 를 낸다)
 5) 다시 돌리면 — pdf.json 이 있고 PDF sha256 이 같으면 건너뛴다 (--force 로 다시)

출력  data/interim/s04c_pdf.json   정관 폴더 → {pdf_txt, total_chars, n_pdfs, pages, ocr_pages}
"""
import argparse
import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote_plus

sys.path.insert(0, str(Path(__file__).parent))
from _common import CHARTER, DART_WEB, INTERIM, RAW, ROOT, Http, now_iso, read_json, write_json  # noqa: E402

PDF_LINK = re.compile(r"""<a\s[^>]*href\s*=\s*['"]([^'"]*download\.do[^'"]*\.pdf)['"]""", re.I)
MIN_TEXT = 30            # 쪽 글자층이 이보다 적으면 스캔 쪽으로 보고 글자 인식


def pdf_links(d: Path) -> list[dict]:
    """viewer_*.html 의 PDF 링크 (원문 순서, 같은 주소는 한 번)."""
    out, seen = [], set()
    for h in sorted(d.glob("viewer_*.html")):
        for href in PDF_LINK.findall(h.read_text(encoding="utf-8")):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            fl = re.search(r"flNm=([^&]+)", href)
            out.append({"src_url": href if href.startswith("http") else DART_WEB + href,
                        "flNm": unquote_plus(fl.group(1)) if fl else ""})
    return out


def extract(pdf: Path, render_dir: Path, ocr_mod) -> tuple[list[dict], dict]:
    """PDF → 쪽 목록 [{n, ocr, lines}] · 요약. 글자층 없는 쪽만 그려서 글자 인식."""
    import fitz

    pages, scanned = [], []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc, 1):
            txt = page.get_text("text") or ""
            lines = [" ".join(x.split()) for x in txt.splitlines() if x.strip()]
            if len(re.sub(r"\s", "", txt)) >= MIN_TEXT:
                pages.append({"n": i, "ocr": False, "lines": lines})
                continue
            z = 3000 / max(page.rect.width, page.rect.height)
            png = render_dir / f"{pdf.stem}_p{i:03d}.png"
            if not png.exists():
                render_dir.mkdir(parents=True, exist_ok=True)
                page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csGRAY).save(png)
            pages.append({"n": i, "ocr": True, "png": png})
            scanned.append(pages[-1])
    if scanned:                                         # s04b 와 같은 OCR·원문자 번호·글자 고침
        res = [ocr_mod.ocr_page(p["png"]) for p in scanned]
        ocr_mod.number_rows(res)
        for p, r in zip(scanned, res):
            p["lines"] = r["lines"]
            p.pop("png")
    return pages, {"pages": len(pages), "text_pages": len(pages) - len(scanned), "ocr_pages": len(scanned)}


def main(force: bool = False, limit: int = 0):
    import fitz

    targets = []
    for mf in sorted(CHARTER.glob("*/*/meta.json")):
        d = mf.parent
        links = pdf_links(d)
        if links:
            targets.append((d, links))
    if limit:
        targets = targets[:limit]
    print(f"PDF 첨부 정관 {len(targets)}개", flush=True)

    ocr_mod = None
    http = Http(delay=1.0, timeout=120)
    index_f = INTERIM / "s04c_pdf.json"
    index = read_json(index_f) if index_f.exists() else {}
    for k, (d, links) in enumerate(targets, 1):
        rel = d.relative_to(ROOT).as_posix()
        meta = read_json(d / "meta.json")
        pj = d / "pdf.json"
        if pj.exists() and not force:
            old = read_json(pj)
            if all((d / p["file"]).exists() and hashlib.sha256((d / p["file"]).read_bytes()).hexdigest() == p["sha256"]
                   for p in old["pdfs"]):
                index[rel] = {"pdf_txt": f"{rel}/charter_pdf.txt", "total_chars": old["total_chars"],
                              "n_pdfs": len(old["pdfs"]), "pages": old["pages"], "ocr_pages": old["ocr_pages"]}
                continue
        pdfs, out_lines, tot = [], [], {"pages": 0, "text_pages": 0, "ocr_pages": 0}
        for i, ln in enumerate(links, 1):
            rec = {"file": f"pdf/{i:03d}.pdf", **ln}
            p = d / rec["file"]
            if not (p.exists() and p.stat().st_size > 0 and p.read_bytes()[:4] == b"%PDF"):
                http.s.headers["Referer"] = (meta.get("viewer_urls") or [DART_WEB])[0]
                try:
                    r = http.get(ln["src_url"])
                    if r.content[:4] != b"%PDF":
                        raise RuntimeError(f"PDF 아님 ({r.headers.get('Content-Type')})")
                    p.parent.mkdir(exist_ok=True)
                    p.write_bytes(r.content)
                except RuntimeError as e:
                    rec["error"] = str(e)
                    pdfs.append(rec)
                    out_lines += [f"[PDF {i:03d}: {ln['flNm']}] → {rec['file']}", f"[받기 실패: {e}]"]
                    continue
            b = p.read_bytes()
            rec.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
            if ocr_mod is None:
                import importlib
                ocr_mod = importlib.import_module("s04b_charter_ocr")
            try:
                pages, summ = extract(p, RAW / "pdf_pages" / d.name, ocr_mod)
            except Exception as e:  # noqa: BLE001 — 깨진 PDF 등
                rec["error"] = f"글자 뽑기 실패: {e}"
                pdfs.append(rec)
                out_lines += [f"[PDF {i:03d}: {ln['flNm']}] → {rec['file']}", f"[글자 뽑기 실패: {e}]"]
                continue
            rec.update(summ)
            for key in tot:
                tot[key] += summ[key]
            pdfs.append(rec)
            out_lines.append(f"[PDF {i:03d}: {ln['flNm']}] → {rec['file']}")
            for pg in pages:
                out_lines.append(f"[쪽 {pg['n']}{' · OCR' if pg['ocr'] else ''}]")
                out_lines += pg["lines"]
        body = "\n".join(out_lines) + "\n"
        (d / "charter_pdf.txt").write_text(body, encoding="utf-8")
        chars = len(re.sub(r"\s", "", "\n".join(x for x in out_lines if not x.startswith("["))))
        info = {"pdfs": pdfs, "total_chars": chars, **tot, "created_at": now_iso(),
                "engine": {"text": f"PyMuPDF {fitz.VersionBind}",
                           "ocr": "Windows.Media.Ocr ko (s04b 와 같은 설정)" if tot["ocr_pages"] else None}}
        write_json(pj, info)
        meta.update(content_type="pdf", pdfs=pdfs, n_pdfs=len(pdfs))
        write_json(d / "meta.json", meta)
        index[rel] = {"pdf_txt": f"{rel}/charter_pdf.txt", "total_chars": chars, "n_pdfs": len(pdfs),
                      "pages": tot["pages"], "ocr_pages": tot["ocr_pages"]}
        print(f"  {k}/{len(targets)} {rel} PDF {len(pdfs)} · 쪽 {tot['pages']} (OCR {tot['ocr_pages']}) · 글자 {chars:,}"
              f"{' · 오류 ' + str(sum('error' in x for x in pdfs)) if any('error' in x for x in pdfs) else ''}", flush=True)
        write_json(index_f, index)
    write_json(index_f, index)
    print(f"PDF 정관 {len(index)}개 · 쪽 {sum(v['pages'] for v in index.values())} "
          f"(OCR {sum(v['ocr_pages'] for v in index.values())}) · 글자 {sum(v['total_chars'] for v in index.values()):,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 앞 N개 문서만")
    a = ap.parse_args()
    main(a.force, a.limit)
