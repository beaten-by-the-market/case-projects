"""notebooks/00_master.ipynb 를 만든다 (셀 내용은 여기서만 고친다).

    python scripts/make_notebook.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/00_master.ipynb   # 실행 결과까지 저장
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md("""# kospi-charter 마스터 노트북 — 최근 1년 사업보고서 목록 + 코스피 정관 원문

이 노트북 하나를 위에서 아래로 실행하면 결과물 전체가 다시 만들어진다. 각 단계는 `scripts/sNN_*.py` 의 `main()` 을 부른다
(터미널에서 `python scripts/s01_list.py` … 로 돌려도 결과는 같다).

| 단계 | 하는 일 | 출처 |
|---|---|---|
| s01 | 최근 1년 사업보고서 목록, **최종보고서만** (`final=True` = `last_reprt_at=Y`) | OpenDART `list.json` (A001) |
| s02 | 소속시장 — **기준일 현재 상장사 목록 한 번** | KIND 상장종목현황 |
| s03 | `[첨부정정]` 행의 `rcept_no_new` + 코스피 행의 첨부문서 목록 | DART `main.do` (`family`·`att` 선택상자) |
| s04 | 코스피 행의 정관 원문(텍스트·스캔 이미지) 내려받기·정리 | DART `viewer.do`·`download.do` |
| s04b | 스캔 이미지 정관 글자 인식(OCR) → `charter_ocr.txt` | Windows 내장 OCR (네트워크 없음) |
| s04c | PDF 로 첨부된 정관 → PDF 받기·글자 뽑기 → `charter_pdf.txt` | DART `download.do` · PyMuPDF |
| s05 | 코스피 행마다 원본 제출일 ~ 기준일 주주총회소집공고(최종본) 목록 | OpenDART `list.json` (E006) |
| s06 | 소집공고 XML 원문 저장 → '정관의 변경' 절 찾기·txt 저장 | OpenDART `document.xml` |
| s07 | 결과물(JSON·CSV·XLSX) 만들기 | — |
| s08 | 웹페이지 데이터 `site/data.js` | — |

**재현성.** 기준일 `AS_OF` 를 고정한다(아래 설정 셀). 원본 응답(목록 페이지·KIND 목록·DART 화면·원문 HTML)은 모두
`data/raw/`·`data/charter/` 에 저장되고, 다시 실행하면 저장된 것을 읽는다. 처음부터 다시 받으려면 `data/raw` 를 지운다.
DART 는 IP 단위로 막으므로 **다른 DART 수집과 동시에 돌리지 않는다** (요청 간격 1초).
"""),
    md("## 0. 환경"),
    code("""# 처음 한 번 (Colab 등 새 환경):
# !pip install -r ../requirements.txt
import os, sys, json
from pathlib import Path

ROOT = Path.cwd().resolve()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("KC_AS_OF", "2026-11-16")   # 기준일 — 바꾸면 data/raw 를 지우고 다시 받는다
import pandas as pd
pd.set_option("display.max_columns", 40); pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 60)

import _common as C
print("ROOT", ROOT)
print("기준일", C.AS_OF, "· 조회기간", C.BGN, "~", C.AS_OF)
print("DART 키", len(C.dart_keys()), "개 (.env 또는 환경변수 DART_API_KEY*)")"""),

    md("""## 1. 사업보고서 목록 (s01)

* `pblntf_detail_ty=A001`, `last_reprt_at=Y` — 보고서마다 **최종본 한 줄**
* 회사를 지정하지 않으면 검색기간이 3개월로 묶여 있어 3개월 이하 구간으로 나눠 부른다
* A001 안의 `사업보고서제출기한연장신고서` 는 뺀다
* 한 회사가 기간 안에 여러 번 냈으면 **가장 최근 것 하나만** — 결산기(`report_period`)가 가장 늦은 것, 같으면 접수번호가 늦은 것
  (뺀 행: `logs/s01_dropped_older.csv`)
