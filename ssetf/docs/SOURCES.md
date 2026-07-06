# 데이터 소스 기술 레퍼런스 (SOURCES.md)

각 시장·지표의 **원천 API, 인증 방식, 엔드포인트, 함정**을 한곳에 모은 문서.
스크립트가 어떻게/왜 그렇게 동작하는지의 근거. 사용법(명령어)은 [README](../README.md)에.

> 인증 원칙: 토큰·API키·비밀번호는 **절대 코드/깃에 커밋 금지**. 환경변수 또는
> 외부 `.env`로만. 캡처가 필요한 토큰은 브라우저 DevTools에서 그때그때 얻는다.

---

## 1. 홍콩 HKEX — 거래데이터 (`scripts/hkex_history.py`)

- **위젯 API**: `https://www1.hkex.com.hk/hkexwidget/data/{endpoint}` (JSONP)
  - `getchartdata2` : 일별 `[ts, O, H, L, C, Volume, Turnover]`, 상장 첫날부터
  - `getequityquote`: 정적정보 `isin, nm(종목명), ccy, nav, amt_os(발행좌수), management_fee`
- **인증**: 요청 파라미터 `token` 필요. 페이지 JS `LabCI.getToken()`가 생성 → 정적
  스크래핑 불가. **DevTools > Network** 에서 `getchartdata2`/`getequityquote` 요청의
  `token` 값을 복사. 한동안 유효, 만료 시 재캡처. 환경변수 `HKEX_TOKEN` 또는 `--token`.
- **함정 — 타임존**: 타임스탬프가 **HK 자정(UTC+8)** 기준. UTC로 읽으면 하루 밀림.
  스크립트가 `+8`로 변환.
- **함정 — 티커 매핑**: 자료마다 7747/7709 기초종목을 뒤바꿔 표기. 확정본은
  `getequityquote`의 ISIN·종목명으로 검증(→ [tickers.csv](../tickers.csv), README §종목).

## 2. 런던 LSE — 거래데이터 (`scripts/lse_history.py`)

- **위젯**: `https://refinitiv-widgets.financial.com` (LSEG/구 Refinitiv)
  - 인증 2단계: `POST /auth/api/v1/tokens` (헤더 `X-API-KEY`) → **JWT** →
    `GET /rest/api/timeseries/historical` (헤더 `jwt`)
- **인증**: `X-API-KEY`(재사용 가능, JWT 자동발급) 또는 캡처한 `JWT`(**5분 만료**).
  DevTools의 `auth/api/v1/tokens` 요청에서 `X-API-KEY` 헤더 복사. 위젯 초기화 때
  주입돼 정적 스크래핑 불가. 환경변수 `LSE_API_KEY` / `LSE_JWT`.
- **특징**: OHLC + Turnover(on book)만. **거래량 없음**(이 피드 미제공), ISIN도 없음
  (웹소켓 경유라). 야후와 달리 **상장 첫날부터** 데이터 있음.

## 3. 런던 LSE — AUM·NAV (`scripts/lse_aum.py`)  ★

HNX3/SMG3은 ETF가 아니라 **ETP(담보부 채무증권)** → Bloomberg·investing·etfdb에
AUM이 안 실린다. 이슈어 상품페이지엔 있으나 **JS로 주입**돼 정적 HTML엔 `-` 빈칸.

- **진짜 출처(백엔드)**:
  ```
  POST https://leverageshares.com/Lab_Forty_Scripts/php/etp_data.php
  Content-Type: application/json
  body: {"name":"<슬러그>","documentLocaleType":"en-eu"}
  ```
  슬러그 = 상품페이지 URL의 path segment[3].
  - HNX3 = `leverage-shares-3x-long-sk-hynix-etp`
  - SMG3 = `leverage-shares-3x-long-samsung-electronics-etp`
- **응답 핵심 필드**:
  - `Etp[0].etp_securities_issued` = 상품페이지가 **'AUM'으로 표기**하는 값(순 AUM, USD)
  - `value_underlying_assets` = 기초자산 총액(3x 총 익스포저 ≈ AUM×3)
  - `liabilities`(마진론), `Outstanding_Shares_Par`(발행좌수), `price`(NAV)
  - `Usd[]`/`Gbp[]` = 통화별 **일별 시계열**(date, price=NAV, etp_securities_issued=그날
    AUM, turnoverBaseCurrency, SoldShares). USD 상장라인=`Usd`, GBP라인(3HNX/3SMG)=`Gbp`,
    `Eur`는 비어있음.
- **인증**: 없음(무토큰).

## 4. 홍콩 CSOP — AUM·NAV (`scripts/csop_aum.py`)  ★

`Total NAV(AUM) = 단위당 NAV × 발행좌수`. 두 조각의 출처가 소스별로 다름.

- **왜 csopasset.com 직접 스크래핑 불가**: 'Total NAV' 값은
  `/asset/lai/js/<slug>.js`가 렌더 후 주입 + 그 `/asset/lai/` 경로 전체가 **WAF로 차단**
  (비브라우저 요청은 `/en/home`으로 302, Googlebot도 403). 헤드리스 브라우저 없이는 불가.

