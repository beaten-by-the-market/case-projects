"""s08 웹페이지 데이터 → site/data.js  (화면 틀 site/index.html·app.js·style.css 는 고정)

data/final/*.json 을 읽어 site/data.js 에 `window.DATA = {...};` 한 줄로 쓴다 — file:// 로 열어도 보이게.
표마다 cols(열 이름) + rows(값 배열) 로 담아 키 반복을 없앤다. 없는 파일·열은 건너뛰고 화면은 '수집 중'으로 보인다.

    python -X utf8 scripts/s08_site.py                                  # data/final → site/data.js
    python -X utf8 scripts/s08_site.py --watch 600                      # 10분마다 다시 (수집 중 띄워 두기)
    python -X utf8 scripts/s08_site.py --final-dir D:/fx/data/final --out D:/fx/site/data.js

보기  케이스 폴더에서  python -m http.server 8000  →  http://localhost:8000/site/
      정관 txt·정관의변경.txt 미리보기는 http 로 열어야 된다 (file:// 이면 링크만).

담는 것
  built      생성 시각
  manifest   data/final/manifest.json 그대로 (없으면 null)
  tables     kospi_charter · annual_reports · agm_notices · charter_docs  →  {cols, rows, file, updated}
             kospi_charter·charter_docs 에는 imgs = 스캔 이미지 **전체** [[폴더 기준 파일, DART 원본 주소], …] 를 붙인다 — meta.json 에서.
             화면은 로컬 파일을 먼저 띄우고, 없으면(GitHub Pages — img/ 는 git 제외) DART 원본 주소로 띄운다.
  missing    없는 결과 파일 이름
  local      경로 열이 가리키는 로컬 파일 확인 결과 (있음/없음 건수)
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]

# 알려진 열 순서 (docs/02-데이터사전.md + s07_build). 파일에 더 있는 열은 뒤에 붙인다.
BASE = ["corp_code", "corp_name", "stock_code", "corp_cls", "report_nm", "rcept_no", "flr_nm", "rcept_dt", "rm",
        "rcept_no_new", "fiscal_year", "settle_month", "report_period", "market", "market_basis_date", "sec_group",
        "market_match_by", "amend_tag", "rcept_no_new_status", "dart_url"]
CHARTER = ["charter_status", "charter_title", "charter_att_date", "charter_rcpNo", "charter_dcmNo", "charter_url",
           "charter_viewer_url", "charter_content_type", "charter_text_chars", "charter_n_images", "n_charter_att",
           "charter_dir", "charter_txt", "charter_img_dir", "charter_meta", "charter_ocr_txt", "charter_ocr_chars",
           "charter_pdf_txt", "charter_n_pdfs", "charter_pdf_chars", "charter_llm_txt", "charter_llm_chars",
           "charter_fulltext_txt"]
AGM = ["orig_rcept_no", "orig_rcept_dt", "agm_count", "agm_charter_amend_count", "agm_rcept_nos", "agm_kinds",
       "agm_charter_amend_rcept_nos", "agm_charter_amend_txt", "agm_charter_amend_dart_url", "agm_errors"]
TABLES = {
    "kospi_charter": BASE + CHARTER + AGM,
    "annual_reports": BASE,
    "agm_notices": ["corp_code", "corp_name", "stock_code", "rcept_no", "rcept_dt", "report_nm", "amend_tag",
                    "agm_kind", "has_charter_amend", "detect", "section_chars", "charter_amend_txt", "folder",
                    "main_xml", "dart_url", "error", "used_by_rcept_no"],
    "charter_docs": ["corp_code", "corp_name", "stock_code", "att_title", "att_date", "rcpNo", "dcmNo", "att_url",
                     "content_type", "text_chars", "n_images", "n_image_errors", "n_nodes", "folder",
                     "used_by_rcept_no", "fetched_at"],
}


def clean(v):
    """JSON 에 못 쓰는 값(NaN·inf) → None. 목록·사전은 안쪽까지."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:     # 쓰는 중인 파일 등
        print(f"  읽기 실패 {p.name}: {type(e).__name__} {e}")
        return None


def mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if p.exists() else ""


def img_list(root: Path, folder: str | None, cache: dict) -> list[list[str]] | None:
    """정관 폴더의 meta.json → 스캔 이미지 전체 [[file('img/001.jpg'), src_url(DART 원본)], …] (원문 순서). 없으면 None."""
    if not folder:
        return None
    if folder not in cache:
        m = read_json(root / folder / "meta.json")
        imgs = None
        if isinstance(m, dict) and isinstance(m.get("images"), list):
            imgs = [[str(i.get("file")), str(i.get("src_url") or "")] for i in m["images"]
                    if isinstance(i, dict) and i.get("file")]
        cache[folder] = imgs or None
    return cache[folder]