* **사업연도**(`fiscal_year`)·**결산월**(`settle_month`)은 보고서명 `(YYYY.MM)` 에서 읽는다.
  사업연도는 OpenDART 정기보고서 API 의 `bsns_year` 와 같은 규칙(결산기 말일이 속한 연도)이다 — `docs/03-검증기록.md`"""),
    code("""import s01_list
reports = pd.DataFrame(s01_list.main())
reports.head(3)"""),
    code("""print(reports["amend_tag"].replace("", "(없음)").value_counts().to_string())
print(pd.crosstab(reports["fiscal_year"], reports["settle_month"]))"""),

    md("""## 2. 소속시장 (s02) — KIND 기준일 현재 목록 한 번

KIND 상장종목현황에서 기준일 현재 상장사 목록을 한 번 받아(유가·코스닥·코넥스, 주권·외국주권·리츠·투자회사·스팩·DR)
종목코드(없으면 회사명)로 맞춘다. 목록에 없으면 `기타`.

> **한계** — 제출 당시가 아니라 **기준일 현재** 시장이다. 제출 뒤 상장폐지·이전상장·신규상장된 회사는 현재 시장으로 분류된다
> (예: 한창 005110 은 2026-03-26 제출 때 유가증권시장 상장사였지만 지금은 `기타`). OpenDART `corp_cls` 도 현재 기준이라 두 값은 같다."""),
    code("""import s02_market
market = s02_market.main()
pd.Series({k: v["market"] for k, v in market.items()}).value_counts()"""),

    md("""## 3. `rcept_no_new`·첨부문서 목록 (s03)

`[첨부정정]` 은 첨부서류만 바꾼 공시라 접수번호는 새로 받지만 본문이 없다. 기존 프로젝트(`get_recent`) 규칙 그대로
DART `main.do` 의 `<select id="family">`(+본문선택+) **첫 옵션 = 가장 최근 본문**의 접수번호를 `rcept_no_new` 로 넣는다.
다른 행은 `rcept_no_new = rcept_no`.

* `family`·`att` 는 보고서 가족 전체의 **현재** 목록이다. 첨부정정 뒤에 기재정정이 또 나왔으면 첫 옵션은 그 뒤 본문이다
  (`rcept_no_new_status` 에 `_after_amend` 표시).
* `[첨부추가]` 는 새 접수번호를 받지 않는다(원 공시 이름만 바뀐다) → 대상이 아니다.
* 같은 화면의 `<select id="att">` 가 OpenDartReader `attach_docs()` 가 읽는 첨부문서 목록이다."""),
    code("""import s03_dart_main
s03_dart_main.main()
pages = C.read_json(C.INTERIM / "s03_main.json")
ac = reports[reports["amend_tag"].str.contains("첨부정정", regex=False)].copy()
ac["rcept_no_new"] = ac["rcept_no"].map(lambda r: pages[r]["rcept_no_new"])
ac["status"] = ac["rcept_no"].map(lambda r: pages[r]["new_status"] + ("_after_amend" if pages[r]["new_after_amend"] else ""))
ac["family"] = ac["rcept_no"].map(lambda r: " / ".join(f["rcpNo"] + " " + f["title"] for f in pages[r]["family"]))
print(ac["status"].value_counts().to_string())
ac[["corp_name", "report_nm", "rcept_no", "rcept_no_new", "status", "family"]].head(15)"""),

    md("""## 4. 정관 원문 (s04)

코스피 행마다 첨부문서 목록에서 제목이 `정관` 인 것을 고른다(여럿이면 가장 늦은 날짜, 같은 날이면 `[정정]`).
정관 문서(`dcmNo`)마다 한 번만 받는다 — 같은 보고서의 정정본들은 같은 정관을 가리킨다.

