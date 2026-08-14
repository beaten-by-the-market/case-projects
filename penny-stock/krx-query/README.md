# krx-query — 지정사유 발생일 시간외거래 조사 (거래소 내부 DB)

시가총액 미달 · 주가 미달(동전주) 사유로 관리종목에 지정된 종목들에 대해,
**지정사유가 확정된 날(15:30 종가 확정일)의 15:40~공시 발표 시각 사이 시간외거래**를
거래소 내부 Oracle 에서 뽑는다. [../proposal/](../proposal/) 의 "공시가 시간외거래보다
늦게 나간다" 는 조사에서 남은 숙제 — **피해 규모 정량화** — 를 채우는 부분이다.

## 파일

| 파일 | 실행 위치 | 역할 |
|---|---|---|
| [offhour_impact_query.py](offhour_impact_query.py) | **폐쇄망 (내부 DB)** | ★ Spyder **F5** 진입점. 조회 → `.txt` 출력 |
| [targets.py](targets.py) | (데이터) | 조사 대상 76건 — 종목·사유발생일·공시시각 |
| [build_targets.py](build_targets.py) | 외부망 | `targets.py` 재생성 (KIND 공시 수집본 + 스냅샷 코드 매핑) |

폐쇄망에는 `offhour_impact_query.py` + `targets.py` 두 개만 들고 들어가면 된다.

## 실행

1. DB 접속정보를 넣는다. 둘 중 하나:
   - 같은 폴더에 `credentials_local.py` 생성 (권장 — `.gitignore` 대상)
     ```python
     DB_USER = "실제계정"
     DB_PASSWORD = "실제비밀번호"
     DB_DSN = "DBMMXP"
     ```
   - 또는 `offhour_impact_query.py` 상단 `DB_USER/DB_PASSWORD/DB_DSN` 의 `"CHANGE_ME"` 교체
     (⚠ 교체본을 commit 하지 말 것)
2. Spyder 에서 `offhour_impact_query.py` 를 열고 **F5**.
3. 스크립트와 **같은 폴더**에 결과가 떨어진다.
   - `offhour_impact_<YYYYMMDD_HHMMSS>.txt` — 사람이 읽는 리포트
   - `offhour_impact_<YYYYMMDD_HHMMSS>_ticks.txt` — 체결 단위 전건(탭 구분, 엑셀 붙여넣기용)

먼저 `LIMIT = 3` 으로 소수 건만 돌려 접속·권한·컬럼을 확인한 뒤 `None` 으로 되돌리는 걸 권한다.

## 뽑는 것

| # | 내용 | 산출 |
|---|---|---|
| 1 | 사유발생일 **15:40 ~ 공시 발표 시각** 시간외거래 | 거래대금 · 거래량 · 체결건수 · VWAP · 보드별 분해 · **체결가격 목록(체결 단위 전건 + 가격별 집계)** |
| 2 | 같은 날 **하루 전체** 거래 | 일별 집계(시가/고가/저가/종가/거래량/거래대금/시총) + 체결원장 보드별 분해 + 시간외 비중 % |
| 3 | **다음 거래일(= 지정 효력일) 시가** | 시가, 당일 종가 대비 등락, **체결가격별·체결 단위 수익률 목록**, 익일 시가 청산 가정 평가손익 |

수익률 = `익일 시가 / 체결가 − 1`. 시간외에 매수해 지정 효력일 시가에 청산했을 때의 손익이다.

## DB 객체

| 객체 | 용도 | 비고 |
|---|---|---|
| `USSV.VWSV_SPOT_TRD3` | 현물 체결 원장 | `TRD_TM` = `HHMMSSXXX`, `BRD_ID` = 보드 |
| `USMD.TBMD_BYDD_ISU_TRDPRC` | 일별 종목 거래·시세 | `TDD_OPNPRC` 시가, `ACC_TRDVAL/VOL` 누적, `MKTCAP` |
| `USMC.TBMC_BZ_DD` | 영업일 마스터 | `CALND_ID='EXCH'` — 다음 거래일 산출 |

보드ID (`TBMC_CD_VAL`, `CD_ENG_NM='BRD_ID'`):

| 보드 | 의미 | 시간 |
|---|---|---|
| `G1` | 정규장 | 09:00~15:30 (종가단일가 15:20~15:30) |
| `G3` | 장종료후종가 | 15:40~16:00 |
| `G4` | 장종료후단일가 | 16:00~18:00 |
| `B3`/`K3`/`N3` | 장종료후 대량·바스켓·협의대량 | 리포트에 별도 표기 |

**핵심 집계는 `G3+G4`(시간외 일반매매)** 이고, 대량·협의(`B3/K3/N3`)는 성격이 달라
합계에 섞지 않고 따로 보여준다. 전 보드 합계도 함께 찍는다.

## 조사 구간 경계

`INCLUDE_END_MIN = False` (기본) 이면 공시시각 **직전**까지 — 공시 18:35 이면 18:34:59.999.
KIND 접수시각이 분 단위라 공시 분에 걸친 체결의 선후를 가릴 수 없어 보수적으로 뺀다.
`True` 로 두면 그 분을 통째로 포함한다.

## 대상 76건

KIND 공시 전수 (2026-02-12 ~ 2026-08-13). 시총·동전주 사유 지정은 2026년에 처음
등장했으므로 이게 전수다. 근거·수집 방법은 [../proposal/findings_공시시각분포.md](../proposal/findings_공시시각분포.md).

| | 시가총액 미달 | 주가 미달(동전주) | 시총+주가 동시 | 계 |
|---|---:|---:|---:|---:|
| 코스닥 | 35 | 24 | 2 | **61** (53종목) |
| 유가증권 | 10 | 3 | 2 | **15** (15종목) |
| **계** | **45** | **27** | **4** | **76** |

`targets.py` 의 `dd` 는 **공시일 = 지정사유 발생일**(그날 15:30 종가로 판정 확정)이고,
지정 효력은 그 다음 거래일부터다. 스크립트가 [3]에서 쓰는 "익일" 이 곧 지정 효력일이다.

목록을 갱신하려면 외부망에서:

```bash
python proposal/scripts/collect_disclosure_times.py --from 2015 --to 2026 --to-date <오늘>
python proposal/scripts/analyze_disclosure_times.py
python krx-query/build_targets.py
```

## 참고

쿼리 작성 방식은 `krx-mktinfo-queries` (특히 `trading_halt_spread/`, `krx_db/SCHEMA_GUIDE.md`)
와 `krx-bizmeta` 의 관행을 따랐다 — `config` 상단 일괄 설정, `credentials_local.py` 분리,
Spyder F5 단일 진입점, owner prefix 포함 `TBL_*` 상수화.