def pdf_list(root: Path, folder: str | None, cache: dict) -> list[list[str]] | None:
    """정관 폴더의 meta.json → PDF 첨부 [[file('pdf/001.pdf'), src_url(DART 원본), 원래 파일 이름], …]. 없으면 None."""
    if not folder:
        return None
    if folder not in cache:
        m = read_json(root / folder / "meta.json")
        out = None
        if isinstance(m, dict) and isinstance(m.get("pdfs"), list):
            out = [[str(p.get("file")), str(p.get("src_url") or ""), str(p.get("flNm") or "")] for p in m["pdfs"]
                   if isinstance(p, dict) and p.get("file")]
        cache[folder] = out or None
    return cache[folder]


def pack(rows: list[dict], known: list[str]) -> dict:
    """레코드 배열 → {cols, rows}. 알려진 열 중 파일에 있는 것 + 파일에만 있는 열."""
    seen = {}
    for r in rows:
        for k in r:
            seen.setdefault(k, None)
    cols = [c for c in known if c in seen] + [c for c in seen if c not in known]
    return {"cols": cols, "rows": [[clean(r.get(c)) for c in cols] for r in rows]}


def build(final: Path, root: Path, out: Path) -> None:
    t0 = time.time()
    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "manifest": None, "tables": {}, "missing": [],
            "local": {}}
    m = read_json(final / "manifest.json")
    if isinstance(m, dict):
        data["manifest"] = clean(m)
    else:
        data["missing"].append("manifest.json")

    cache: dict = {}
    pcache: dict = {}
    for name, known in TABLES.items():
        f = final / f"{name}.json"
        rows = read_json(f)
        if not isinstance(rows, list):
            data["missing"].append(f.name)
            continue
        rows = [r for r in rows if isinstance(r, dict)]
        if name == "kospi_charter":
            for r in rows:
                if r.get("charter_img_dir") or (r.get("charter_n_images") or 0) > 0:
                    r["imgs"] = img_list(root, r.get("charter_dir"), cache)
                if r.get("charter_pdf_txt"):
                    r["pdfs"] = pdf_list(root, r.get("charter_dir"), pcache)
        elif name == "charter_docs":
            for r in rows:
                if (r.get("n_images") or 0) > 0:
                    r["imgs"] = img_list(root, r.get("folder"), cache)
                if r.get("content_type") == "pdf":
                    r["pdfs"] = pdf_list(root, r.get("folder"), pcache)
        t = pack(rows, known + ["imgs", "pdfs"])
        t.update(file=f.name, updated=mtime(f))
        data["tables"][name] = t

    # 경로 열이 가리키는 파일이 이 컴퓨터에 있는지 (화면에는 건수만; 링크는 어차피 '../' + 경로)
    def count(name, col):
        t = data["tables"].get(name)
        if not t or col not in t["cols"]:
            return None
        i = t["cols"].index(col)
        paths = [p for r in t["rows"] for p in (r[i] if isinstance(r[i], list) else [r[i]]) if p]
        have = sum((root / p).exists() for p in paths)
        return {"paths": len(paths), "exists": have}

    for name, col in (("kospi_charter", "charter_txt"), ("kospi_charter", "charter_img_dir"),
                      ("kospi_charter", "agm_charter_amend_txt"), ("agm_notices", "charter_amend_txt")):
        c = count(name, col)
        if c:
            data["local"][f"{name}.{col}"] = c

    out.parent.mkdir(parents=True, exist_ok=True)
    js = "window.DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str) + ";\n"
    out.write_text(js, encoding="utf-8")
    sizes = " · ".join(f"{k} {len(v['rows']):,}행" for k, v in data["tables"].items())
    print(f"{out} {len(js.encode('utf-8')) / 1e6:.2f}MB · {sizes or '표 없음'} · {time.time() - t0:.1f}초")
    if data["missing"]:
        print("  없는 파일:", ", ".join(data["missing"]))
    for k, v in data["local"].items():
        print(f"  로컬 파일 {k}: {v['exists']:,}/{v['paths']:,} 있음")


def main():
    ap = argparse.ArgumentParser(description="data/final/*.json → site/data.js")
    ap.add_argument("--final-dir", type=Path, default=CASE / "data" / "final", help="결과 JSON 폴더 (기본 data/final)")
    ap.add_argument("--root", type=Path, default=None,
                    help="경로 열의 기준 폴더 (기본: final-dir 이 …/data/final 이면 그 두 단계 위, 아니면 케이스 폴더)")
    ap.add_argument("--out", type=Path, default=CASE / "site" / "data.js", help="출력 (기본 site/data.js)")
    ap.add_argument("--watch", type=int, default=0, help="초. 0 이면 한 번만")
    a = ap.parse_args()
    final = a.final_dir.resolve()
    root = (a.root or (final.parents[1] if final.parent.name == "data" else CASE)).resolve()
    while True:
        try:
            build(final, root, a.out.resolve())
        except Exception as e:  # noqa: BLE001 — 수집 중 파일이 쓰이는 순간 등: 다음 주기에 다시
            if not a.watch:
                raise
            print("빌드 실패:", type(e).__name__, e)
        if not a.watch:
            break
        time.sleep(a.watch)


if __name__ == "__main__":
    main()