```
data/charter/{종목코드}_{회사명}/{첨부일자}_{dcmNo}/
    viewer_01.html   DART 원문 HTML 그대로
    charter.txt      본문 텍스트 (이미지 자리: '[이미지 001: 캡션] → img/001.jpg')
    img/001.jpg …    스캔 이미지 (원래 순서)
    meta.json        출처 URL·종류(text/image/mixed/empty)·글자 수·이미지 목록(크기·sha256)·이 정관을 쓰는 접수번호
```
처음 실행은 오래 걸린다(문서·이미지마다 요청). 다시 실행하면 이미 받은 폴더는 건너뛴다."""),
    code("""import s04_charter
s04_charter.main()
docs = pd.DataFrame(C.read_json(C.INTERIM / "s04_docs.json").values())
print(docs["content_type"].value_counts().to_string())
docs[["corp_name", "att_title", "content_type", "text_chars", "n_images", "folder"]].head(10)"""),
    code("""# 텍스트형 하나, 이미지형 하나 보기
from IPython.display import Image, display
t = docs[docs.content_type == "text"].iloc[0]
print(t.corp_name, t.folder); print((ROOT / t.folder / "charter.txt").read_text(encoding="utf-8")[:600])
im = docs[docs.content_type == "image"]
if len(im):
    x = im.iloc[0]; print(x.corp_name, x.folder)
    print((ROOT / x.folder / "charter.txt").read_text(encoding="utf-8")[:300])
    first = ROOT / x.folder / x.images[0]["file"]
    if first.exists():
        display(Image(filename=str(first), width=360))"""),

    md("""## 4b. 스캔 정관 글자 인식 (s04b)

`content_type` 이 `image`·`mixed` 인 정관을 Windows 내장 OCR(`ko`)로 읽어 같은 폴더에 `charter_ocr.txt`·`ocr.json` 을 만든다.
Windows 에서만 되고 네트워크는 쓰지 않는다. 이미지 sha256 이 같으면 다시 하지 않는다(`--force` 로 다시). 품질은 docs/01 R5-7."""),
    code("""import subprocess
r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "s04b_charter_ocr.py")], capture_output=True, text=True, encoding="utf-8")
print(r.stdout[-1200:] or r.stderr[-1200:])
ocr = C.read_json(C.INTERIM / "s04b_ocr.json")
print("글자 인식 문서", len(ocr), "· 장", sum(v["pages"] for v in ocr.values()), "· 글자", sum(v["total_chars"] for v in ocr.values()))"""),

    md("""## 4c. PDF 로 첨부된 정관 (s04c)

원문 화면이 PDF 링크뿐인 정관(처음에는 '빈 문서'로 나온 31개)의 PDF 를 받아(DART 웹) PyMuPDF 로 글자층을 뽑는다.
글자층이 없는 쪽만 s04b 와 같은 글자 인식을 한다 → `charter_pdf.txt`·`pdf.json`. 규칙은 docs/01 R5-8."""),
    code("""import s04c_charter_pdf
s04c_charter_pdf.main()
pdfi = C.read_json(C.INTERIM / "s04c_pdf.json")
print("PDF 정관", len(pdfi), "· 쪽", sum(v["pages"] for v in pdfi.values()), "(글자 인식", sum(v["ocr_pages"] for v in pdfi.values()), ") · 글자", sum(v["total_chars"] for v in pdfi.values()))"""),

    md("""## 5. 주주총회 소집공고 목록 (s05)

코스피 행마다 **사업보고서 원본 최초 접수일 ~ 기준일**에 **접수된** 주주총회소집공고 최종본(`E006`, `last_reprt_at=Y`)을 센다.
* 원본 최초 접수일 = 목록 행이 정정본이면 DART `family` 의 가장 오래된 본문 접수번호의 날짜 (s03 화면)
* 시장 전체 목록을 3개월 구간으로 한 번에 받고 코스피 회사만 거른다

> 보통 소집공고(주총 2주 전)가 사업보고서(주총 1주 전)보다 먼저 접수되므로, 사업보고서 직후 열리는 정기주총은 이 셈에 들어가지 않을 수 있다.
> 사용자 결정(2026-11-16)으로 **소집공고 접수일 기준**을 쓴다."""),
    code("""import s05_agm_list
