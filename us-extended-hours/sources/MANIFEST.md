# sources/ — **1차 출처 원문 보존**

> **[← 목차](../README.md)** · 수집 기준일 **2026-07-13** · 재현: [`fetch_sources.py`](fetch_sources.py)

**이 폴더의 목적**: 보고서의 모든 인용을 **원문으로 되짚을 수 있게** 하는 것. 링크는 썩고, SEC는 스크립트를 차단하고, 채용공고는 내려간다. **인용의 근거는 여기 있다.**

---

## A. SEC 규칙제정 문서 (연방관보 전문)

| 파일 | 릴리스 / 파일번호 | 일자 | 무엇을 인용하나 |
| --- | --- | --- | --- |
| ★★★ [`34-105199_nasdaq-23-5-approval.txt`](34-105199_nasdaq-23-5-approval.txt)<br>(119,805자) | **34-105199**<br>SR-NASDAQ-2025-109 | **2026-04-10** | **나스닥 23/5 승인문.** 이 조사의 **가장 중요한 문서** → 전용 해부: **[D1](../D1-34-105199.md)**<br>· **각주 92** (공시 창을 "7:00 a.m.–8:00 p.m."로 못 박은 문장)<br>· **각주 68** (야간 인력 약속)<br>· *"All NMS Stocks would be eligible"*<br>· *"build industry-wide consensus … volatility moderators"*<br>· *"already able to trade during that time"* (SEC 승인 논거)<br>· ★ **`LULD` 0회 · `MarketWatch` 1회** — 직접 검증 가능 |
| ★★ [`34-105860_nasdaq-corporate-action-halts.txt`](34-105860_nasdaq-corporate-action-halts.txt)<br>(52,960자) | **34-105860**<br>SR-NASDAQ-2026-057 | **2026-07-08**<br>(관보 07-13) | **야간 기업행위 강제정지.** 21:00 전 정지 → 익일 08:00 Halt Cross 재개<br>· *"will no longer have an overnight trading pause during which it can process corporate actions"*<br>· *"pause … primarily … maintenance … **rather than** … coordinated processing"*<br>· ★ **`news`·`MarketWatch` 0회** |
| ★★ [`34-105596_luld-27th-overnight-bands.txt`](34-105596_luld-27th-overnight-bands.txt)<br>(57,262자) | **34-105596**<br>File **4-631** | **2026-06-01**<br>(⚠ **승인 전**) | **LULD 제27차 — 야간 ±20% 가격밴드.** 전 참가자 **만장일치**<br>· *"determined **not to implement automatic Trading Pauses**"*<br>· *"**similar to ATSs** … (ATSs simply reject orders that fall outside their bands)"*<br>· ★ **`news`·`MarketWatch` 0회** |

⚠ **SEC PDF(sec.gov)가 아니라 연방관보(Federal Register) 전문이다.** 같은 문서이고, SEC 서버는 스크립트 접근을 차단한다. **인용 시 릴리스 번호를 쓸 것.**

---

## B. 거래소 공식 문서

| 파일 | 무엇 | 무엇을 인용하나 |
| --- | --- | --- |
| ★★ [`nyse_extended-hours-FAQ_v3.0_2026-05.pdf`](nyse_extended-hours-FAQ_v3.0_2026-05.pdf) · [.txt](nyse_extended-hours-FAQ_v3.0_2026-05.txt) | **NYSE Extended-Hours FAQ v3.0** (2026-05) | ★ *"the plan is for **all other NYSE Group equities exchanges to continue to operate within their current trading hours**"* ← **NYSE 본체가 연장 안 한다는 유일한 공식 문장**<br>· *"LULD rules apply **only during the Core Session**"*<br>· 기업행위 정지 **"논의 중"** 자인<br>· 개시 목표 **2026-12-06**<br>⚠ **이 문장은 2024-10 ICE 보도자료에는 없다. 출처를 FAQ로 달 것** |
| ★★★ [`nyse_rule-7.34_trading-sessions_current.txt`](nyse_rule-7.34_trading-sessions_current.txt) | **NYSE Rule 7.34 현행 원문**<br>(nyseguide.srorules.com, 2026-06-30 빌드) | ★★ *"All orders in **Exchange-listed securities** are deemed designated for the **Core Trading Session only**."*<br>· *"The Exchange will have **two trading sessions**"*<br>· *"**Only UTP Securities** are eligible to trade in the Early Trading Session"*<br>→ **NYSE 상장종목은 자기 거래소에서 정규장 밖에 거래될 수 없다** (**[B0](../B0-what-happened.md) §B0-3**)<br>⚠ **이전 조사가 쓴 룰북 PDF는 2019년 스냅샷이었다. 이것이 현행본이다.** |
| ★★★ [`nasdaq_global-trading-hours-FAQ.txt`](nasdaq_global-trading-hours-FAQ.txt) | **나스닥 자체 23/5 고객 FAQ**<br>(nasdaq.com/24-hour-trading-hub) | ★★★ **`news` 0회 · `MarketWatch` 0회 · `disclosure` 0회.** `halt` 4회는 **전부 기업행위**<br>· **야간 정지 대상 기업행위 전체 목록** (아래)<br>· 정지코드 **`M1`**<br>· 밴드 최소값: **$3.00** (OCP<$1.00이면 **$1.00**) |
| [`nasdaq_marketwatch-surveillance-page.txt`](nasdaq_marketwatch-surveillance-page.txt) | 나스닥 MarketWatch 소개 페이지 | MarketWatch = **공시 데스크**임을 나스닥이 설명 |
| [`nasdaqtrader_marketwatch-hours.html`](fetch_sources.py) *(재수집)* | nasdaqtrader.com MarketWatch | ★ *"business hours … **4:00 a.m. to 8:00 p.m. ET**"* · *"implements trading halts from **7:00 a.m. – 8:00 p.m.**"*<br>⚠ **23/5 승인 3개월 뒤에도 야간 언급 0회** |

