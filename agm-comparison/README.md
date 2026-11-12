# agm-comparison — 주주총회 공시의 구조화 수준 (DART vs SEC)

DART 주주총회소집공고 XML 원문에 붙는 **표준 코드(안건유형 등)** 를 실물로 정리하고,
SEC 주주총회 관련 공시가 어떤 형태로 제공되며 안건유형 분류가 가능한지 비교한다.

## 핵심

→ 결론과 주장별 판정은 [docs/00-결론정리.md](docs/00-결론정리.md)


- DART 소집공고의 안건유형 코드는 `TITLE@AASSOCNOTE="L0-0-2-N-0"`, **N = 증권발행공시규정 제3-15조 ③항 N호** (1 재무제표 승인 … 20 기타). → [docs/01](docs/01-DART코드정리.md), [data/final/agm_codebook.csv](data/final/agm_codebook.csv)
- 코드는 의안 단위가 아니라 **안건유형 단위**다. 의안 목록은 자유 텍스트.
- SEC 는 DEF 14A 안건에 유형 태그가 없다. 가장 가까운 것은 펀드가 내는 N-PX XML 의 14개 `categoryType`. → [docs/02](docs/02-SEC주총공시.md)

## 실행 순서

`.env` 에 `DART_API_KEY`(여러 개면 `DART_API_KEY_1` …). OpenDART 는 IP 단위 차단 — 다른 수집과 동시에 돌리지 않는다.

| 단계 | 스크립트 | 출력 |
|---|---|---|
| 1 | `python scripts/s01_list_filings.py` | 소집공고(E006) 목록 2016-01~2026-10 → `data/interim/filings_e006.csv` (캐시 `data/raw/list/`) |
| 2 | `python scripts/s02_sample.py` | 층화 표본 99건 → `data/interim/sample.csv` |
| 2b | `python scripts/s02b_sample_extra.py` | 보충 표본 175건(비성수기·신서식) → `data/interim/sample_extra.csv` |
| 3 | `python scripts/s03_fetch_xml.py [--sample …]` | 원문 ZIP 풀어 저장 → `data/raw/xml/{rcept_no}/` |
| 4 | `python scripts/s04_extract_codes.py` | 코드 등장 전수 `data/interim/code_occ.csv`, 집계 `data/final/code_summary.csv` |
| 5 | `python scripts/s06_targets.py` → s03 `--sample data/interim/sample_targets.csv` | 뉴스로 찾은 드문 안건(7·15~18호) 표적 공고 |
| 5b | `python scripts/s10_scan_rare.py` (2차: `--since 20250101 --corr --peak --stop-eng17`) | 아직 받지 않은 공고를 훑어 7·16·17호 찾기 → `data/interim/scan_rare.csv`, 나온 공고만 원문 저장(s04 전에 실행) |
| 6 | s04 다시 → `python scripts/s05_codebook.py` | 코드북 `data/final/agm_codebook.csv` |
| 7 | `python scripts/s07_section_tables.py` | 안건 절 안 표의 소제목·머리행 (항목 태그 없음 확인용) → `data/interim/section_tables.csv`, `data/final/section_table_summary.csv` |
| 8 | `python scripts/s08_krx_convene.py` | 거래소 소집결의·참고서류 원문과 시차 → `data/interim/krx_convene.csv`, `data/raw/krx/`, `data/raw/d003/` |

## 폴더

`scripts/`(sNN 단계 + `_dart.py` 공용) · `data/raw`(원문 캐시, git 제외) · `data/interim` · `data/final` · `docs/01~03` · `logs/`(git 제외)