s05_agm_list.main()
amap = C.read_json(C.INTERIM / "s05_agm_map.json")
pd.Series({k: len(v["notices"]) for k, v in amap.items()}).value_counts().sort_index()"""),

    md("""## 6. 소집공고 XML 원문 → '정관의 변경' 절 (s06)

* 원문: OpenDART `document.xml` ZIP 을 풀어 `data/agm/{종목코드}_{회사명}/{접수일}_{rcept_no}/` 에 그대로 저장
* 찾기: `III. 경영참고사항 › 2. 주주총회 목적사항별 기재사항` 의 안건유형 절 제목 `TITLE@AASSOCNOTE="L0-0-2-2-0"`
  (증권발행공시규정 제3-15조③ 2호 '정관의 변경' — `agm-comparison` 케이스에서 20개 호 전부 실물 확인). 코드가 없으면 '목적사항별 기재사항' 뒤 제목 글자로 찾는다
* 절 = 그 제목의 부모 SECTION 전체 → 같은 폴더 `정관의변경.txt` (표는 행마다 ` | `)"""),
    code("""import s06_agm_xml
s06_agm_xml.main()
adocs = pd.DataFrame(C.read_json(C.INTERIM / "s06_agm_docs.json").values())
print(adocs.get("detect", pd.Series(dtype=str)).fillna("-").replace("", "-").value_counts().to_string())
x = adocs[adocs.get("has_charter_amend", False) == True].head(1)
if len(x):
    print(x.iloc[0].corp_name, x.iloc[0].charter_amend_txt)
    print((ROOT / x.iloc[0].charter_amend_txt).read_text(encoding="utf-8")[:800])"""),

    md("## 7. 결과물 (s07)"),
    code("""import s07_build
s07_build.main()
final = pd.read_json(C.FINAL / "annual_reports.json", dtype=False)
kc = pd.read_json(C.FINAL / "kospi_charter.json", dtype=False)
print(final.shape, kc.shape)
kc[["corp_name", "report_nm", "rcept_no", "rcept_no_new", "fiscal_year", "settle_month", "market",
    "charter_title", "charter_content_type", "charter_txt", "orig_rcept_dt", "agm_count", "agm_charter_amend_count",
    "agm_charter_amend_txt"]].head(10)"""),
    code("""json.loads((C.FINAL / "manifest.json").read_text(encoding="utf-8"))["counts"]"""),

    md("## 8. 검증"),
    code("""# (1) 목록 — 최종본·중복·접두어
assert final["rcept_no"].is_unique
assert final["report_nm"].str.contains(r"사업보고서 \\(\\d{4}\\.\\d{2}\\)$").all()
assert (final.loc[~final.amend_tag.str.contains("첨부정정", regex=False), "rcept_no_new"]
        == final.loc[~final.amend_tag.str.contains("첨부정정", regex=False), "rcept_no"]).all()
# (2) 첨부정정 — rcept_no_new 는 family 목록 안의 본문이고 원 접수번호와 다르다
for r in ac.itertuples():
    fam = [f["rcpNo"] for f in pages[r.rcept_no]["family"]]
    assert r.rcept_no_new in fam and r.rcept_no_new != r.rcept_no, r
# (3) 코스피 행 수 = s02 코스피 수, 링크 파일이 실제로 있다
assert len(kc) == (final.market == "코스피").sum()
ok = kc[kc.charter_status == "ok"]
missing = [p for col in ("charter_txt", "charter_meta") for p in ok[col].dropna() if not (ROOT / p).exists()]
print("코스피", len(kc), "· 정관 ok", len(ok), "· 없는 링크", len(missing)); assert not missing
# (4) 이미지 — meta 의 개수·sha256 이 디스크 파일과 같다
import hashlib
bad = unserved = 0
for d in C.read_json(C.INTERIM / "s04_docs.json").values():
    for im in d["images"]:
        if "error" in im:                       # DART 가 서비스하지 않는 이미지 등 — meta 에 이유가 남아 있다
            unserved += 1
            continue
        p = ROOT / d["folder"] / im["file"]
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != im.get("sha256"):
            bad += 1
