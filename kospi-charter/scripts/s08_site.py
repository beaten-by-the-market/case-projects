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
  manifest_kosdaq  data/final/kosdaq_manifest.json 그대로 (없으면 null) — kind_kosdaq·fetched·counts
  check_group      data/interim/s02e_check_group.json 의 {종목코드: 확인그룹} (코스피만, 없으면 {})
  tables     kospi_charter · annual_reports · agm_notices · charter_docs · kospi_absent  →  {cols, rows, file, updated}
             kosdaq_charter · kosdaq_agm_notices · kosdaq_charter_docs · kosdaq_absent  (코스닥, s07k — 표 이름 = 결과 파일 이름.
             코스피 표와 섞지 않고 따로 넣는다. 사업보고서 표와 rcept_no 로 합치는 것은 app.js 가 한다)
             kospi_absent = KIND 코스피 상장사 중 사업보고서가 없어 목록에 없는 회사와 근거 (s02b → s07), kosdaq_absent 는 s02c → s07k
             absent_charter = 그중 신규상장·투자회사의 정관을 증권신고서·분할공시·KIND·홈페이지에서 찾은 것 (s04e → s07e, 두 시장 함께)
             kospi_charter·charter_docs (코스닥 짝도) 에는 imgs = 스캔 이미지 **전체** [[폴더 기준 파일, DART 원본 주소], …] 를 붙인다 — meta.json 에서.
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
    "kospi_absent": ["stock_code", "corp_name", "sec_group", "listed_date", "corp_code", "acc_mt", "reason_code", "reason",
                     "n_annual_reports_all", "n_annual_reports_window", "last_annual_report_dt", "last_annual_report_nm",
                     "first_fy_end", "first_report_due", "n_filings_window", "filing_forms_window", "last_filing_dt",
                     "last_filing_nm", "last_filing_rcept_no", "kind_n_disclosures_window", "kind_misc_n",
                     "kind_misc_groups", "kind_misc_kinds", "kind_misc_items", "dart_url"],
}
# 코스닥 (s07k) — 열은 코스피 짝과 같다. kosdaq_absent 만 corp_code_match_by·kind_titles_window 두 열이 더 있다
TABLES.update({
    "kosdaq_charter": TABLES["kospi_charter"],
    "kosdaq_agm_notices": TABLES["agm_notices"],
    "kosdaq_charter_docs": TABLES["charter_docs"],
    "kosdaq_absent": TABLES["kospi_absent"][:-1] + ["corp_code_match_by", "kind_titles_window", "dart_url"],
})
# 사업보고서가 없어 목록에 없는 회사의 정관 (s04e → s07e) — 1행 = 회사, 근거문서(증권신고서 등) 열 + 정관·주총 열
TABLES["absent_charter"] = (["market", "stock_code", "corp_name", "corp_code", "sec_group", "listed_date", "settle_month",
                             "reason_code", "reason", "charter_source_doc", "charter_source_rcept_no", "charter_source_nm",
                             "charter_source_dt", "charter_source_url"] + CHARTER + AGM)
CHARTER_ROWS = ("kospi_charter", "kosdaq_charter", "absent_charter")   # 정관 열이 있는 행 → imgs·pdfs 를 charter_dir 기준으로
DOC_ROWS = ("charter_docs", "kosdaq_charter_docs")      # 행 = 정관 문서 1건 → imgs·pdfs 를 folder 기준으로


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
    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "manifest": None, "manifest_kosdaq": None,
            "tables": {}, "missing": [], "local": {}}
    for key, fname in (("manifest", "manifest.json"), ("manifest_kosdaq", "kosdaq_manifest.json")):
        m = read_json(final / fname)
        if isinstance(m, dict):
            data[key] = clean(m)
        else:
            data["missing"].append(fname)
    # 확인그룹 (s02e, 사용자가 준 엑셀의 코스피 종목별 그룹 번호): 웹페이지 각 탭의 '확인그룹' 칸. 없으면 비워 둔다
    cg = read_json(root / "data" / "interim" / "s02e_check_group.json") if (root / "data" / "interim" / "s02e_check_group.json").exists() else None
    data["check_group"] = (cg or {}).get("check_group") or {}

    cache: dict = {}
    pcache: dict = {}
    for name, known in TABLES.items():
        f = final / f"{name}.json"
        rows = read_json(f)
        if not isinstance(rows, list):
            data["missing"].append(f.name)
            continue
        rows = [r for r in rows if isinstance(r, dict)]
        if name in CHARTER_ROWS:
            for r in rows:
                if r.get("charter_img_dir") or (r.get("charter_n_images") or 0) > 0:
                    r["imgs"] = img_list(root, r.get("charter_dir"), cache)
                if r.get("charter_pdf_txt"):
                    r["pdfs"] = pdf_list(root, r.get("charter_dir"), pcache)
        elif name in DOC_ROWS:
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
                      ("kospi_charter", "agm_charter_amend_txt"), ("agm_notices", "charter_amend_txt"),
                      ("kosdaq_charter", "charter_txt"), ("kosdaq_charter", "charter_img_dir"),
                      ("kosdaq_charter", "charter_fulltext_txt"), ("kosdaq_charter", "agm_charter_amend_txt"),
                      ("kosdaq_agm_notices", "charter_amend_txt"),
                      ("absent_charter", "charter_txt"), ("absent_charter", "charter_fulltext_txt"),
                      ("absent_charter", "agm_charter_amend_txt")):
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
