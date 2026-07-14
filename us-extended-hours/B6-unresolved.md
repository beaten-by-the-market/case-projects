# B6. 아직 안 풀린 것: **미국도 답을 못 냈다**

> **[← 목차](README.md)** · 선행: **[B5. 주체별 입장](B5-positions.md)** · 다음: **[C1. 코스닥 시사점](C1-implications-krx.md)**

---

## 한 문장

> ## **개시가 5개월 남았다. 인프라(청산·시세)는 풀렸다. 그런데 새벽에 악재가 터지면 거래소가 그것을 알 방법이 없고, 가격이 무너지면 무엇이 막는지도 정해지지 않았다.**
>
> ### **기업행위는 답이 나왔다 — 그리고 그 답은 "밤새 거래시키지 않는다"였다.**

---

## B6-1. ★★ 미해결 목록

| # | 미해결 쟁점 | 현재 상태 | 근거 |
| --- | --- | --- | --- |
| **1** | ★★ **새벽 2시에 악재가 터지면 거래소가 그것을 어떻게 아는가** | ❌ **통보 경로 없음.** 회사의 사전통보 창은 **07:00–20:00 그대로**. 거래소는 **정지 권한도 야간 전담팀도 있지만**, 악재를 **미리 알 방법이 없다** | [B2](B2-disclosure-halts.md) |
| **2** | **어떤 기업행위에 야간 정지를 걸 것인가** | ✅ ⚠ **나스닥은 2026-07-08 확정** (SR-NASDAQ-2026-057). 방식은 ★ **"21:00 전 강제정지 → 익일 08:00 재개" = 밤새 거래시키지 않는다.** **NYSE·Cboe 조화 개정은 미제출** | [B2](B2-disclosure-halts.md) §B2-2b |
| **3** | **가격이 무너지면 무엇이 막는가** | ⚠ **밴드는 생겼다 — 정지는 없다.** LULD 제27차 개정(2026-06-01, 만장일치, **승인 전**)이 야간 **±20% 밴드** 신설. ★ **그러나 자동 거래정지(Trading Pause)는 명시적으로 도입하지 않았다.** 그리고 그 밴드는 **Blue Ocean ATS를 베낀 것** | [B3](B3-volatility.md) §B3-0 |
| **4** | **SIP 통합시세** | ✅ **SEC 승인 완료. 2026-12-06 시행 확정** (⚠ 더 이상 "미해결"이 아니다) | [B4](B4-infrastructure.md) |
| **5** | **야간 OTC 체결의 실시간 보고** | ❌ **익일 04:15 보고.** SIFMA가 경고한 "2단 투명성"이 현실화 | [B4](B4-infrastructure.md) |
| **6** | **누가 비용을 대는가** | ❌ **SIFMA 질문. 답 없음** | [B5](B5-positions.md) |
| **7** | **증거금** | ⚠ 야간 마진콜 처리 미정 | SIFMA 쟁점 3 |
| **8** | **거래소 배상책임 한도** | ⚠ SIFMA: *"the liability caps are **woefully inadequate**"* ⚠ **금액은 쓰지 말 것 — "월 $500k"의 1차 출처를 확인하지 못했다** | SIFMA |

> ## ★★ **2번이 이 보고서에서 가장 중요한 갱신이다**
>
> **나스닥은 "야간에 기업행위 정지를 어떻게 걸 것인가"에 답을 냈다. 그 답이 "안 건다 — 그 종목을 밤새 거래시키지 않는다"였다.**
>
> ### **"미국은 시간을 늘릴 때 반드시 무언가를 포기했다"의 네 번째 사례다.**
>
> | | 포기한 것 |
> | --- | --- |
> | **NYSE** | 자기 상장종목의 애프터 **세션 전체** |
> | **Nasdaq** | 야간 **공시 사전통보 의무 전체** |
> | **SEC** | **LULD·서킷브레이커 전체** |
> | ★ **Nasdaq (2026-07)** | **기업행위 종목의 야간거래 전체** |

---

## B6-2. 1번을 정확히 이해할 것: **없는 것은 "주체"가 아니라 "통보 경로"다**

> ### ⚠ **먼저 오해를 걷어낼 것.**
>
> **나스닥은 야간세션에 "실시간 감시·명백한 오류 처리·필요시 거래정지를 집행할 전담팀"을 두겠다고 SEC 승인문(Rel. 34-105199)에 명시했고, 실제로 채용 중이다**([B2](B2-disclosure-halts.md) §B2-3·§B2-4).
>
> ### **따라서 "정지를 걸 주체가 없다"는 틀렸다. 정지 권한도 사람도 있다.**
>
> ### **없는 것은 회사가 악재를 알려줄 의무 — 즉 정지의 근거가 거래소에 도착하는 경로다.**