### ★ 나스닥 FAQ가 밝힌 **야간 정지 대상 기업행위 전체 목록** (정지코드 `M1`)

> 21:00 **전에** 정지 → **익일 08:00** 재개

- **종목코드·CUSIP 변경**
- **직전 종가의 25% 이상 배당**
- **액면분할·액면병합** (Forward and Reverse Splits)
- **De-SPAC**
- **회사분할** (Spin-off)
- **증권 종류 변경** (예: 우선주 → 보통주)
- **합병·강제교환** (Merger/Mandatory exchange)
- ⚠ **"그 밖에 공정·질서 있는 시장, 투자자 보호, 공익을 위해 거래소가 정지가 필요하다고 판단하는 모든 기업행위·사건"** ← **포괄 재량 조항**

---

## C. 채용공고 (야간 인력의 실체)

| 파일 | 공고 | 왜 중요한가 |
| --- | --- | --- |
| ★★★ [`jobs_NYSE-Regulation_extended-hours-analyst.txt`](jobs_NYSE-Regulation_extended-hours-analyst.txt) | **Analyst, Initial Listings and Extended Hours Trading, NYSE Regulation**<br>2026-07-08 게시 · **20:00–04:00** · **$92,000–108,000** | ★ *"**Review and analyze global news to identify material news**…"*<br>· *"**Review and analyze press releases for materiality that may necessitate a trading halt.**"*<br>→ ⚠ **"야간 뉴스감시를 하는 미국 거래소는 없다"를 반박하는 증거** (**[B2](../B2-disclosure-halts.md) §B2-4b**) |
| [`jobs_NYSE_trading-operations-overnight.txt`](jobs_NYSE_trading-operations-overnight.txt) | **Analyst, Trading Operations** · 2026-05-22 · 20:00–04:00 | **운영직**(공시 아님). NYSE가 야간 인력을 쌓고 있다는 방증 |

### ⚠ 나스닥 채용공고는 Workday **JSON API**로만 확보된다 (SPA)

[`fetch_sources.py`](fetch_sources.py) 의 `nasdaq_jobs()` 참조. **검색어 `MarketWatch` → 총 2건** (2026-07-13):

| 공고 | 소속 | 근무시간 |
| --- | --- | --- |
| **Senior Manager – MarketWatch** (R0026194, 2026-06-18) | Nasdaq **MarketWatch** | ### ⚠ **야간 언급 0회** |
| **Extended Hours Surveillance Analyst** (R0025371, 2026-05-20) | **Market Surveillance** | **20:00–04:00 명시** |

> ### **나스닥은 야간 인력을 뽑을 땐 시간을 명시한다. MarketWatch를 뽑을 땐 안 한다.** → **[B2](../B2-disclosure-halts.md) §B2-4a**

---

## D. 자체 수집 데이터

| 경로 | 내용 |
| --- | --- |
| **[`../data/`](../data/)** | **NYSE 공개 halt API 24개월치 원자료** (26,388행, 2024-07~2026-06). 수집 [`fetch_halts.py`](../data/fetch_halts.py) · 집계 [`analyze_halts.py`](../data/analyze_halts.py) |

---

## E. ⚠ 확보하지 못한 것

