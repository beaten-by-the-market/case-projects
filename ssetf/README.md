# 삼성전자·SK하이닉스 레버리지 상품 데이터셋

한국(KRX)·홍콩(HKEX)·런던(LSE)에 상장된 **삼성전자/SK하이닉스 레버리지 ETP/ETF**의
① 일별 거래데이터, ② AUM·NAV, ③ 한국인 보유·결제(SEIBRO)를 **각 거래소 네이티브
소스**에서 수집·통합한다. (야후는 커버리지 공백·강등 함정으로 폐기 → `archive/`.)

이 README는 **재현 런북**이다. 소스별 기술 상세는 [docs/SOURCES.md](docs/SOURCES.md),
파일 스키마는 [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).

---

## 폴더 구조

```
ssetf/
├─ README.md                  # ← 이 문서(시작점·런북)
├─ requirements.txt           # 파이썬 의존성(+krx-data-api 외부)
├─ tickers.csv                # ★ 종목 매핑 마스터(19종목)
├─ scripts/                   # 수집·통합 스크립트 (어디서 실행하든 루트 기준으로 동작)
│   ├─ hkex_history.py  lse_history.py  krx_history.py   # 거래데이터
│   ├─ lse_aum.py  csop_aum.py                            # AUM·NAV
│   ├─ naver_fx.py  seibro_daily.py                       # 환율·SEIBRO
│   └─ build_dataset.py                                   # 통합+KRW 환산
├─ charts/                    # 차트 스크립트 + 산출 PNG (charts/ 바로 아래 유지 필수)
├─ data/                      # 모든 CSV/JSON 산출물 (utf-8-sig)
├─ docs/
│   ├─ SOURCES.md             # 소스별 API·인증·엔드포인트·함정
│   ├─ DATA_DICTIONARY.md     # data/ 파일 스키마
│   └─ samples/lse_trade.json # 캡처 샘플(LSE 위젯 응답)
├─ assets/images/             # 스크린샷(bloomberg/csop/seibro 등)
├─ _posts/                    # 블로그 초안
└─ archive/                   # 레거시(야후 기반, 폐기)
```

> **실행 규칙**: 스크립트는 자기위치를 잡아 항상 프로젝트 루트 기준으로 `data/`를 읽고
> 쓴다. `python scripts/…` 든 절대경로든 어디서 호출해도 산출물은 `data/`로 간다.

---

## 빠른 시작

```bash
pip install -r requirements.txt
python scripts/build_dataset.py      # 이미 수집된 data/로 통합본(all_krw.csv) 재생성 — 무인증
```

전체를 **원천부터** 다시 만들려면 아래 런북을 순서대로.

---

## 재현 런북 (원천 → 통합 → 차트)

### 0) 인증 준비 (필요한 것만)
| 소스 | 필요 | 얻는 법 | 전달 |
|---|---|---|---|
| HKEX(거래·CSOP AUM hkex소스) | 위젯 token | DevTools→`getequityquote`의 `token` | `--token` / `HKEX_TOKEN` |
| LSE(거래) | X-API-KEY | DevTools→`auth/api/v1/tokens`의 헤더 | `--api-key` / `LSE_API_KEY` |
| KRX | krx-data-api + 로그인 | 외부 레포 설치 + `.env` | 자동 |
| **LSE AUM / CSOP AUM(ice) / FX / SEIBRO** | **없음** | — | 무인증 |

자세한 인증·엔드포인트: [docs/SOURCES.md](docs/SOURCES.md).

### 1) 거래데이터 수집
```bash
python scripts/hkex_history.py 7747 9747 7709 7347 9347 --token "<HKEX_TOKEN>"
python scripts/lse_history.py  HNX3.L SMG3.L --api-key "<X-API-KEY>" --start 2026-06-01
python scripts/krx_history.py            # 기본 14개 레버리지 ETF (krx-data-api 필요)
python scripts/underlying_krx.py         # 본주(삼성·하이닉스) 거래대금·시가총액 (차트 기준선)
```

