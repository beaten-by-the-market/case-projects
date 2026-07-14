# B4. 쟁점 4 — 인프라 전제조건: **SEC가 실제로 건 유일한 조건**

> **[← 목차](README.md)** · 선행: **[B3. 가격 안전장치](B3-volatility.md)** · 다음: **[B5. 주체별 입장](B5-positions.md)**

---

## 한 문장

> ## **SEC는 유동성 게이트도, 가격제한도, 공시심사도 요구하지 않았다. 딱 하나를 요구했다: "통합시세(SIP)가 그 시간에 시세를 배포할 수 있을 때까지 열지 마라." 그 조건 하나 때문에 승인 20개월이 지난 지금도 아무도 열지 못하고 있다.**

---

## B4-1. ★★ SEC가 세 거래소 모두에 건 동일한 조건

**24X · Nasdaq · NYSE Arca 승인문 셋 모두에 같은 문장이 들어 있다.**

**SEC Release 34-101777 (24X) 원문:**

> "Pursuant to its amended Form 1, **24X will not operate during the 24X Market Session until the Equity Data Plans are able to collect, consolidate, process and disseminate quotation and transaction information at all times during the session.**"

### 메커니즘 (24X Rule 1.5(c) · 11.16)

| 단계 | 내용 |
| --- | --- |
| 1 | 야간세션 개시 **전에** 별도의 **§19(b) 규칙제정**("24X Market Session Proposed Rule Change")을 제출해야 한다 |
| 2 | 그 제출에서 **Equity Data Plans(CTA/CQ·UTP SIP)가 정규장과 동등한 수준으로 시세를 배포할 수 있음**을 확인해야 한다 |
| 3 | **"24X will not commence operations of the 24X Market Session until a proposed rule change as required under 24X Rule 1.5(c) has been approved, or has otherwise become effective."** |
| 4 | ★ **18개월 조항**: 승인 후 18개월(= **2026-05-27**) 내에 제출하지 못하면, **24X는 야간세션 규정을 스스로 삭제하는 규칙제정을 제출해야 한다** |

> ⚠ **정확히 표현할 것**: SEC가 규정을 "무효화"하는 게 아니라, **거래소가 스스로 삭제 신청을 해야 하는 의무**다.

**NYSE Arca Rule 7.34-E(T) 전문(前文)도 같다:**

> "the Exchange **shall not commence operation of Extended Hours Trading … unless the Equity Data Plans (1) have established a mechanism to collect, consolidate, process and disseminate quotation and transaction information at all times during Extended Hours Trading**…"

---

## B4-2. 왜 SIP가 없으면 안 되는가

| 시간대 | 통합시세(NBBO) | 통합체결(Tape) |
| --- | --- | --- |
| **04:00–20:00** (현행) | ✅ 배포 | ✅ 배포 |
| **20:00–04:00** | ❌ **없음** | ❌ **없음** |

**오늘 야간에 일어나는 거래(Blue Ocean 등 ATS)는 공적 통합시세 인프라에 실시간으로 보이지 않는다.**

### SIP가 없으면 연쇄적으로 무너지는 것들

| # | 무너지는 것 | 이유 |
| --- | --- | --- |
| 1 | **최선집행의 벤치마크** | FINRA 5310의 5개 판단요소 중 하나가 **"accessibility of the quotation"** 인데, 호가 자체가 없다 |
| 2 | **ETF 차익거래** | 지수값·IIV(실시간 순자산가치 추정)가 배포되지 않는다. 나스닥 규정(Equity 2 §20)은 이를 **고객에게 고지하라고 요구**: *"The absence of an updated underlying index value or intraday indicative value is an **additional trading risk in extended hours** for Derivative Securities Products"* |
| 3 | **Reg SHO 공매도 규제** | Rule 201의 제한은 **"NBB가 배포되는 동안"** 만 작동한다. NBB가 없으면 **자동으로 꺼진다** |
| 4 | **이상 체결가의 공적 대조 기준** | 야간의 이상 체결을 대조할 통합 기록이 없다 |

> ### ★ **SEC가 24X에 허용한 것 하나가 이 구조를 잘 보여준다.**
>
> **24X는 최초 위험고지 문구에 "통합 시세가 없을 수 있다"는 항목을 넣었다가, SEC가 그것을 삭제하도록 허용했다.** 이유: **Rule 1.5(c)가 SIP 배포를 보장하므로 그 고지가 불필요해졌기 때문이다.**
>
> **즉 SEC는 "통합시세 없이 여는 것"을 아예 상정하지 않았다.**