- **`--source ice` (기본, 무토큰)** — 단위당 NAV를 ICE iNAV 공개 API에서:
  ```
  GET https://inav.ice.com/api/1/csop/application/index/quote?symbol=<코드>&language=en
  ```
  - 인증/쿠키 **불필요**(응답에 Authorization 없음. `__cf_bm`은 Cloudflare 봇쿠키일 뿐).
  - 응답: `INTRA_DAY_ESTIMATED_NAV_PER_UNIT`, `INTRA_DAY_MARKET_PRICE` (통화별).
    삼성(7747/9747)은 **USD·HKD 둘 다**, 하이닉스(7709)·인버스는 **HKD만**.
  - **ICE는 iNAV 계산 대행사**일 뿐, 상장지(HKEX)와 무관. CSOP가 ICE를 고용한 것.
    다른 발행사는 Solactive/Bloomberg 등 다른 대행사일 수 있음.
  - **발행좌수는 ICE에 없음** → `--units 7747=177500000` 로 주거나 캐시
    (`data/csop_units.json`)/`DEFAULT_UNITS` 시드 사용. 좌수는 설정/환매로 변동하니
    가끔 CSOP 페이지에서 읽어 갱신.

- **`--source hkex` (토큰)** — `getequityquote`가 `nav`·`amt_os`(좌수)를 한 번에 →
  `Total NAV = nav × amt_os`. §1과 같은 위젯·`HKEX_TOKEN`. 좌수까지 자동.

- **듀얼카운터 합산 금지**: 삼성 2x는 **한 펀드**, 7747(HKD)·9747(USD)은 통화만 다른
  같은 값(좌수 공유). 더하면 이중계상. 하이닉스 2x(7709)는 HKD 카운터만.
- **검증**(2026-07-03): 9747 NAV 17.67 × 177,500,000좌 = 3,135,908,512 USD = CSOP 공시.
- **CSOP URL slug**: 삼성2x=`hk-smsn-2l`, 하이닉스2x=`hk-skhy-2l`, 삼성인버스=`hk-smsn-2i`.

## 5. 한국 KRX — 거래데이터·NAV (`scripts/krx_history.py`)

- **로컬 레포 `krx-data-api`** 사용(`C:\Users\Peter\github\krx-data-api`, `pip install -e .`).
  인증: 레포 `.env`의 `KRX_ID`/`KRX_PW`로 자동 로그인(`auth=True`).
- 두 endpoint:
  - `etf_all_info` (MDCSTAT04601): 전종목 ETF 기본정보 → **단축코드↔표준코드(ISIN)**·운용사·추적배수
  - `etf_price_trend` (MDCSTAT04501): 개별 시세추이 → OHLCV+거래대금+**NAV**+순자산총액+기초지수
- 참고: 주식화면 `individual_price_trend`(MDCSTAT01701)도 OHLCV는 나오나 **NAV 없음** →
  ETF 전용 화면 사용.

### 5-1. 본주(기초자산) 시총·거래대금 (`scripts/underlying_krx.py`)
- 같은 레포의 `individual_price_trend`(MDCSTAT01701 개별종목시세추이) 사용. 이 한 화면이
  일자별 **거래대금 + 시가총액**을 함께 줌(required: `isuCd, strtDd, endDd`).
- 본주: 삼성전자 005930=`KR7005930003`, SK하이닉스 000660=`KR7000660001`. `adjusted_price=False`
  (원주가; 구간 내 분할 없어 수정주가와 동일). 산출은 DATA_DICTIONARY '본주 데이터' 참고.

## 6. 환율 — Naver 매매기준율 (`scripts/naver_fx.py`)

- `https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd=FX_{CUR}KRW`
  iframe 표를 페이지네이션. 값은 **매매기준율**. 인증 없음. 파싱에 `lxml` 필요.

## 7. SEIBRO — 한국인 해외종목 결제/보관 (`scripts/seibro_daily.py`)

- `https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp` (WebSquare, XML)
  국가=HK. 영업일마다 단일일 1콜로 일별 시계열 구성. 공휴일=빈 응답→스킵.
- `--kind settlement`: 결제대금(매수/매도/합계/순매수), **결제완료일(T+2)** 기준
- `--kind holdings`: 보관잔고 스냅샷(최근 1~2일 지연)
- **단위 USD**. 인용 시 **"한국예탁결제원 증권정보포털(SEIBro)" 출처 명기 의무**.
- 레버리지 종목만 추린 `*_leverage_daily.csv`도 함께 생성(내부 ISIN 매핑).

## 8. (레거시) Yahoo Finance — `archive/yahoo_history.py`

네이티브 소스로 전환하며 폐기. 함정 기록용:
- 신규종목에 `range=max`가 일봉을 **1시간봉으로 강등** → `--start`로 회피.
- **LSE 상장 첫 주(2026-06-12~19)를 통째로 누락** → 네이티브 전환의 직접 계기.

---

## 부록 — ISIN 조회 경로
Yahoo·OpenFIGI(티커→ISIN)로는 안 됨. HKEX=`getequityquote`가 직접 제공, KRX=MDCSTAT04601,
LSE=상품페이지/justETF. 듀얼카운터 7747·9747은 **같은 ISIN**(HK0001121349, OpenFIGI 역방향 확인).