print("이미지 불일치", bad, "· 받지 못한 이미지(이유 기록)", unserved)
assert bad == 0
print(kc.charter_status.value_counts().to_string())
# (5) 회사별 1건
assert final["corp_code"].is_unique
# (6) 주총 — 정관변경 수 ≤ 주총 수, 소집공고 접수일이 기간 안, txt 가 실제로 있다
notices = pd.read_json(C.FINAL / "agm_notices.json", dtype=False)
dt = dict(zip(notices.rcept_no, notices.rcept_dt))
for r in kc.itertuples():
    assert r.agm_charter_amend_count <= r.agm_count == len(r.agm_rcept_nos)
    assert all(r.orig_rcept_dt <= dt[n] <= C.AS_OF.strftime("%Y%m%d") for n in r.agm_rcept_nos), r.rcept_no
    assert all((ROOT / p).exists() for p in r.agm_charter_amend_txt), r.rcept_no
print("소집공고", len(notices), "· 정관변경 포함", int(notices.has_charter_amend.fillna(False).sum()),
      "· 원문 오류", int(notices.error.notna().sum()))"""),
    code("""# (7) attach_docs() 대조 — 이 파이프라인의 첨부문서 파서가 OpenDartReader.attach_docs() 와 같은 목록을 내는지
#     DART 에 직접 요청하므로 기본은 끈다. 확인할 때만 True.
RUN_LIVE_CHECK = False
if RUN_LIVE_CHECK:
    try:
        from opendartreader import OpenDartReader       # 0.3.x
    except ImportError:
        import OpenDartReader                           # 0.2.x (모듈 자체가 클래스)
    dart = OpenDartReader(C.dart_keys()[0])
    sample = list(ok.sample(3, random_state=0).rcept_no) + list(ac.rcept_no[:2])
    for rno in sample:
        lib = dart.attach_docs(rno)
        lib_rows = [(t, u.replace("http://", "https://")) for t, u in zip(lib.title, lib.url)]
        mine = [(a["title"], a["url"]) for a in pages[rno]["att"]]
        print(rno, "일치" if lib_rows == mine else "불일치", len(lib_rows))"""),

    md("""## 9. 웹페이지 (s08)

`site/index.html` 은 고정 틀이고 `scripts/s08_site.py` 가 `data/final` 로 `site/data.js` 를 만든다.
본문 미리보기(정관 txt·정관의변경 txt)는 `fetch` 로 읽으므로 케이스 폴더에서 `python -m http.server` 를 띄우고
`http://localhost:8000/site/` 로 연다 (file:// 로 열면 표는 보이고 미리보기 대신 링크가 나온다)."""),
    code("""import subprocess
if (ROOT / "scripts" / "s08_site.py").exists():
    print(subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "s08_site.py")],
                         capture_output=True, text=True, encoding="utf-8").stdout[-800:])"""),

    md("""## 10. 다시 만들기·갱신

* **같은 기준일로 재현**: 이 노트북을 그대로 실행 (캐시를 읽는다).
* **기준일을 옮겨 새로 받기**: 0번 셀의 `KC_AS_OF` 를 바꾸고 `data/raw/`·`data/interim/`·`data/charter/` 를 지운 뒤 실행.
  DART 화면의 `family`·`att` 는 수집시점 기준이다(`s03_main.json` 의 `fetched_at`, 범위는 `manifest.json` 의 `fetched`).
* 스캔 이미지는 git 에 올리지 않는다(`.gitignore`). `meta.json` 의 `src_url` 로 다시 받을 수 있고 `sha256` 으로 같은 파일인지 확인한다.
"""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}})
out = ROOT / "notebooks" / "00_master.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print("wrote", out)
