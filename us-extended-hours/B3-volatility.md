# B3. 쟁점 3 — 가격 안전장치: **밴드 없이 승인했고, 업계가 뒤늦게 메우러 왔다**

> **[← 목차](README.md)** · 선행: **[B2. 공시와 거래정지](B2-disclosure-halts.md)** · 다음: **[B4. 인프라 전제조건](B4-infrastructure.md)** · **기준일 2026-07-13**

---

## 한 문장

> ## **SEC는 23시간 거래를 개별종목 가격제한 **없이** 승인했다 (2026-04-10, 승인문 전문에 "LULD"가 0회).**
> ## **그러자 두 달 뒤, 전 거래소가 만장일치로 야간 ±20% 가격밴드를 SEC에 제출했다 (2026-06-01).**
> ## **★ 그러나 자동 거래정지(Trading Pause)는 여전히 없다. 그리고 그 밴드는 ATS(Blue Ocean)를 그대로 베낀 것이다.**

---

## B3-0. ⚠⚠ **최신화 — 이 문서에서 가장 중요한 절**

> ### **"야간에 LULD가 없다"고만 쓰면 낡은 자료가 된다. 3주 전에 상황이 바뀌었다.**

**LULD Plan 제27차 개정안** (Rel. **34-105596** · File **4-631** · **2026-06-01 공고**)

> "The Twenty-Seventh Amendment proposes to amend the Plan to **establish temporary price band protections to overnight trading ('Overnight Protections')** in anticipation of overnight trading by certain national securities exchanges."
>
> "The proposal reflects changes **unanimously approved by the Participants.**"

| | **정규장 LULD** | ★ **야간 Overnight Protections (제안)** |
| --- | --- | --- |
| **적용 시간** | 09:30–16:00 | **21:00–04:00** |
| **밴드** | 티어·가격대별 (5~20%) | ★ **±20% 고정** |
| **참조가격** | 직전 5분 체결 평균 | **공식 종가** · **19:45 통합 최종체결가** 중 유·불리 쪽 |
| **레버리지 ETP** | (별도 규정 없음) | **20% × 레버리지 배수** |
| **최소 밴드** | — | **$1.00** |
| ★★ **자동 거래정지** | ✅ **Limit State → 5분 정지** | ### ❌ **없다** |
| **성격** | 확정 제도 | ⚠ **"temporary" · "interim"이라고 스스로 부른다** |
| **상태** | 시행 중 | ⚠ **제안·의견수렴 단계.** 의견마감 **2026-06-25** · **승인명령 아직 없음** |
| **시행 목표** | — | **2026-12-06** (SIP 개시일) |

### ★★ 그래서 정확한 서술은 이것이다

> ## ❌ ~~"SEC는 가격제한을 포기했다"~~ → **그대로 쓰면 반박당한다.**
>
> ## ✅ **"SEC는 가격제한 *없이* 승인했다(2026-04). 그러자 업계가 만장일치로 야간 밴드를 제출했다(2026-06). 개시 전에 스스로 메우러 온 것이다."**

### ★★★ 그래도 살아남는 것 — **셋. 그리고 이게 진짜 발견이다**

**① 자동 거래정지는 여전히 없다** (개정안 원문):

> "the Participants have **determined not to implement automatic Trading Pauses** during Overnight Protected Hours."

> ### **정규장 LULD의 핵심은 밴드가 아니라 "Limit State → 5분 정지"다. 그 핵심이 빠졌다.**
>
> **밴드 밖 주문은 거부될 뿐, 종목이 멈추지 않는다. 악재가 터져도 가격은 −20%까지 미끄러진 뒤 그 자리에 붙어 있을 뿐, 아무도 멈춰 세우지 않는다.**

**② 거래소가 ATS를 베꼈다** — 개정안이 스스로 밝힌다:

> "**similar to ATSs** which also do not implement automatic trading pauses during overnight trading sessions (**ATSs simply reject orders that fall outside their bands**)."

> ### **Blue Ocean ATS의 ±20% 밴드가 그대로 정규거래소의 표준이 됐다.**
>
> **정규거래소가 ATS 수준으로 내려간 것이지, ATS를 정규장 수준으로 끌어올린 것이 아니다.** → **[A2](A2-ats-and-brokers.md) §A2-4**

**③ 스스로 "임시(interim)"라고 부른다** — 나중에 *"remove the interim measures and replace them with revised overnight protections"* 하겠다고 한다. **완성된 제도가 아니다.**

---

## B3-1. LULD는 정규장에만 적용된다

