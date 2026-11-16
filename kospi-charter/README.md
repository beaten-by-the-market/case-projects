# kospi-charter — 최근 1년 사업보고서 목록 + 코스피 정관 원문

## 한 줄 요약

OpenDART 에서 **최근 1년(2025-11-16 ~ 2026-11-16) 사업보고서 최종본 목록**을 JSON 으로 받아 **회사마다 가장 최근 1건**만 남기고,
`[첨부정정]` 은 본문 접수번호(`rcept_no_new`)를, 모든 행에 사업연도·결산월·소속시장을 붙였다.
그중 **코스피 기업** 행마다 첨부문서 목록(OpenDartReader `attach_docs()` 와 같은 목록)에서 **정관 URL** 을 찾아 넣고,
정관 원문(텍스트 또는 스캔 이미지)을 회사·문서별 폴더에 내려받아 그 위치를 목록에 링크로 달았다.
이어서 사업보고서 원본 제출일부터 기준일까지 접수된 **주주총회소집공고**(최종본)의 XML 원문을 모두 저장하고,
'2. 주주총회 목적사항별 기재사항'에 **정관의 변경** 절이 있는 공고를 세어 그 절 텍스트를 txt 로 따로 저장해 링크했다.
결과는 data.krx.co.kr 디자인을 빌린 정적 웹페이지(`site/`)로 본다.

| 결과 (기준일 2026-11-16) | 값 |
|---|---|
| 사업보고서 최종본, 회사별 1건 | **3,349사** — 코스피 825 · 코스닥 1,784 · 코넥스 107 · 기타 633 |
| `[첨부정정]` → `rcept_no_new` | 86건 |
| 코스피 정관 원문 | **825/825** — 텍스트 629 · 스캔 이미지 164(글자 인식) · PDF 31 · 혼합 1 |
| 원본 제출일 이후 소집공고 | **247건**, 그중 '정관의 변경' 절 **146건** (해당 회사 134사) |

자세한 건수와 확인한 사실은 [docs/03-검증기록.md](docs/03-검증기록.md), `data/final/manifest.json`.

## 결과물

| 파일 | 내용 |
|---|---|
| [`data/final/annual_reports.json`](data/final/annual_reports.json) · `.csv` | 사업보고서 최종본 전체. API 열 + `rcept_no_new`·`fiscal_year`·`settle_month`·`market` … |
| [`data/final/kospi_charter.json`](data/final/kospi_charter.json) · `.csv` · `.xlsx` | 코스피 행 + `charter_url`(정관 URL)·`charter_content_type`·`charter_txt`·`charter_img_dir` … |
| [`data/final/charter_docs.csv`](data/final/charter_docs.csv) | 내려받은 정관 문서 색인 |
| [`data/final/agm_notices.csv`](data/final/agm_notices.csv) | 주주총회소집공고 색인 — 정관의 변경 절 유무·`정관의변경.txt` 위치 |
| [`data/agm/`](data/agm/) | 소집공고 원문 — `{종목코드}_{회사명}/{접수일}_{rcept_no}/` 아래 XML·`정관의변경.txt`·`meta.json` |
| [`site/`](site/) | 웹페이지 (`index.html` + `data.js`) |
| [`data/charter/`](data/charter/) | 정관 원문 — `{종목코드}_{회사명}/{첨부일자}_{dcmNo}/` 아래 `charter.txt`·`img/`·`meta.json`·`viewer_01.html` |
| [`data/final/manifest.json`](data/final/manifest.json) | 기준일·조회기간·출처·건수 |

열 설명은 [docs/02-데이터사전.md](docs/02-데이터사전.md). 폴더·열 이름의 `charter` 는 정관(영문 정식 명칭 Articles of Incorporation)을 가리키는 식별자다.

## 규칙 (자세히는 [docs/01-수집사양.md](docs/01-수집사양.md))

| | 규칙 |
|---|---|
| 목록 | OpenDART `list.json`, `A001`, **`last_reprt_at=Y`(최종본만 = `final=True`)**, 3개월 구간으로 나눠 호출. `사업보고서제출기한연장신고서` 제외. **회사별 가장 최근 1건**(결산기가 가장 늦은 것) |
| `rcept_no_new` | **최종본이 `[첨부정정]` 인 행만** DART `main.do` 의 `<select id="family">` 첫 옵션(최근 본문) 접수번호. 나머지는 `rcept_no` 그대로 (기존 `get_recent()` 규칙) |
| 사업연도·결산월 | 보고서명 `(YYYY.MM)`. 사업연도 = OpenDART `bsns_year` 규칙(결산기 말 연도) |
| 소속시장 | **KIND 기준일 현재 상장 목록을 한 번** 받아 종목코드(없으면 회사명)로 맞춘다 |
| 정관 | `main.do` 의 `<select id="att">`(= `attach_docs()`) 에서 제목이 `정관` 인 첨부 → 첨부 `main.do` → `viewer.do` 원문 → `<img>` 는 `download.do` 로 내려받기 |
| 주총 | 기간 = [사업보고서 **원본 최초 접수일**, 기준일]. 그 안에 **접수된** 소집공고 최종본(`E006`) 수 = `agm_count`. 공고마다 `document.xml` 원문 저장, 안건유형 절 `TITLE@AASSOCNOTE="L0-0-2-2-0"`(정관의 변경)이 있으면 `agm_charter_amend_count` 에 세고 절 텍스트를 `정관의변경.txt` 로 |

## 한계