| # | | 왜 |
| --- | --- | --- |
| ~~1~~ | ~~**NYSE 사전통보 시간대 (07:00–16:00) 현행 확인**~~ | ✅ **해결됨.** 별도 조사 [`us_comparison/nyse/04_nyse_disclosure_requirements.md`](../../../us_comparison/nyse/04_nyse_disclosure_requirements.md) (2026-04, **NYSE 2026 Annual Guidance Letter** 기반)가 확인해 준다 — 아래 **F절** |
| 2 | **나스닥 IM-5250-1 현행 룰북 원문** | listingcenter가 SPA. **다만 조문 시각은 34-105199 각주 92에 그대로 인용돼 있다** |
| 3 | **nasdaqtrader.com "excluded securities" 목록 (실물)** | ⚠ **여전히 미확보** — 공개 URL로 접근되지 않는다 (`/Trader.aspx?id=ExcludedSecurities`, `/dynamic/symdir/excluded.txt` 모두 **"Page Not Available"** 소프트 404. ⚠ HTTP 200을 돌려주므로 상태코드만 보면 속는다)<br>✅ **그러나 위험은 해소됐다** — **규정 원문 확보**로 이 목록이 **나스닥 상장종목에 미칠 수 없음**이 확인됐다. → **[B1](../B1-universe.md) §B1-4a** |
| ~~4~~ | ~~**Cboe EDGX 야간 승인 SEC 1차 문서**~~ | ✅ **해결됨 (2026-07-14).** **Rel. 34-105587 · SR-CboeEDGX-2026-019 · 관보 2026-06-03** — *"Order Granting Accelerated Approval … 23 Hours per Day, Five Days per Week"*. **Overnight Session 21:00 개시.** → **"4개 거래소 승인"이 맞다** |
| 5 | **MarketWatch / NYSE Market Watch 부서 인원** | **어느 해도 공개된 적 없다.** "1인당 종목 수" 검증 불가 |

---

## F. ★★ 외부 교차검증 — **NYSE 공시·통보 의무** (구멍 #1 해결)

**출처**: 같은 사용자의 별도 조사 [`us_comparison/nyse/04_nyse_disclosure_requirements.md`](../../../us_comparison/nyse/04_nyse_disclosure_requirements.md) (2026-04 작성)
**근거**: NYSE Listed Company Manual **§201·§202** · ★ **NYSE 2026 Annual Guidance Letter**

> ### **본 보고서의 NYSE 관련 주장 네 가지를 독립적으로 확인해 준다. 전부 일치한다.**

| 본 보고서의 주장 | 교차검증 결과 | ✓ |
| --- | --- | --- |
| **사전통보 창 = 07:00–16:00** | *"거래시간 중 공시(**7:00 AM ~ 4:00 PM ET**) — Market Watch 팀에 **전화**, 공시 **최소 10분 전**"* | ✅ |
| ★ **그 밖의 시간엔 통보 의무 없음** | *"거래시간 외(**4:00 PM 이후, 7:00 AM 이전**) — **전화 통지 일반적으로 불필요**. 서면 사본 제출만"* | ✅ **핵심 확인** |
| ★ **배당·주식분배만 예외** | *"**예외: 배당/주식 배분** — 거래시간 외에도 **반드시 10분 전** 사전 통지 필요"* | ✅ (SR-NYSE-2017-17과 일치) |
| **뉴스정지는 09:25–16:00 직권** | *"**9:25 AM ~ 4:00 PM** — NYSE 직권 / **7:00 AM ~ 9:25 AM** — **회사 요청 시에만**"* | ✅ |

> ## ### **→ NYSE의 사전통보 시간대는 야간으로 확대되지 않았다. 16:00 이후에는 회사가 전화할 의무가 없다 (배당·분배 제외).**
>
> ### **§3(공시부담)의 마지막 구멍이 메워졌다.** → **[B2](../B2-disclosure-halts.md) §B2-3** · **[B6](../B6-unresolved.md)**

**덤으로 확인된 것 — §202.06 장 마감 후 공시 제한:**

> **16:00 정규장 종료 ~ 공식 종가 게시(대개 16:05) 사이에는 중요정보 공시가 금지된다.**
> 목적: *"타 시장 거래 가격과 NYSE 종가 간 괴리로 인한 혼란 방지"*

> ⚠ **이것을 "미국은 투자자가 소화하도록 마감 후 발표를 권장한다"의 근거로 쓰면 안 된다.** **목적은 종가 단일가매매 보호다.** → **[C1](../C1-implications-krx.md) §C1-8**