**LULD(Limit Up-Limit Down)** = 미국의 개별종목 가격제한. 참조가격(직전 5분 체결 평균) 대비 밴드를 벗어나면 Limit State → 15초 지속 시 **5분 거래정지**.

**적용 시간: 09:30–16:00뿐이다.** 프리마켓·애프터·야간 어디에도 적용되지 않는다.

**NYSE 자신의 FAQ (v3.0, 2026-05) 원문:**

> "Q: Will Limit Up/Limit Down (LULD) price bands apply in the Overnight Session?
> **A: Currently, LULD rules apply only during the Core Session**, but market participants and exchanges are discussing a possible extension of industry-wide LULD-like volatility controls that could eventually apply during the Overnight Session."

---

## B3-2. ★★ 나스닥은 대체할 것이 없다고 **자인했다**

**나스닥이 SEC에 낸 23/5 신청서 원문:**

> "The Exchange would also implement measures to safeguard against trade executions that are clearly erroneous **while it works to build industry-wide consensus on proposals for establishing uniform after-hours volatility moderators.**"

> ### ★ **SEC 승인문(Rel. 34-105199) 전문에 "Limit Up-Limit Down"도 "LULD"도 단 한 번 나오지 않는다.**
>
> **23시간 거래를 승인하면서, 가격제한 없는 세션을 승인한 것이다.**

**나스닥이 새로 만든 Night Session 위험고지 문구:**

> "trading during hours in which there may be **different or limited regulatory protections such as single stock volatility mechanisms**"
>
> "trading during hours that the **primary listing market may not be open to conduct surveillance** and other regulatory obligations"

> **거래소가 스스로 "이 시간엔 개별종목 변동성 장치가 제한적이고, 상장거래소가 감시하지 않을 수 있다"고 고객에게 고지한다.**

---

## B3-3. 24X 때도 반대가 있었다 — SEC는 수용했다

**SEC Release 34-101777 (24X 승인문):**

| | |
| --- | --- |
| **24X의 설계** | 야간세션에 LULD 없음. **명백한 오류 거래(clearly erroneous) 규정**에만 의존 |
| **반대 의견서** | **Nasdaq과 IEX**가 반대 (경쟁 거래소들이 반대했다) |
| **SEC의 판단** | **수용.** 논리: 24X 야간세션은 *"이미 OTC로 거래 가능한 시간대"* 이고 *"기존 연장세션과 일관된다"* |

> ### ⚠ **SEC의 논리를 정확히 이해할 것.**
>
> **"이미 ATS에서 그 시간에 아무 보호 없이 거래되고 있으니, 거래소가 같은 수준으로 여는 것은 새로운 위험이 아니다."**
>
> **즉 기존 ATS 시장의 낮은 보호수준이 정규거래소의 기준선이 됐다.** 밑으로 수렴한 것이다.

---

## B3-4. 그러면 야간에 **남아 있는** 가격 통제는 무엇인가

**시장 전체 장치는 없다. 주문 단위 장치만 있다. 그리고 이것은 종목을 멈추는 게 아니라 주문을 거부한다.**

| 장치 | 내용 | 성격 |
| --- | --- | --- |
| **주문유형 제한** | **지정가만.** 시장가·비지정가·페그 주문 전면 금지 | 사전 |
| **Nasdaq LOP** (Rule 4757(c)) | 참조가 대비 **10% 또는 $0.50 중 큰 값**을 벗어난 지정가 주문 **거부**. "across all trading sessions" | 사전 |
| **NYSE Arca** | 지정가 가격검증. **"not adjusted for early or late sessions"** | 사전 |
| **명백한 오류 거래 취소** | **기준이 2배로 완화** (아래 §B3-5) | **사후** |
| **Blue Ocean ATS** (참고) | ★ **±20% 참조가격 밴드.** 밴드 밖 주문 거부, 밴드 밖 체결 **취소** | 사전 |

> ### ⚠⚠ **아이러니: ATS가 정규거래소보다 강한 가격 통제를 갖고 있다.**
>
> **Blue Ocean은 ±20% 밴드가 있는데, 승인된 정규거래소 야간세션에는 밴드가 없다.**
>
> **FINRA 2026 감독보고서가 이것을 명시적으로 지적한다:** 감독 절차는 야간거래의 고유 특성 — **"such as venue-specific overnight price bands"** — 을 반영해야 한다.

---

## B3-5. ⚠ 명백한 오류 거래: **기준이 2배로 완화된다**

**의도적으로 약화된 안전장치다.** NYSE Arca 7.10-E · Cboe BZX 11.17 · FINRA 11892 원문 확인.

