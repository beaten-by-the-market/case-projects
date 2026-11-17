# kospi-charter — 최근 1년 사업보고서 목록 + 코스피·코스닥 정관 원문

## 한 줄 요약

OpenDART 에서 **최근 1년(2025-11-16 ~ 2026-11-16) 사업보고서 최종본 목록**을 JSON 으로 받아 **회사마다 가장 최근 1건**만 남기고,
`[첨부정정]` 은 본문 접수번호(`rcept_no_new`)를, 모든 행에 사업연도·결산월·소속시장을 붙였다.
그중 **코스피 기업** 행마다 첨부문서 목록(OpenDartReader `attach_docs()` 와 같은 목록)에서 **정관 URL** 을 찾아 넣고,
정관 원문(텍스트 또는 스캔 이미지)을 회사·문서별 폴더에 내려받아 그 위치를 목록에 링크로 달았다.
이어서 사업보고서 원본 제출일부터 기준일까지 접수된 **주주총회소집공고**(최종본)의 XML 원문을 모두 저장하고,
'2. 주주총회 목적사항별 기재사항'에 **정관의 변경** 절이 있는 공고를 세어 그 절 텍스트를 txt 로 따로 저장해 링크했다.
**코스닥 기업**에도 같은 규칙으로 정관 원문·소집공고를 모으고, KIND 상장회사 중 목록에 없는 회사의 근거를 남겼다(docs/01 R7, `kosdaq_*` 파일).
결과는 data.krx.co.kr 디자인을 빌린 정적 웹페이지(`site/`)로 본다.
끝으로 정관마다 **결산배당 기준일 조항**을 키워드 발췌 + Claude Opus 5.5 로 읽어 `정관no`(이사회가 정함)·`정관yes`(정관상 결산일)·
`정관yesorno`(결산일 원칙 + 이사회도 가능) 태그를 달았다(코스피는 API, 코스닥은 같은 지침으로 Claude Code 서브에이전트) — [docs/04-배당기준일태깅.md](docs/04-배당기준일태깅.md), 스킬 `.claude/skills/charter-dividend-record-date/`.

| 결과 (기준일 2026-11-16) | 값 |
|---|---|
| 사업보고서 최종본, 회사별 1건 | **3,349사** — 코스피 825 · 코스닥 1,784 · 코넥스 107 · 기타 633 |
| KIND 코스피 상장회사 중 목록에 없는 회사 | **829사 중 4사** — 신규상장 1(첫 사업보고서 기한 전) · 투자회사 3(사업보고서 대신 KIND '기타신고사항') |
| `[첨부정정]` → `rcept_no_new` | 86건 |
| 코스피 정관 원문 | **825/825** — 텍스트 629 · 스캔 이미지 164 · PDF 31 · 혼합 1 |
| 스캔 쪽 Opus 전사 | **3,225쪽 / 181개 정관, 실패 0** (Claude Opus 5.5 · Batches API · 약 $51) |
| 원본 제출일 이후 소집공고 | **247건**, 그중 '정관의 변경' 절 **146건** (해당 회사 134사) |
| **코스닥** 정관 원문 | **1,784/1,784** — 텍스트 1,390 · 스캔 이미지 290 · PDF 93 · 혼합 11. 정관 전문 1,780 (PDF 를 받을 수 없는 4사 제외) |
| 코스닥 스캔 쪽 Opus 전사 | **6,017쪽 / 370개 정관, 실패 0** (약 $98) |
| 코스닥 원본 제출일 이후 소집공고 | **720건**, 그중 '정관의 변경' 절 **464건** (해당 회사 401사). 원문 없음 1(기준일 당일 접수) |
| KIND 코스닥 상장회사 중 목록에 없는 회사 | **1,833사 중 49사** — 신규상장 48(주권 34 · 스팩 13 · DR 1) · 회생절차로 사업보고서 미제출 1(피씨엘) |
| 사업보고서 없는 상장회사의 정관 (다른 근거문서) | **52/52사** — 증권신고서 47 · 모회사 분할공시 2 · 기타신고사항 3 (코스피 4 · 코스닥 48, 피씨엘 제외) |
| 정관 결산배당 기준일 태그 (첨부 정관) | **정관no 437 · 정관yes 378 · 정관yesorno 7 · 확인필요 3** (LLM 약 $16, 사람 검토 41건) |
| 결산배당 기준일 태그 (지금) | **정관no 449 · 정관yes 369 · 정관yesorno 7** — 제출 뒤 주총 가결 9사(KIND 주주총회결과 확인) · 확인필요 3사는 전년도 정관·소집공고로 |
| 코스닥 결산배당 기준일 태그 (지금) | **정관no 758 · 정관yes 824 · 정관yesorno 202** (1,784사) — 서브에이전트 판별(API 비용 0) · 서식 판정 259건 중 39건 태그 조정 · 제출 뒤 주총 가결 16사 · 확인필요 4사는 전년도 정관·사업보고서 본문으로 |