**나스닥 Rule 4120(a)(10)(D)** (야간세션에 대한 유일한 *조문상* 정지 근거):

> "**If the primary listing market determines to halt trading** … the Exchange will halt trading … until trading resumes on the primary listing market."

### 나스닥 상장종목의 경우

```
새벽 2시, 나스닥 상장종목에 악재 발생
  ↓
회사의 사전통보 의무? → ❌ 없다 (창은 07:00–20:00 그대로)
  ↓
조문상 정지 근거 4120(a)(10)(D) = "상장거래소가 정지하면 따른다"
  ↓
그런데 나스닥 상장종목의 상장거래소 = 나스닥 자신 → 조문이 순환한다
  ↓
남는 것: 야간 전담팀의 순수 재량
  ↓
⚠ 정지는 걸 수 있다. 그러나 뉴스가 시장에 이미 퍼져
   가격이 무너지는 것을 보고 나서야 알 수 있다 (사후 감시)
```

### NYSE 상장종목의 경우 — **더 심하다**

```
새벽 2시, NYSE 상장종목이 NYSE Arca 야간세션에서 거래 중
  ↓
상장거래소 = NYSE 본체
  ↓
NYSE의 공시 사전통보 "의무" 창 = 07:00–16:00
NYSE의 공표된 재량 뉴스정지 절차 = 09:25–16:00 (07:00–09:25는 회사 요청 시만)
  ↓
⚠ 16:00 이후: 회사에 통보 의무가 없다
   ("not required to provide advance notice … but are encouraged
     to email a courtesy copy")
  ↓
❌ 그래서 NYSE도 야간 악재를 미리 알 경로가 없다
```

> ## ⚠⚠ **"NYSE는 16:00 이후 뉴스정지 기능이 아예 없다"고 쓰지 말 것 — 우리 데이터가 반박한다.**
>
> **우리가 집계한 24개월 원자료에 NYSE 상장종목의 16:00 이후 뉴스정지가 32건(147건 중 21.8%) 있고, 그중 9건은 `News pending` 정지 *개시*다.** 기능이 없는 게 아니라 **의무가 없는 것**이다.
>
> ⚠ **예외도 먼저 밝힐 것**: **배당·주식분배 통보는 시간 제한이 없다** — *"including when such announcement is being made **outside of Exchange trading hours**"* (SR-NYSE-2017-17). **"NYSE는 장 끝나면 아무것도 안 받는다"는 틀렸다.**

> ### ★ **그래도 구조적 공백은 남는다: 세션을 운영하는 거래소(NYSE Arca)는 상장거래소가 아니고, 상장거래소(NYSE 본체)는 그 시간에 회사로부터 공시를 받을 의무를 지우지 않는다.**

### 이미 걸린 정지는 이어진다 (부분적 해결)

| 상황 | 처리 |
| --- | --- |
| **장 마감 전에 걸린 정지** → 야간세션으로 이어짐 | ✅ **처리된다.** Nasdaq 4120(a)(10)(D) · Blue Ocean도 동일: *"if trading in a security has been halted by an exchange … the ATS will not trade that security in its immediately ensuing trading session"* · **FINRA Rule 5260**(정지 중 거래·호가 금지)에 시간대 예외 없음 |
| **야간 중 새로 발생한 사건** | ❌ **사전통보 경로 없음.** 거래소 재량에 의한 **사후 감시**뿐 |

> **우리 실측에 따르면 나스닥은 연 839건의 뉴스형 정지를 19:50(애프터 종료 10분 전)에 걸어 다음날 아침 09:00까지 유지한다** ([B2](B2-disclosure-halts.md) §B2-6). **그 정지들은 야간세션이 열려도 유효하다. 문제는 새로 거는 것이다.**

---

## B6-3. 2번: 기업행위 정지 — **거래소들이 공식 인정한 미해결**

**NYSE Extended Hours FAQ v3.0 (2026-05) 원문:**

> "The listing exchanges (NYSE, Nasdaq, and Cboe) **are working together, in consultation with SIFMA, to identify complex Corporate Actions that will be halted in the Overnight Trading Session.** Those exchanges **are working on harmonized rule Amendments** to this effect."

> ### ⚠ **그러나 이것은 2026-05 시점의 상태다. 두 달 뒤 나스닥이 먼저 답을 냈다.**

**SR-NASDAQ-2026-057 (Rel. 34-105860, 2026-07-08, 즉시효력):**