⚠ **"FINRA·Nasdaq·Cboe·Arca·24X 모두 동일"이라고 쓰지 말 것.** 우리가 원문을 연 것은 **세 곳(Arca·BZX·FINRA)** 이다. 나스닥 11890과 24X 11.14는 **승인문의 *"See, e.g."* 참조 목록에서 이름만 확인**했다 — 수치표가 같다는 것을 확인한 게 아니다.

| 참조가격 | **정규장** | **프리·애프터·야간** |
| --- | --- | --- |
| $25.00 이하 | **10%** | **20%** |
| $25.00 초과 ~ $50.00 | **5%** | **10%** |
| $50.00 초과 | **3%** | **6%** |
| **레버리지 ETF/ETN** | — | ★ **정규장 기준 × 레버리지 배수** |

> ### **$60짜리 주식이 직전 체결가 대비 5% 벗어나 체결되면, 오전 11시에는 취소 대상이고 저녁 6시에는 취소 대상이 아니다. 그 체결은 그대로 유효하다.**

> ## ⚠⚠ **레버리지 ETP — 이전 판(60%)은 틀렸다. 30%다.**
>
> **규칙 원문 (NYSE Arca 7.10-E Exhibit 5):**
>
> > *"Leveraged ETF/ETN securities … **Core Trading Session Numerical Guidelines multiplied by the leverage multiplier** (e.g., 2x)"*
>
> ### **곱하는 기준은 "정규장(Core) 기준"이다. "2배 완화된 연장시간 기준"이 아니다.**
>
> **$25 이하 3배 레버리지 ETP → 10% × 3 = **30%**.** (~~20% × 3 = 60%~~ 는 **이중 계산**이었다.)
>
> ⚠ **"정규장에는 LULD가 레버리지 배수를 곱한 밴드로 잡아준다"도 쓰지 말 것 — 근거가 없다.** LULD 규정에 **레버리지 배수라는 개념 자체가 없다**(Tier 1/2와 가격대별 파라미터만 있다).
>
> ### **그래도 논지는 남는다: 30%는 정규장 기준(10%)의 3배이고, 그 위에 LULD도 없다. 그리고 야간 거래량의 61%가 ETP다** (정규장은 21%). → **[A3](A3-evidence.md)**

⚠ **아래 NYSE 인용문을 "명백한 오류 기준"의 근거로 쓰지 말 것 — 다른 질문에 대한 답이다.**

> **Q: What checks are applied by the Exchange to orders during the Overnight Session?**
> A: NYSE Arca will continue to apply the **Limit Order price protection checks**… *"There is an option within the NYSE Pillar Risk Controls for firms to adjust to **double-wide percentages (20% / 10% / 6%)** in the Overnight, Early, or Late Trading Sessions."*

**이것은 회원사가 선택적으로 넓힐 수 있는 *사전 주문 가격검증*이다** (→ **§B3-4**의 "사전" 항목). **사후 체결 취소 기준이 아니다.** 숫자(20/10/6)가 우연히 같아서 혼동하기 쉽다. **명백한 오류에 대한 FAQ의 답은 따로 있다**: *"The current CEE rules for non-Core Session trading hours will apply in the Overnight Session in the same way as in the Early and Late Sessions."*

---

## B3-6. 그 밖에 야간에 꺼지는 것들 (참고)

**야간세션은 프리·애프터보다 더 벗겨진다.** 상세는 **[A1. 기존 체제](A1-legacy-regime.md) §A1-2**.

| 안전장치 | 정규장 | **프리·애프터** | **야간 21:00–04:00** |
| --- | --- | --- | --- |
| **LULD** | ✅ | ❌ | ❌ |
| **시장 전체 서킷브레이커** | ✅ | ❌ | ❌ |
| **Reg NMS Rule 611** (최선호가 관통 금지) | ⚠ ✅ (**폐지 제안 중** ↓) | ❌ | ❌ |
| **SIP 통합시세 (NBBO)** | ✅ | ✅ | ❌ **아예 없음** (→ [B4](B4-infrastructure.md)) |
| **Reg SHO 201** (공매도 업틱) | ✅ | ⚠ 제한만 | ❌ **무력화** (NBB가 없으므로) |
| **시장조성 의무** | ✅ | ❌ **opt-in** | ❌ **opt-in** |
| **공식 종가 반영** | ✅ | ❌ (`T` 조건) | ❌ |
| **오류거래 취소** | 10/5/3% | ⚠ **20/10/6%** | ⚠ **20/10/6%** |