자세한 건수와 확인한 사실은 [docs/03-검증기록.md](docs/03-검증기록.md), `data/final/manifest.json`(코스닥은 `kosdaq_manifest.json`).

## 결과물

| 파일 | 내용 |
|---|---|
| [`data/final/annual_reports.json`](data/final/annual_reports.json) · `.csv` | 사업보고서 최종본 전체. API 열 + `rcept_no_new`·`fiscal_year`·`settle_month`·`market` … |
| [`data/final/kospi_charter.json`](data/final/kospi_charter.json) · `.csv` · `.xlsx` | 코스피 행 + `charter_url`(정관 URL)·`charter_content_type`·`charter_txt`·`charter_img_dir` … |
| [`data/final/charter_docs.csv`](data/final/charter_docs.csv) | 내려받은 정관 문서 색인 |
| [`data/final/kospi_absent.csv`](data/final/kospi_absent.csv) | KIND 코스피 상장회사인데 목록에 없는 회사와 근거 (사업보고서 이력·대신 낸 공시) |
| [`data/final/agm_notices.csv`](data/final/agm_notices.csv) | 주주총회소집공고 색인 — 정관의 변경 절 유무·`정관의변경.txt` 위치 |
| [`data/agm/`](data/agm/) | 소집공고 원문 — `{종목코드}_{회사명}/{접수일}_{rcept_no}/` 아래 XML·`정관의변경.txt`·`meta.json` |
| [`site/`](site/) | 웹페이지 (`index.html` + `data.js`) — 근거문서 표 하나(사업보고서 1건 = 1행 + 사업보고서 없는 상장회사는 증권신고서 등 근거문서 1행, 시장·근거문서·정관 원문 종류·소집공고 정관변경 필터), 배당기준일 탭 3개(배당기준일 · 배당기준일 취합 · 배당 특이사항)는 `dividend.js` + 근거 그림 `evidence/` |
| [`data/charter/`](data/charter/) | 정관 원문 — `{종목코드}_{회사명}/{첨부일자}_{dcmNo}/` 아래 `charter.txt`·`img/`·`meta.json`·`viewer_01.html` |
| [`data/final/manifest.json`](data/final/manifest.json) | 기준일·조회기간·출처·건수 |
| [`data/final/kosdaq_charter.json`](data/final/kosdaq_charter.json) · `.csv` · `.xlsx` · `kosdaq_charter_docs` · `kosdaq_agm_notices` · `kosdaq_absent` · `kosdaq_manifest.json` | 코스닥 — 열은 코스피 짝(`kospi_charter` · `charter_docs` · `agm_notices` · `kospi_absent` · `manifest`)과 같다 |
| [`data/charter_kosdaq/`](data/charter_kosdaq/) · [`data/agm_kosdaq/`](data/agm_kosdaq/) | 코스닥 정관·소집공고 원문 — 폴더 구조는 `data/charter/` · `data/agm/` 과 같다 |
| [`data/final/absent_charter.json`](data/final/absent_charter.json) · `.csv` | 사업보고서가 없어 빠진 신규상장·투자회사의 정관 — 근거문서(`charter_source_doc`: 증권신고서 · 분할공시(모회사) · 기타신고사항 · 홈페이지) + 정관·주총 열. 원문은 `data/charter_absent/` · `data/agm_absent/` |
| [`data/final/charter_dividend_record_date.json`](data/final/charter_dividend_record_date.json) · `.csv` · `_kosdaq.json` · `_kosdaq.csv` · `_absent.json` · `_absent.csv`(사업보고서 없는 상장회사 52사) | 코스피·코스닥 정관 결산배당 기준일 태그 — `tag`·근거 조문·인용·중간/분기배당·검증·제출 뒤 안건(`tag_after_agm`). 열 설명은 docs/04 |
| [`.claude/skills/charter-dividend-record-date/`](.claude/skills/charter-dividend-record-date/SKILL.md) | 태깅 스킬 — 판별 지침(LLM 프롬프트 원본)·배당기준일 규제 연혁. 원문 사본은 `source/regulation/` |