> *"the Exchange would implement a **mandatory regulatory halt in that security before the start of the Night Session at 9:00 p.m. ET**, and trading would **resume with a Nasdaq Halt Cross at 8:00 a.m. ET**"*

| | |
| --- | --- |
| **나스닥** | ✅ **확정.** 방식 = **야간 배제** |
| **NYSE · Cboe** | ⚠ **조화 개정 미제출** |

> ### **"어떤 기업행위에 정지를 걸 것인가"의 답은 "정지를 거는 게 아니라, 그 종목을 야간에 아예 안 열어둔다"였다.**

**참고: 코스닥은 이 문제를 이미 실측했다.** 매매거래정지 910건 중 **집행형(주식병합·분할 전자등록, SPAC 소멸합병) 306건의 99.7%가 애프터 시간대**다 ([REPORT 부록 D](../kosdaq-afterhours/REPORT.md#부록-d-거래정지-사건-분류-재현용)). **미국이 지금 "어떤 것을 멈출까" 고민하는 목록이 대체로 이것이다.**

---

## B6-4. 3번: 가격 통제 — **"업계 합의를 만드는 중"**

**나스닥이 SEC에 낸 문장:**

> "The Exchange would also implement measures to safeguard against trade executions that are clearly erroneous **while it works to build industry-wide consensus on proposals for establishing uniform after-hours volatility moderators.**"

**NYSE FAQ:**

> "market participants and exchanges **are discussing** a possible extension of industry-wide LULD-like volatility controls that **could eventually apply** during the Overnight Session."

> ### **두 거래소 모두 "아직 없다, 논의 중이다"라고 공식 문서에 썼다. 그리고 SEC는 그 상태로 승인했다.**
>
> ⚠ **아이러니**: **Blue Ocean ATS는 ±20% 가격밴드가 있다.** 승인된 정규거래소 야간세션에는 없다. → [B3](B3-volatility.md) §B3-4

---

## B6-5. ★ 이 문서가 코스닥에 주는 것

### ① **"미국이 어떻게 하나 보고 따라가자"는 전략이 지금은 성립하지 않는다**

> ### **미국은 아직 안 열었다. 그리고 핵심 질문들에 답을 못 냈다.**
>
> **KRX가 애프터를 이미 운영하고 있다면, 이 질문들에 미국보다 먼저 답해야 하는 위치에 있다.**

### ② ★ 우리가 미국보다 앞서 있는 것

| | **미국** | **코스닥 (우리 연구)** |
| --- | --- | --- |
| **어떤 공시가 애프터에 몰리는가** | 실측 없음 (거래소가 통계를 공표하지 않음) | ✅ **수시공시 71,972건 중 58.2%가 15:40~20:00** |
| **어떤 정지를 즉시 걸어야 하는가** | ❌ **"논의 중"** | ✅ **뉴스형 604건 vs 집행형 306건으로 분류 완료** ([부록 D](../kosdaq-afterhours/REPORT.md#부록-d-거래정지-사건-분류-재현용)) |
| **그 부담이 어느 종목에 쏠리는가** | 실측 없음 | ✅ **거래대금 1조원당 뉴스형 정지: D10이 D1의 161배** |
| **가격충격이 얼마나 되는가** | BH2004(2000년 데이터) · Eaton 2025 | ✅ **Amihud: D10은 1억원에 1.65%** |

> ### **미국이 "논의 중"인 질문 중 상당수를, 우리는 이미 데이터로 답해놨다. 그것이 이 연구의 강점이다.**

### ③ ⚠ 그리고 미국의 미해결이 우리에게 던지는 질문

| # | 미국의 공백 | **한국은 답이 있는가** |
| --- | --- | --- |
| 1 | **애프터 중 새로 발생한 사건에 누가 정지를 거는가** | KRX는 애프터에 실시간 정지를 걸 것인가? 걸 인력이 있는가? |
| 2 | **어떤 기업행위에 애프터 정지를 걸 것인가** | ✅ 우리는 목록이 있다 (부록 D). **그러나 KRX가 확정했는가?** |
| 3 | **애프터에 가격제한이 있는가** | ⚠ **확인 필요.** 미국은 없다 |
| 4 | **애프터 시세가 공적으로 통합·배포되는가** | ⚠ **확인 필요.** KRX+NXT 통합시세 체계 |
| 5 | **애프터 체결이 종가·지수·NAV에 반영되는가** | ⚠ **확인 필요.** 미국은 `T` 조건으로 **제외**한다 |

> **3~5번은 이번 조사 범위 밖이다. KRX 내부 설계 문서를 봐야 한다. 그러나 미국 사례가 이 질문들이 중요함을 보여준다.**