---

## B4-3. ★ 그래서 지금 어디까지 왔나

| 인프라 | 상태 |
| --- | --- |
| **NSCC 청산 (DTCC)** | ✅ **SEC 승인 2026-05-27** (SR-NSCC-2026-006, Rel. **34-105565**) · **2026-06-28 24x5 가동** (일 20:00 – 금 20:00). **야간 체결분에도 CCP 보증·리스크관리 적용.** **SIFMA의 2024년 최대 반대사유가 해소됐다** |
| **TRF 보고 (FINRA)** | ⚠ **2026-03-30부터 04:00 개장.** 그러나 **야간 체결은 여전히 익일 04:15까지 보고** |
| **SIP — Tape A·B (CTA/CQ)** | ✅ **SEC 승인 2026-06-26** (SR-CTA/CQ-2026-01, Rel. **34-105779**). 일 21:00 – 금 20:00, 월~목 **20:00–21:00 정비 중단** |
| **SIP — 나스닥 종목 (UTP)** | ✅ **SEC 승인 2026-06-26** (File S7-24-89, Rel. **34-105780**) |
| | ### ★ **양쪽 모두 2026-12-06 시행 명시** |
| ⚠ **가격밴드 (LULD 제27차)** | ⚠ **2026-06-01 공고, 만장일치, 아직 승인 전.** 야간 ±20% 밴드 — **자동 거래정지는 없다** → **[B3](B3-volatility.md) §B3-0** |
| **Night-to-Day 전환** | ✅ **SR-NASDAQ-2026-047** (Rel. **34-105590**, 2026-06-01, 즉시효력). 04:00 전환 시 Day/Night 시스템의 **호가 중복 전송을 막기 위한 극히 짧은 공백**("Momentary Handoff"). 정확한 길이는 개시 전 Trader Alert로 공지 |

> ## ⚠⚠ **최신화 — "목표"가 아니라 "확정"이다**
>
> **2025-12-19 확대안 제출 → SEC가 CTA/UTP 개정을 승인했다.** 승인명령 관보 게재 **2026-07-01** (이 조사 기준일 **11일 전**).
>
> ### **따라서 "SIP는 아직 목표 단계"라거나 "미국은 인프라가 안 돼서 못 열고 있다"는 서술은 더 이상 사실이 아니다.**
>
> **청산 = 2026-06-28 이미 가동. 시세 = 2026-12-06 시행 확정. 인프라는 사실상 풀렸다.**

### 청산은 해결됐다

**SIFMA의 2024년 최대 반대사유였다:**

> NSCC/DTCC가 21:00–01:30에 가동하지 않아, 그 시간 체결은 *"**excluded from the protections provided by NSCC and DTCC's real-time guarantee model**"* — 하루 5시간 이상 **상대방 위험에 노출**된다. 게다가 *"because of the anonymous nature of exchange trading, broker-dealers **would not know the counterparty**"*

**2026-06-28 NSCC 24x5 가동으로 사실상 해소됐다.**

### ⚠ 그러나 TRF는 해결되지 않았다 — **2단 투명성**

**FINRA Regulatory Notice 25-15 (2025-11-13), Rule 6380A·6380B 개정:**

| | |
| --- | --- |
| TRF 개장 | 08:00 → **04:00** (2026-03-30 시행) |
| 04:00–20:00 체결 | **10초 내 보고** |
| ★ **야간 체결** (TRF 닫힘) | **익일 04:15까지 보고** ← **상시 규칙** |

⚠ **혼동 금지**: 흔히 함께 인용되는 **"2026-03-30 ~ 2027-12-31 한시 예외"는 위 04:15 규칙의 일몰이 아니다.** 그것은 **NAV 기준 ETF 거래·야간 배치 처리 등 "qualifying overnight transactions"에 한정된 좁은 예외**(Supplementary Material .05)로, 보고 기한을 **08:15까지 늦춰주는** 것이다. **일반적인 야간거래 면제가 아니다.**

> ### **이것이 정확히 SIFMA가 경고한 "two-tiered system of market and price transparency"다.**
>
> *"exchange trades would be publicly disseminated in real time but OTC trades in the same securities would be reported the next day"*
>
> **야간에 OTC·ATS에서 무슨 일이 일어났는지, 아침에야 안다.**

---

## B4-4. ⚠ SIP 기한이 어긋났다 — 24X의 면제 신청