열 설명은 [docs/02-데이터사전.md](docs/02-데이터사전.md). 폴더·열 이름의 `charter` 는 정관(영문 정식 명칭 Articles of Incorporation)을 가리키는 식별자다.

## 규칙 (자세히는 [docs/01-수집사양.md](docs/01-수집사양.md))

| | 규칙 |
|---|---|
| 목록 | OpenDART `list.json`, `A001`, **`last_reprt_at=Y`(최종본만 = `final=True`)**, 3개월 구간으로 나눠 호출. `사업보고서제출기한연장신고서` 제외. **회사별 가장 최근 1건**(결산기가 가장 늦은 것) |
| `rcept_no_new` | **최종본이 `[첨부정정]` 인 행만** DART `main.do` 의 `<select id="family">` 첫 옵션(최근 본문) 접수번호. 나머지는 `rcept_no` 그대로 (기존 `get_recent()` 규칙) |
| 사업연도·결산월 | 보고서명 `(YYYY.MM)`. 사업연도 = OpenDART `bsns_year` 규칙(결산기 말 연도) |
| 소속시장 | **KIND 기준일 현재 상장 목록을 한 번** 받아 종목코드(없으면 회사명)로 맞춘다. 코스피 상장회사 중 행이 없는 회사는 OpenDART·KIND 공시로 이유를 확인해 `kospi_absent` 에 남긴다 |
| 정관 | `main.do` 의 `<select id="att">`(= `attach_docs()`) 에서 제목이 `정관` 인 첨부 → 첨부 `main.do` → `viewer.do` 원문 → `<img>` 는 `download.do` 로 내려받기 |
| 주총 | 기간 = [사업보고서 **원본 최초 접수일**, 기준일]. 그 안에 **접수된** 소집공고 최종본(`E006`) 수 = `agm_count`. 공고마다 `document.xml` 원문 저장, 안건유형 절 `TITLE@AASSOCNOTE="L0-0-2-2-0"`(정관의 변경)이 있으면 `agm_charter_amend_count` 에 세고 절 텍스트를 `정관의변경.txt` 로 |
| 코스닥 | 위 규칙을 코스닥 행에 그대로. 코스닥 단계(`sNNk_kosdaq_*.py`)는 코스피 스크립트의 함수를 import 해 쓰고 저장 위치만 바꾼다. 본문 텍스트에 같은 정관 PDF 도 붙은 정관은 `text`, PDF 를 받을 수 없는 정관은 전문 없음 |
| 사업보고서 없는 회사 | 신규상장은 상장 때 증권신고서의 첨부 정관, 인적분할 재상장은 모회사 회사분할결정의 분할계획서 '분할신설회사 정관(안)' 쪽, 투자회사는 KIND 정관 개정 공지 첨부·홈페이지 게시 정관. 그 뒤 소집공고의 '정관의 변경'도 붙인다 (docs/01 R8) |

## 한계

* **소속시장은 제출 당시가 아니라 기준일 현재다** (사용자 결정 2026-11-16). 제출 뒤 상장폐지·이전상장·신규상장된 회사는 현재 시장으로 분류된다.
  OpenDART `corp_cls` 도 현재 기준이라 `market` 과 같다 (예: 한창 005110 — 2026-03 제출 때 유가 상장사, 지금 `기타`).