> ### **야간 20:00~04:00은 통합시세조차 없다. 그래서 Reg SHO 공매도 규제가 자동으로 꺼진다.**
>
> **야간에 주가가 10% 폭락해도 공매도 서킷브레이커는 발동조차 되지 않는다.**

> ## ⚠⚠ **이 표의 기준선(정규장 열)이 흔들리고 있다 — 반드시 밝힐 것**
>
> **SEC는 2026-06-11 Reg NMS Rule 611(최선호가 관통 금지)과 610(e)(락트/크로스 금지)를 *전면 폐지*하겠다고 제안했다.** (보도자료 2026-54 · Rel. **34-105655** · 91 FR 36656. **의견제출 2026-08-17 마감**)
>
> ### **아직 제안 단계이고 두 규칙은 현행 유효하다. 그러나 이 표는 "정규장에는 있는데 연장시간엔 벗겨진다"를 논거로 쓴다 — 그 기준선 자체가 폐지 절차에 들어가 있다.**
>
> **폐지되면 611은 *모든 세션*에서 사라지고, 가격 보호의 최후 보루는 **최선집행 의무(best execution)** 하나만 남는다.**
>
> ⚠ **인용 시 반드시 이 진행 상황을 함께 밝힐 것.** 밝히지 않으면 "낡은 자료"로 반박당한다.

⚠ **참고 — 611의 예외가 하나 있다.** **Cboe BZX Rule 11.13**은 자율적으로 연장시간 체결이 *"equal to or better than the highest Protected Bid or lowest Protected Offer"* 이도록 요구한다. **거래소 단위의 자율 규정**이며, BZX에 대해서만 확인했다.

---

## B3-7. ★ 이 쟁점이 코스닥에 주는 것

### ① **미국의 애프터·야간은 "보호가 벗겨진 별도 시장"이다**

| | |
| --- | --- |
| **미국이 여는 것** | 가격제한 없음 · 서킷브레이커 없음 · 최선호가 보호 없음 · 오류거래 기준 2배 완화 · 체결가가 공식 종가에 반영 안 됨 · 시장조성 의무 없음 |
| **한국이 여는 것** | ⚠ **정규장급 보호를 주려 한다면, 그것은 미국보다 훨씬 강한 약속이다** |

> ### **"미국도 애프터를 한다"는 사실은 맞다. 그러나 그 세션은 우리가 생각하는 그 세션이 아니다.**
>
> **미국의 선택은 "종목을 고르는 대신, 보호를 낮춘 별도 시장을 만들고 위험을 고지한다"였다.**

### ② 그리고 그것이 정확히 비판받는 지점이다

**Better Markets (2024-11-27, 24X 승인 비판):**

> "Retail investors trading during an overnight session will be trading in a market where there are **few buyers and sellers**, and where prices will be **more volatile** and less favorable than during normal hours."
>
> "during overnight sessions, retail investors will only get **the best prices in a bad market**."
>
> ## **"Disclosure, however, is not protection, as research has shown."**

> ### **미국 애프터 투자자 보호의 사실상 중심은 FINRA Rule 2265 위험고지다. 승인문 세 건 모두에서 그것이 유일한 실질 도구다.**
>
> **"위험을 알렸으니 됐다"가 미국의 답이고, Better Markets는 그것이 답이 아니라고 말한다.**

### ③ ★ 대안 설계: **미국은 유동성으로 "적격성"이 아니라 "의무의 크기"를 가른다**

**배제하지 않고도 저유동성 종목을 다루는 방법이 미국 규정 안에 있다.**

| 도구 | 내용 |
| --- | --- |
| **LULD Tier** | **Tier 2(= S&P500·러셀1000 밖의 전 NMS 종목)는 밴드가 2배 넓다** (10% vs 5%) |
| **NYSE DMM 의무** | 통합 ADV **100만주 미만** 종목은 최우선호가 시간의 **15%**, **100만주 이상**은 **10%** → **유동성이 낮을수록 의무가 더 무겁다** |

> ### **"저유동 종목을 애프터에서 빼자" 대신 "저유동 종목의 애프터에는 시장조성자를 반드시 세우자"는 설계가 가능하다.**
>
> ⚠ **다만 미국 연장세션의 시장조성은 opt-in이라 이 조합의 선례는 없다.** (Nasdaq Equity 2 §8: *"A Nasdaq Market Maker **may voluntarily** open for business prior to 9:30 a.m. and remain open … later than 4:00 p.m."*)

→ **[C1. 코스닥 시사점](C1-implications-krx.md) §대안 도구**
