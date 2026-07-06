# 데이터 사전 (DATA_DICTIONARY.md)

`data/` 와 `charts/` 산출물의 **스키마·단위·생성 스크립트**. 모든 CSV는 `utf-8-sig`.
컬럼 세부·근거는 [SOURCES.md](SOURCES.md), 실행법은 [README](../README.md).

## 명명 규칙
- `<코드>_HK_hkex.csv` · `<RIC>_lse.csv` · `<코드>_KS_krx.csv` = 종목별 원본
- `*_all.csv` = 시장별 통합, `all_krw.csv` = 전시장 통합+KRW
- `*_aum*.csv` = AUM/NAV(거래데이터와 별개 파이프라인)

---

## 거래데이터 (원본, 종목별)

| 파일 | 생성 | 컬럼 | 단위/비고 |
|---|---|---|---|
| `<코드>_HK_hkex.csv` (7747/9747/7709/7347/9347) | `hkex_history.py` | Symbol, Currency, Name, ISIN, Date, Open, High, Low, Close, Volume, Turnover | 현지통화(HKD/USD). 상장일부터 |
| `<RIC>_lse.csv` (HNX3_L/SMG3_L) | `lse_history.py` | Symbol, Date, Open, High, Low, Close, Turnover | USD. **거래량 없음** |
| `<코드>_KS_krx.csv` (14개) | `krx_history.py` | Symbol, ISIN, Name, Currency, Date, OHLC, Volume, Turnover, NAV, NetAssets, IndexName, IndexClose | KRW. NAV·순자산·기초지수 포함 |

## 거래데이터 (통합)

| 파일 | 생성 | 내용 |
|---|---|---|
| `hkex_all.csv` | `hkex_history.py` | HKEX 5종목 결합 |
| `lse_all.csv` | `lse_history.py` | LSE 2종목 결합 |
| `krx_all.csv` | `krx_history.py` | KRX 14종목 결합 |
| `all_krw.csv` | `build_dataset.py` | **19종목 통합 + KRW 환산**. 컬럼: Symbol, Exchange, Underlying, Leverage, Currency, ISIN, Name, Date, OHLC, Volume, Turnover, NAV, FX_Pair, FX_Rate, {Open/High/Low/Close/NAV}_KRW |

## AUM · NAV (별도 파이프라인)

| 파일 | 생성 | 컬럼 | 비고 |
|---|---|---|---|
| `HNX3_L_aum.csv` · `SMG3_L_aum.csv` | `lse_aum.py` | Symbol, Date, NAV, AUM, Turnover, SoldShares | 런던 3x **일별 AUM 시계열**. AUM=USD |
| `lse_aum_all.csv` | `lse_aum.py` | 위 통합 | |
| `lse_aum_snapshot.csv` | `lse_aum.py` | Symbol, ShareName, Ticker, Isin, Currency, AsOf, NAV, AUM, GrossUnderlying, Liabilities, SharesOutstanding, Leverage, ArrangerFee, YTD%, Underlying | 최신 스냅샷 |
| `csop_aum_snapshot.csv` | `csop_aum.py` | Symbol, Product, Underlying, Leverage, CounterCcy, NAV, OutstandingUnits, TotalNAV, TotalNAV_USD, Source, AsOf, ISIN, MgmtFee, CSOP_URL | 홍콩 2x/-2x AUM. TotalNAV=CounterCcy, TotalNAV_USD=페그환산 |
| `csop_units.json` | `csop_aum.py` (`--units`) | {코드:{units, asof}} | 발행좌수 캐시. 삼성 177.5M·하이닉스 715M(2026-07-06) |

## 환율

| 파일 | 생성 | 컬럼 |
|---|---|---|
| `fx_USDKRW_naver.csv` · `fx_HKDKRW_naver.csv` | `naver_fx.py` | Date, Rate (매매기준율) |

## SEIBRO (한국인 보유·결제, 단위 USD)

| 파일 | 생성 | 컬럼 |
|---|---|---|
| `seibro_HK_settlement_daily.csv` | `seibro_daily.py --kind settlement` | Date, 국가명, ISIN, 종목명, 매수대금, 매도대금, 매수매도대금, 순매수대금, 종목구분 |
| `seibro_HK_holdings_daily.csv` | `seibro_daily.py --kind holdings` | Date, 국가명, ISIN, 종목명, 보관잔고금액, 종목구분 |
| `seibro_HK_*_leverage_daily.csv` | 〃 (파생) | 위와 동일, **레버리지 종목만** 필터 |

## 본주(기초자산) 데이터 — 차트 기준선

| 파일 | 생성 | 컬럼 | 비고 |
|---|---|---|---|
| `underlying_krx_turnover.csv` | `underlying_krx.py` | Date(YYYY-MM-DD), Turnover, Underlying | 삼성·하이닉스 **본주 거래대금 시계열**(KRW) |
| `underlying_krx_mktcap.csv` | `underlying_krx.py` | Underlying, Date(YYYY/MM/DD), MktCap_KRW | 본주 **시가총액 스냅샷**(최신 1행/종목). 차트가 `set_index("Underlying")`로 소비 |
| `underlying_krx_mktcap_series.csv` | `underlying_krx.py` | Underlying, Date(YYYY-MM-DD), MktCap_KRW | 시가총액 **전체 시계열**(재현·검증용, 차트 미사용) |

> 출처: `individual_price_trend`(MDCSTAT01701 개별종목시세추이) 한 화면이 거래대금·시가총액을
> 함께 제공. 본주 = 삼성전자 005930(KR7005930003) · SK하이닉스 000660(KR7000660001).

## 차트 산출물 (`charts/`)

| 파일 | 생성 | 입력 |
|---|---|---|
| `aum_comparison.png` | `charts/make_aum_chart.py` | krx_all, seibro leverage, underlying_krx_mktcap |
| `aum_vs_turnover.png` | `charts/make_bloomberg.py` | krx_all, underlying_krx_turnover |
| `turnover_timeseries.png` | `charts/make_charts.py` | hkex_all, krx_all, fx, underlying_krx_turnover |
| `seibro_hk_holdings.png` | `charts/make_seibro_holdings.py` | seibro holdings, fx, hkex_all, krx_all |

> 차트 스크립트는 `os.chdir(루트)`로 자기위치를 잡으므로 **반드시 `charts/` 바로 아래**에
> 둬야 한다(더 깊이 옮기면 루트 계산이 틀어짐).