* DART 화면의 `family`·`att` 는 **수집시점(2026-11-16 코스피 11:51 ~ 12:10 · 코스닥 18:56 ~ 19:31) 기준**이다(`s03_main.json` 의 `fetched_at`, `manifest.json` 의 `fetched`). 그 뒤 정정공시가 나오면 바뀐다.
* **코스피 정관 표는 조회기간에 사업보고서를 낸 회사만 담는다.** KIND 코스피 상장회사 829사 중 4사가 빠진다.
  한화머시너리앤서비스홀딩스는 2026-08-25 신규상장이라 첫 사업보고서(기한 2027-03-31)가 아직 없다.
  투자회사 KB발해인프라·맵스리얼티·맥쿼리인프라는 DART 사업보고서 이력이 없고, 분기·결산 보고를 KIND '기타신고사항'으로 낸다. 명단과 근거는 `kospi_absent`, 웹페이지 근거문서 표 위 안내(정관은 다른 근거문서로 찾아 `absent_charter` 로 넣었다).
  코스닥은 1,833사 중 49사가 빠진다 — 2026-03 이후 신규상장 48사(첫 사업보고서 기한 2027-03-31)와, 회생절차를 신청해 2025년 결산 사업보고서를 내지 않은 피씨엘(`kosdaq_absent`).
* **코스닥 정관 4사는 전문이 없다** — 이씨에스·청담글로벌·민테크는 DART 가 PDF 를 내주지 않고(‘안내’ 화면), 레이는 DRM 암호화 PDF 다(`charter_fulltext_txt` 빈 값).
  코스닥 소집공고 1건(오스코텍, 기준일 당일 접수)은 OpenDART 원문이 아직 없다(`agm_errors`).
* **주총은 소집공고 접수일로 센다** (사용자 결정). 소집공고(주총 2주 전)가 사업보고서(주총 1주 전)보다 먼저 나오므로,
  사업보고서 직후 열리는 정기주총은 대개 `agm_count` 에 들어가지 않는다.
* 스캔 이미지 정관(`charter_content_type=image`)은 Windows 내장 OCR 로 글자를 옮긴 `charter_ocr.txt` 를 함께 둔다(`charter_ocr_txt`).
  기계 인식이라 틀린 글자가 있다 — 선명한 장은 약 99%, 작은 스캔은 80~93% (docs/01 R5-7). 인용할 때는 이미지와 대조한다.
