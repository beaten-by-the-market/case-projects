# low-pbr — 저PBR기업 최초 선정·공표(2026.11.2) 재현

한국거래소가 처음으로 공표한 **저PBR기업 151사**(유가 96·코스닥 55)를 공개 데이터로 다시 선정한다.
단계마다 숫자의 근거를 남긴다. 주가는 CHECK API(원격 게이트웨이), 재무는 CHECK IFRS 값과
**DART 원문 위치(접수번호·목차 노드·캡처)**로 보여 준다. 최종 결과는 KIND 밸류업 페이지 공표 목록과 대조하고,
차이 나는 회사에는 밸류업(기업가치 제고계획) 공시 여부와 URL을 붙인다.

## 폴더

| 경로 | 내용 | git |
|---|---|---|
| `source/` | 보도자료 PDF(원본), CHECK 게이트웨이 노트북(키 포함 → 제외) | PDF만 |
| `docs/00-보도자료-정리.md` | 보도자료 해설·검산·모호한 점 | ✅ |
| `docs/01-재현사양.md` | 규칙(R1~R14)·가정(A1~A7)·단계·최종 대조 방법 | ✅ |
| `docs/02-데이터저장.md` | MySQL `dart_periodic` 설계, 기존 수집분 재사용 | ✅ |
| `docs/03-검증기록.md` | 날짜별로 확인한 사실 | ✅ |
| `sql/dart_periodic.sql` | 정기보고서 원문 DB 스키마 | ✅ |
| `scripts/` | 단계별 스크립트 `sNN_*.py` + 공용 `_gw.py`(게이트웨이)·`_db.py`(MySQL)·`_rules.py` | ✅ |
| `data/raw/` | 응답 캐시(CHECK·KIND·KRX) — 재수집 가능 | ❌ |
| `data/interim/` | 단계 중간 산출물. **CHECK 원천값(`mktcap_daily`·`mktcap_round`·`equity_hist`·`comp_basic`)은 재배포하지 않아 제외** — s03·s05 로 다시 만든다 | 일부 |
| `data/final/` | 정답지(`press_*`·`kind_*`)와 재현 결과(`replica_selection`·`replica_sector`). `replica_firm_round`(CHECK 원값 포함)는 제외 | 일부 |
| `site/` | 결과 웹페이지(KIND 스타일)와 DART 캡처 | ✅ |
| `logs/` | 실행 로그 | ❌ |

## 실행 순서

```powershell
python scripts/s00_press.py         # 보도자료 → 정답지 CSV (검산 포함)
python scripts/s01_calendar.py      # 13개 회차 공표일·기준일·20거래일 구간          [CHECK]
python scripts/s02_universe.py      # 회차별 모집단 스냅샷·종류주 매핑              [KIND·KRX]
python scripts/s03_mktcap.py        # 시가총액 (약 4시간, 캐시로 이어 받기)          [CHECK]
python scripts/s04_dart_filings.py  # 정기보고서 목록 → MySQL dart_periodic          [OpenDART]
python scripts/s05_equity.py        # 자본총계 이력·업종(WICS)                       [CHECK]
python scripts/s10_kind_valueup.py  # KIND 저PBR 목록·밸류업 공시 목록               [KIND]
python scripts/s06_select.py        # PBR·업종 컷·선정·면제 → 보도자료·KIND 대조
python scripts/s07_dart_docs.py     # 근거 보고서 원문·목차·재무상태표 값            [OpenDART·DART]
.venv/Scripts/python scripts/s08_capture.py   # 자본총계 행 캡처 (Playwright)
python scripts/s09_site.py          # 웹페이지
```

- CHECK 호출은 **순차로만**(게이트웨이 뒤 KOSCOM 이 IP 단위 동시 연결을 막는다). 두 CHECK 스크립트를 동시에 돌리지 않는다.
- OpenDART·DART 웹도 IP 단위로 차단한다. s04·s07 을 동시에 돌리지 않는다.
- 게이트웨이 서버 인증서가 2026-10-16 에 만료된 채 갱신되지 않았다. 루트 CA로 체인을 검증한 leaf 지문을
  `.env` 의 `CHECK_GW_FP` 에 고정해 쓴다(`scripts/_gw.py`). 서버의 Caddy 를 재시작해 인증서가 갱신되면 이 값을 비운다.

## 설정

`.env.example` 을 `.env` 로 복사해 채운다 (게이트웨이 키·CA 경로, MySQL, DART 키).
캡처용 Playwright 는 프로젝트 가상환경에만 설치했다: `python -m venv .venv` → `.venv/Scripts/pip install playwright pymysql requests pandas` → `.venv/Scripts/python -m playwright install chromium`.