### 2) AUM·NAV 수집
```bash
python scripts/lse_aum.py                                  # 런던 3x AUM 스냅샷+시계열(무토큰)
python scripts/csop_aum.py 9747 7709 --units 9747=177500000 7709=715000000   # 홍콩 2x(무토큰)
# 좌수는 한 번 넣으면 data/csop_units.json에 캐시 → 이후 `python scripts/csop_aum.py 9747 7709` 만으로 갱신
```

### 3) 환율 + 통합
```bash
python scripts/naver_fx.py USD HKD --start 2025-05-01     # (build_dataset가 없으면 자동 호출)
python scripts/build_dataset.py                            # → data/all_krw.csv (19종목 + KRW)
```

### 4) SEIBRO (한국인 보유·결제, 선택)
```bash
python scripts/seibro_daily.py --kind settlement --start 2025-05-26 --end 2026-07-03
python scripts/seibro_daily.py --kind holdings   --start 2025-05-26 --end 2026-07-03
```

### 5) 차트
```bash
python charts/make_charts.py          # 거래대금 시계열
python charts/make_aum_chart.py       # AUM 비교
python charts/make_seibro_holdings.py # 한국인 보유
```
> 일부 차트는 `data/underlying_krx_{mktcap,turnover}.csv`(본주 시총·거래대금)를 입력으로
> 쓴다 → 위 1)의 `scripts/underlying_krx.py`가 생성하므로 차트 전에 실행해 둘 것.

---

## 종목 유니버스 (19)

> ⚠️ 홍콩 7747/7709 기초종목은 자료마다 뒤바뀐다. 아래는 ISIN·종목명 검증 확정본.
> 전체·표준코드는 [tickers.csv](tickers.csv).

| 시장 | 삼성전자 | SK하이닉스 |
|---|---|---|
| **HKEX 2x** | 7747(HKD)·9747(USD) *듀얼, ISIN 공유* | 7709(HKD only) |
| **HKEX -2x** | 7347(HKD)·9347(USD) | — (없음) |
| **LSE 3x** | SMG3.L (GBP라인 3SMG) | HNX3.L (GBP라인 3HNX) |
| **KRX 2x** | KODEX/TIGER/ACE/RISE/PLUS/KIWOOM·1Q선물 (7) | 동일 7개 |

---

## 문서 색인
- [docs/SOURCES.md](docs/SOURCES.md) — 소스별 API·인증·엔드포인트·함정
- [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) — `data/` 파일 스키마
- `tickers.csv` — 종목 매핑 마스터

---

## 핵심 주의사항 (요약)
- **HKEX 타임존**: 타임스탬프 HK 자정(UTC+8) 기준 → 하루 밀림 주의(스크립트가 처리).
- **LSE JWT 5분 만료** / **HKEX 토큰 만료** → 자동화엔 API키·재캡처 필요.
- **듀얼카운터 합산 금지**: 7747·9747(삼성)은 통화만 다른 같은 펀드. AUM 이중계상 주의.
- **LSE·CSOP AUM은 JS/WAF 뒤에** → 정적 크롤 불가. 각각 `etp_data.php`·ICE로 우회(SOURCES §3,4).
- **SEIBRO 인용 시** "한국예탁결제원 증권정보포털(SEIBro)" 출처 명기 의무. 단위 USD.

## 상태 / TODO
- [x] HKEX·LSE·KRX 거래데이터 수집
- [x] KRW 통합(`build_dataset.py`)
- [x] LSE·CSOP AUM 수집(`lse_aum.py`·`csop_aum.py`, 무토큰 경로 포함)
- [x] SEIBRO 결제·보관, Naver 환율
- [x] 폴더/문서 체계화(scripts·docs·assets 분리)
- [x] 본주 시총·거래대금 자동 수집(`underlying_krx.py`, MDCSTAT01701)
- [ ] AUM 시계열을 통합본에 결합(현재 거래데이터와 별도 파이프라인)