* 스캔 쪽(이미지 3,185장 + PDF 스캔 40쪽)은 **Claude Opus 5.5 가 직접 읽어 옮긴 글**(`charter_llm_txt`)을 함께 둔다 — Windows OCR 이 틀리던 작은 스캔·원문자도 바로 읽는다(docs/01 R5-9).
  웹페이지는 정관 본문을 한 파일만 건다 — 스캔은 Opus 전사이고 OCR 결과는 데이터 폴더에만 둔다(사용자 결정).
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
| 2b | `scripts/s02b_kospi_absent.py` | KIND 코스피 상장회사 중 목록에 없는 회사와 근거 | OpenDART · KIND |
| 3 | `scripts/s03_dart_main.py` | `rcept_no_new` + 첨부문서 목록 (`--prewarm` 은 s02 없이 화면 캐시만 미리) | DART 웹 |
| 4 | `scripts/s04_charter.py` | 정관 원문 내려받기·정리 (`--limit N` 파일럿) | DART 웹 |
| 4b | `scripts/s04b_charter_ocr.py` | 스캔 정관 글자 인식 → `charter_ocr.txt` (Windows 전용, 네트워크 없음) | Windows OCR |
| 4d | `scripts/s04d_charter_llm_ocr.py` | 스캔 쪽 전부를 Claude Opus 5.5 로 전사 (Batches API · `.env` 의 `ANTHROPIC_API_KEY`, 비용 발생) | Anthropic API |
| 4c | `scripts/s04c_charter_pdf.py` | PDF 로 첨부된 정관 → PDF 받기·글자 뽑기 → `charter_pdf.txt` | DART 웹 |
| 5 | `scripts/s05_agm_list.py` | 주주총회소집공고 최종본 목록 · 행별 기간 | OpenDART |
| 6 | `scripts/s06_agm_xml.py` | 소집공고 XML 저장 → 정관의 변경 절 txt | OpenDART |
| 7 | `scripts/s07_build.py` | 결과물 JSON·CSV·XLSX | — |
| 8 | `scripts/s08_site.py` | 웹페이지 데이터 `site/data.js` (코스피·코스닥 결과물 함께) | — |
| 2c | `scripts/s02c_kosdaq_absent.py` | **코스닥** — KIND 코스닥 상장회사 중 목록에 없는 회사와 근거 (s02b 복사본) | OpenDART · KIND |
| 2d | `scripts/s02d_kind_settle_month.py` | 지금 결산월 (KIND 상장법인목록, 코스피·코스닥) → 배당기준일 탭 결산월 비교 | KIND |
| 2e | `scripts/s02e_check_group.py` | 확인그룹 — 사용자가 준 엑셀의 코스피 종목별 그룹 번호(이름은 싣지 않음) → 웹페이지 '확인그룹' 칸 | 엑셀 |
| 3k·4k | `scripts/s03k_kosdaq_main.py` · `s04k_kosdaq_charter.py` | 코스닥 — 첨부문서 목록 · 정관 원문 | DART 웹 |
| 4ck·4bk·4dk | `scripts/s04ck_kosdaq_pdf.py` · `s04bk_kosdaq_ocr.py` · `s04dk_kosdaq_llm.py` | 코스닥 — PDF 정관 · Windows OCR · Opus 전사(비용 발생) | DART 웹 · Windows OCR · Anthropic API |
| 5k·6k | `scripts/s05k_kosdaq_agm_list.py` · `s06k_kosdaq_agm_xml.py` | 코스닥 — 소집공고 목록 · XML·정관의 변경 절 | OpenDART |
| 7k | `scripts/s07k_kosdaq_build.py` | 코스닥 결과물 `data/final/kosdaq_*` (그 뒤 8 을 다시) | — |
| 4e | `scripts/s04e_absent_charter.py` `plan` · `fetch` · `ocr` · `llm pages`/`organize` · `agm` | 사업보고서 없는 회사 — 근거문서 고르기 · 정관 받기 · OCR · 전사 목록(API 없이, 전사는 세션 에이전트) · 소집공고 | DART 웹 · KIND · 홈페이지 · OpenDART |
| 7e | `scripts/s07e_absent_build.py` | 사업보고서 없는 회사 결과물 `data/final/absent_charter.*` (그 뒤 8 을 다시) | — |
| 9a | `scripts/s09a_dividend_excerpt.py` | 정관에서 배당기준일 관련 대목만 발췌 (한글·한자 키워드 앵커 + 참조 조문) | — |
| 9b | `scripts/s09b_dividend_tag_llm.py` | 발췌를 Claude Opus 5.5 로 판별 → 태그 (`pilot`·`submit`·`collect` · Batches API, 비용 발생 — 코스닥은 `pack`·`ingest` 로 서브에이전트가 판별) | Anthropic API / 서브에이전트 |
| 9d | `scripts/s09d_dividend_after_agm.py` | 제출 뒤 '정관의 변경' 안건이 결산배당 기준일을 바꾸는지 (동기, 비용 발생) | Anthropic API |
| 9e | `scripts/s09e_agm_result_kind.py` | 기준일 조항을 바꾸는 안건의 가결 여부 — KIND 주주총회결과 (krx-kind-data-api) | KIND |
| 9f | `scripts/s09f_prev_charter.py` | 확인필요 회사: 전년도 사업보고서 정관·그 사이 소집공고 받기(`fetch`, DART 웹 — 다른 수집과 겹치지 않게) → 전사·판별 | DART 웹 · OpenDART · Anthropic API |
| 9h | `scripts/s09h_kosdaq_review.py` | 코스닥: 서브에이전트 태그가 갈린 정관 서식(스팩 잔존 문구·상법 제354조식 단서·택일형 등)을 한 기준으로 → `s09_review_kosdaq.json` | — |
| 9i | `scripts/s09i_pre_agm.py` | 사업보고서보다 먼저 접수된 그해 정기주총 소집공고의 '정관의 변경' — 대상(E006 캐시)·원문(OpenDART document.xml)·`pack`·`ingest`(서브에이전트 판별) | OpenDART · 서브에이전트 |
| 9c | `scripts/s09c_dividend_build.py` | 인용 대조·독립 규칙 판별·사람 검토(`s09_review.json`) 반영 · 지금 태그(`tag_current`)·근거 종류 → `charter_dividend_record_date` (`--queue` 검토 목록) | — |
| 9g | `scripts/s09g_dividend_evidence.py` | 근거 조항(조 단위) · 스캔 쪽을 OCR 로 다시 읽어 해당 부분만 잘라 `site/evidence/` · 소집공고 대비표 행 | Windows OCR |
| 10 | `scripts/s10_dividend_site.py` | 웹페이지 배당기준일 탭 3개의 데이터 `site/dividend.js` (s08·data.js 와 따로) | — |