| | |
| --- | --- |
| **SEC가 24X 승인문에 쓴 기한** | **2026-05-27** (승인 후 18개월) |
| **SIP의 실제 시행일 (확정)** | **2026-12-06** |
| **차이** | **약 6개월** |

**그래서 24X가 2025-12-15에 SEC에 한시적·조건부 **면제**를 신청했다** (Rule 602 Reg NMS · Equity Data Plans · §19(g)(1) 관련. Release 34-104894, File No. S7-2026-06). **SIP가 준비되면 면제는 소멸하는 구조다.** 2026-04-29 승인 촉구 답변서 제출.

> ⚠ **본 조사 시점(2026-07-12) 미결. 인용 전 재확인 필요.**

---

## B4-5. ★★ 이 쟁점이 코스닥에 주는 것

### ① **미국 규제당국이 투자자 보호를 접근한 축이 다르다**

| | **SEC가 요구한 것** | **SEC가 요구하지 않은 것** |
| --- | --- | --- |
| | ★ **통합시세(SIP) 준비** | 유동성 게이트 |
| | 청산 인프라 | 가격제한(LULD) |
| | CAT·ISG·17d-2 등 감시 인프라 가입 | 공시 실시간 심사 |

> ### **미국은 "어떤 종목을 거래시킬 것인가"가 아니라 "그 거래가 공적으로 보이는가"를 물었다.**
>
> **종목 선별이 아니라 시장 인프라가 투자자 보호의 축이다.**

### ② 그 결과, **개시가 인프라 준비 속도에 묶였다**

| | |
| --- | --- |
| SEC 최초 승인 (24X) | **2024-11-27** |
| **1차 출처로 확인된 야간 승인** | ★ **4곳** — 24X · NYSE Arca · Nasdaq · **Cboe EDGX** |
| 그중 **21:00–04:00 세션** | **2곳** (Nasdaq · NYSE Arca). 24X는 **일 20:00–금 20:00**로 구조가 다르다 |
| **현재까지 개시** | **0곳** |
| **SIP 시행** | **2026-12-06 확정** |

> ## ✅ **"4개 거래소 승인"이 맞다 — Cboe EDGX도 1차 출처로 확인됐다 (2026-07-14 재검증)**
>
> **Rel. 34-105587 · SR-CboeEDGX-2026-019 · 관보 2026-06-03**
> *"**Order Granting Accelerated Approval** of a Proposed Rule Change … **To Extend the Exchange's Trading Hours to 23 Hours per Day, Five Days per Week**"*
>
> **EDGX의 Overnight Trading Session도 21:00 개시**이고, **SIP 조건도 동일**하다. **더 이상 "업계지 출처"가 아니다.**
>
> ⚠ 다만 **"승인문 셋 모두 SIP 조건이 동일하다"** 는 서술은 그대로 두어도 된다 — 그 문장은 24X·Nasdaq·NYSE Arca 세 건을 대조한 결과이고, EDGX도 같은 조건을 담고 있음이 이번에 확인됐다.

> ## ⚠⚠ **"20개월째 아무도 못 열었다"를 교착의 증거로 쓰지 말 것.**
>
> **SIP는 2026-12-06 시행이 확정됐고, NYSE Arca는 같은 날 개시를 목표로 명시했으며, 24X는 "지연을 예상하지 않는다"고 했다. 청산은 이미 가동됐다.**
>
> ### **지금은 "교착"이 아니라 "5개월 뒤로 잡힌 예정된 개시"다.**

> ### ★ **그래도 살아남는 것 — 그리고 이게 진짜 발견이다:**
>
> ### **SEC가 20개월간 건 조건 중에 "어떤 종목을 거래시킬 것인가"는 단 한 번도 없었다. 오직 "그 거래가 공적으로 보이는가"였다.**

### ③ ★ 한국에 던지는 질문

| # | 질문 |
| --- | --- |
| 1 | **애프터 세션의 시세가 공적으로 통합·배포되는가?** KRX와 NXT의 애프터 시세는 어떻게 통합되는가 |
| 2 | **애프터 체결이 공식 종가·지수·ETF NAV에 어떻게 반영되는가?** (미국은 `T` 조건을 달아 **last-sale 부적격**으로 처리한다 → [A1](A1-legacy-regime.md) §A1-2) |
| 3 | **애프터 체결의 실시간 보고 체계가 있는가?** (미국은 야간 OTC 체결을 익일 04:15에야 보고한다) |

> **미국이 20개월을 기다린 이유가 이 질문들이다. 한국 논의에서 이 축이 빠져 있다면, 그것 자체가 검토 대상이다.**