* **소속시장은 제출 당시가 아니라 기준일 현재다** (사용자 결정 2026-11-16). 제출 뒤 상장폐지·이전상장·신규상장된 회사는 현재 시장으로 분류된다.
  OpenDART `corp_cls` 도 현재 기준이라 `market` 과 같다 (예: 한창 005110 — 2026-03 제출 때 유가 상장사, 지금 `기타`).
* DART 화면의 `family`·`att` 는 **수집시점(2026-11-16 11:51 ~ 12:10) 기준**이다(`s03_main.json` 의 `fetched_at`, `manifest.json` 의 `fetched`). 그 뒤 정정공시가 나오면 바뀐다.
* **주총은 소집공고 접수일로 센다** (사용자 결정). 소집공고(주총 2주 전)가 사업보고서(주총 1주 전)보다 먼저 나오므로,
  사업보고서 직후 열리는 정기주총은 대개 `agm_count` 에 들어가지 않는다.
* 스캔 이미지 정관(`charter_content_type=image`)은 Windows 내장 OCR 로 글자를 옮긴 `charter_ocr.txt` 를 함께 둔다(`charter_ocr_txt`).
  기계 인식이라 틀린 글자가 있다 — 선명한 장은 약 99%, 작은 스캔은 80~93% (docs/01 R5-7). 인용할 때는 이미지와 대조한다.
* 정관이 PDF 파일로 첨부된 경우(31사)는 PDF 를 받아 글자층을 뽑고, 글자층 없는 쪽만 글자 인식했다(`charter_pdf_txt`).
  종류와 상관없이 정관 전문은 `charter_fulltext_txt` 하나로 읽을 수 있다.
* 스캔 이미지 파일은 git 에 올리지 않는다(약 600MB). PDF 원본(31개 약 17MB)은 올린다. 웹페이지는 이 컴퓨터에 파일이 없으면 DART 원본 이미지 주소로 바로 띄운다(GitHub Pages 포함).

## 실행

```bash
pip install -r requirements.txt          # krx-kind-data-api 는 GitHub 에서 설치된다
cp .env.example .env                     # DART_API_KEY 넣기
```

* **노트북 하나로**: [`notebooks/00_master.ipynb`](notebooks/00_master.ipynb) 를 위에서 아래로 실행 (단계별 요약·검증 포함)
* **스크립트로**: 차례대로

| 순서 | 스크립트 | 하는 일 | 출처 |
|---|---|---|---|
| 1 | `scripts/s01_list.py` | 사업보고서 최종본 목록 | OpenDART |
| 2 | `scripts/s02_market.py` | 소속시장 (기준일 현재) | KIND |
| 3 | `scripts/s03_dart_main.py` | `rcept_no_new` + 첨부문서 목록 (`--prewarm` 은 s02 없이 화면 캐시만 미리) | DART 웹 |
| 4 | `scripts/s04_charter.py` | 정관 원문 내려받기·정리 (`--limit N` 파일럿) | DART 웹 |
| 4b | `scripts/s04b_charter_ocr.py` | 스캔 정관 글자 인식 → `charter_ocr.txt` (Windows 전용, 네트워크 없음) | Windows OCR |
| 4c | `scripts/s04c_charter_pdf.py` | PDF 로 첨부된 정관 → PDF 받기·글자 뽑기 → `charter_pdf.txt` | DART 웹 |
| 5 | `scripts/s05_agm_list.py` | 주주총회소집공고 최종본 목록 · 행별 기간 | OpenDART |
| 6 | `scripts/s06_agm_xml.py` | 소집공고 XML 저장 → 정관의 변경 절 txt | OpenDART |
| 7 | `scripts/s07_build.py` | 결과물 JSON·CSV·XLSX | — |
| 8 | `scripts/s08_site.py` | 웹페이지 데이터 `site/data.js` | — |

웹페이지는 케이스 폴더에서 `python -m http.server` 를 띄우고 `http://localhost:8000/site/` 로 연다
(정관·정관의변경 txt 미리보기를 `fetch` 로 읽는다. file:// 로 열면 표만 보인다).

원본 응답은 모두 `data/raw/`(캐시)·`data/charter/` 에 저장되고, 다시 돌리면 저장본을 읽는다. 기준일은 `scripts/_common.py`
`AS_OF`(환경변수 `KC_AS_OF`). DART 는 IP 단위로 막으므로 다른 DART 수집과 동시에 돌리지 않는다.
노트북은 `python scripts/make_notebook.py` 로 다시 만든다.

## 폴더

| 경로 | 내용 | git |
|---|---|---|
| `scripts/` | 단계 `sNN_*.py` + 공용 `_common.py`(경로·기준일·HTTP·DART 파서) + `make_notebook.py` | ✅ |
| `notebooks/00_master.ipynb` | 마스터 노트북 | ✅ |
| `docs/01-수집사양.md` | 규칙 R1~R6 | ✅ |
| `docs/02-데이터사전.md` | 열 설명·저장 구조 | ✅ |
| `docs/03-검증기록.md` | 날짜별로 확인한 사실 | ✅ |
| `data/final/` | 결과물 | ✅ |
| `data/interim/` | 단계별 중간 파일 | ✅ |
| `data/charter/` | 정관 원문 (원문 HTML·텍스트·글자 인식·PDF·meta) | ✅ (`img/` 제외) |
| `data/agm/` | 소집공고 원문 (`정관의변경.txt`·meta) | ✅ (XML 제외) |
| `site/` | 웹페이지 | ✅ |
| `data/raw/` | 원본 응답 캐시 | ❌ |
| `.env` | DART 키 | ❌ (`.env.example` 만) |