* 2026-11-17부터 Claude API 는 쓰지 않는다. 9b·9d·9i 판별과 스캔 쪽 전사는 `pack` → 서브에이전트 → `ingest` 로 한다. 사업보고서 없는 상장회사 52사는 9a~9g 에 `--sfx absent` 로 같은 단계를 탄다.

웹페이지는 케이스 폴더에서 `python -m http.server` 를 띄우고 `http://localhost:8000/site/` 로 연다
(정관·정관의변경 txt 미리보기를 `fetch` 로 읽는다. file:// 로 열면 표만 보인다).

원본 응답은 모두 `data/raw/`(캐시)·`data/charter/` 에 저장되고, 다시 돌리면 저장본을 읽는다. 기준일은 `scripts/_common.py`
`AS_OF`(환경변수 `KC_AS_OF`). DART 는 IP 단위로 막으므로 다른 DART 수집과 동시에 돌리지 않는다.
노트북은 `python scripts/make_notebook.py` 로 다시 만든다.

## 폴더

| 경로 | 내용 | git |
|---|---|---|
| `scripts/` | 단계 `sNN_*.py` + 공용 `_common.py`(경로·기준일·HTTP·DART 파서) + `make_notebook.py` · 코스닥 `sNNk_kosdaq_*.py` + `_kosdaq.py`(코스닥 경로) | ✅ |
| `notebooks/00_master.ipynb` | 마스터 노트북 | ✅ |
| `docs/01-수집사양.md` | 규칙 R1~R8 (R7 = 코스닥, R8 = 사업보고서 없는 회사) | ✅ |
| `docs/02-데이터사전.md` | 열 설명·저장 구조 | ✅ |
| `docs/03-검증기록.md` | 날짜별로 확인한 사실 | ✅ |
| `docs/04-배당기준일태깅.md` | 배당기준일 태그 — 결과·방법·검증·열 설명 | ✅ |
| `.claude/skills/charter-dividend-record-date/` | 배당기준일 태깅 스킬 (SKILL.md · 판별 지침 · 규제 연혁) | ✅ |
| `source/regulation/` | 배당기준일 규제 원문 사본 (금융위·상장협 보도자료 등 10건) | ✅ |
| `data/final/` | 결과물 | ✅ |
| `data/interim/` | 단계별 중간 파일 | ✅ |
| `data/charter/` | 정관 원문 (원문 HTML·텍스트·글자 인식·PDF·meta) | ✅ (`img/` 제외) |
| `data/agm/` | 소집공고 원문 (`정관의변경.txt`·meta) | ✅ (XML 제외) |
| `data/charter_kosdaq/` · `data/agm_kosdaq/` | 코스닥 정관·소집공고 원문 | ✅ (`img/`·XML 제외) |
| `data/charter_absent/` · `data/charter_absent_src/` · `data/agm_absent/` | 사업보고서 없는 회사의 정관 · 정관을 뽑아낸 원문(분할계획서) · 소집공고 원문 | ✅ (`img/`·XML 제외) |
| `site/` | 웹페이지 | ✅ |
| `data/raw/` | 원본 응답 캐시 | ❌ |
| `.env` | DART 키 | ❌ (`.env.example` 만) |
