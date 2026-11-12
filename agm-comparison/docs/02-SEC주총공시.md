# 02. SEC 주주총회 관련 공시의 형태와 구조화 수준 (DART 와 비교)

조사일 2026-11-12 (별도 에이전트 조사, EDGAR 실물 확인 포함). 받은 실물 파일은 저장소 밖 임시 폴더에만 두었다.

## 1. 결론

- SEC 에는 **회사가 낸 위임장설명서(DEF 14A)의 안건에 유형 코드를 붙이는 구조가 없다.** DEF 14A 의 iXBRL 태그는 보수 관련 몇 항목(ECD 택소노미)과 표지 dei 4개 요소뿐이고, 안건 목록은 HTML 본문이다.
- 안건을 유형별로 분류한 공식 기계판독 데이터로 가장 가까운 것은 **펀드·운용사가 내는 Form N-PX XML** 의 `categoryType`(14개 고정 목록)이다. 다만 분류 주체가 발행회사가 아니라 표결한 기관이다.
- 따라서 "DART 처럼 안건유형별로 볼 수 있느냐"에 대한 답: **회사 공시만으로는 안 된다. N-PX 를 회사·주총일·의안 문구로 묶어 간접적으로, 14개 대분류 수준까지만 가능하다.**

## 2. 서식 × 포맷

| 서식 | 내용 | 제출 주체 | 정기주총 때? | EDGAR 포맷 | 구조화 데이터 |
|---|---|---|---|---|---|
| DEF 14A | 확정 위임장설명서 | **발행회사**(경영진) | **매번** (임시주총에도 씀) | iXBRL HTML + 추출 XBRL(`_htm.xml`, xsd/lab/pre/def), R*.htm, FilingSummary.xml, MetaLinks.json | 표지 dei 최소 + ECD(보수 대 성과·부여 시점·내부자거래 정책). **안건 태그 없음** |
| PRE 14A | 예비 설명서 (DEF 10일 전) | 발행회사 | 조건부 — 안건이 이사 선임·감사인 비준·say-on-pay·주주제안·주식보상계획뿐이면 생략, 정관 변경 등이 있으면 제출 | HTML | — (ECD 태그 범위 미확인) |
| ARS | 주주용 연차보고서 | 발행회사 | **대체로 매번** — 이사 선임이 있는 주총의 위임장과 함께 송부 의무(Rule 14a-3(b)). 단 EDGAR 제출이 없는 회사도 있음(아래) | **PDF** (EDGAR 제출 유형 `ARS`, 2023~ 전자 제출) | 없음 |
| DEFA14A | 추가 권유자료 | 발행회사 | 선택 — 주주 서신·발표자료·반대 권고 대응 시 | HTML·이미지 | 없음 |
| PREN14A / DEFN14A | 비경영진 위임장설명서 (경쟁 아닌 권유) | **주주 등 비발행회사** | 해당 시 — 주로 정기주총 주주제안 지지 권유 | HTML | 없음 |
| PREC14A / DEFC14A | 위임장 경쟁 설명서 (2022.8.31~ 보편적 위임장, Rule 14a-19) | **발행회사와 반대 주주 양쪽** | 해당 시 — 대부분 정기주총 이사 선임 경쟁 | HTML | 없음 — 14a-19 는 카드 양식 규칙이지 데이터 표준이 아님 |
| DFAN14A | 비경영진 추가 권유자료 | 주주 등 비발행회사 | 해당 시 (경쟁·캠페인) | HTML·이미지 | 없음 |
| PX14A6G | 권유 면제 서신 (위임장은 안 받고 찬반 호소) | **주주** (보유액 500만 달러 초과면 의무) | 해당 시 — 대부분 정기주총 주주제안 캠페인 | HTML·이미지 | 없음 |
| DEFM14A / PREM14A | 합병 설명서 | 발행회사 | **아님** — 합병 승인용, 대개 임시주총 | HTML | 없음 |
| PRE/DEF 14C | 정보설명서 (위임장 대신 지배주주 서면 동의) | 발행회사 | 드묾 — 주총을 열지 않거나 지배주주가 결의할 때 | HTML, DEF 14C 는 iXBRL 가능 | ECD 태그 가능 |
| 8-K Item 5.07 | 표결 결과 (주총 후 4영업일 내) | 발행회사 | **매번** (모든 주총) | iXBRL HTML | **표지 dei 만**. 안건별 찬성·반대·기권·브로커 미투표는 HTML 표 |
| SC 14N | 주주 이사 후보 추천 (proxy access) | **추천 주주(그룹)** | 해당 시 — 정기주총 이사 선임용 | HTML·텍스트 | 없음 |
| N-PX | 의결권 행사 기록 | **펀드·기관투자자** (13F 제출 운용사) | **주총과 무관** — 연 1회(8.31까지, 전년 7.1~6.30 표결분) | **XML** (`primary_doc.xml` + 표결표 XML) | 사안별 14개 범주 열거값 |

요약: 정기주총마다 발행회사가 반드시 내는 것은 **DEF 14A · ARS · 8-K 5.07** 세 가지(PRE 14A 는 조건부). 주주가 내는 것은 PREN/DEFN14A · PREC/DEFC14A(반대측) · DFAN14A · PX14A6G · SC 14N. 펀드·기관이 내는 것은 N-PX. **안건유형 분류가 붙는 유일한 서식(N-PX)은 발행회사가 아닌 투자자가 내고, 주총 시점과도 따로 논다.**

ARS 실물 확인(2026-11-12, data.sec.gov submissions API): Microsoft 는 DEF 14A 와 같은 날 ARS(PDF)를 낸다(2023-10-19 `d506673dars.pdf` 가 첫 건, 이후 매년). JPMorgan 도 2026-04-06 DEF 14A 와 같은 날 ARS(`annualreport-2025.pdf`). **Apple 은 2019~2026 DEF 14A 8건이 있으나 ARS 는 0건** — 10-K 를 그대로 주주용 연차보고서로 쓰는 회사는 따로 내지 않는 것으로 보인다(추정, 규칙 원문 미확인).

(제출 주체·정기주총 여부 열은 SEC 규칙 기준의 일반 지식으로 채웠다 — EDGAR 실물로 서식별 제출자를 대조하지는 않았다. Codex 교차조사 결과로 확인 예정.)

DART 쪽 대응: 주주총회소집공고(E006)는 **발행회사**가 정기·임시 모두 낸다. 주주가 위임장을 권유하면 그 주주가 **의결권대리행사권유참고서류**(지분공시 D003)를 낸다 — 미국 PREN/DEFC14A 의 반대측 서류에 해당. 이 서류에도 같은 L0 안건유형 코드가 붙는지는 아직 확인하지 않았다.

실물 확인
- Apple DEF 14A (2026.1.8, 0001308179-26-000008): FilingSummary 의 보고서는 Cover / Pay vs Performance / Award Timing / Insider Trading Policies 4개. 안건(이사 선임·감사인 비준·say-on-pay·주주제안) 태그 0개. 네임스페이스 `http://xbrl.sec.gov/ecd/2025`, `http://xbrl.sec.gov/dei/2025`. https://www.sec.gov/Archives/edgar/data/320193/000130817926000008/
- Apple 8-K 5.07 (2026.2.24 주총, 0001140361-26-006577): `_htm.xml` 에 dei 표지 태그만, 안건 5개 표결 수치는 HTML. https://www.sec.gov/Archives/edgar/data/320193/000114036126006577/

## 3. 구조화 데이터의 스키마

### dei 택소노미 (Document and Entity Information)
- SEC 가 관리하는 표지 정보용 택소노미. 공시 **내용**이 아니라 "무슨 문서이고 누가 냈는가"를 태그한다. 네임스페이스 `http://xbrl.sec.gov/dei/2025`.
- iXBRL 로 내는 모든 서식(10-K·10-Q·8-K·DEF 14A 등)의 표지에 공통으로 붙는다.
- 실물에서 본 요소:
  - Apple DEF 14A — `DocumentType`(="DEF 14A"), `EntityRegistrantName`(회사명), `EntityCentralIndexKey`(CIK, 회사 고유번호), `AmendmentFlag`(정정 여부) 4개뿐.
  - Apple 8-K 5.07 — `DocumentType`, `TradingSymbol`(종목코드), `SolicitingMaterial`(권유자료 해당 여부 체크박스) 등 8-K 표지 항목.
- DART XML 로 치면 `DOCUMENT-NAME@ACODE`(서식 코드)·`COMPANY-NAME`(회사)·`FORMULA-VERSION` 같은 문서 머리 정보에 해당한다.
- 그래서 "8-K 5.07 은 표지 dei 만 있다"는 말은 문서 종류·회사 정보만 태그돼 있고 **표결 결과 숫자에는 태그가 없다**는 뜻이다.

### ECD 택소노미 (Executive Compensation Disclosure)
- 스키마 https://xbrl.sec.gov/ecd/2025/ecd-2025.xsd (요소 125개), 가이드 https://xbrl.sec.gov/ecd/2026/ecd-taxonomy-guide-2026-03-16.pdf
- 범위: Reg S-K 402(v) 보수 대 성과, 402(w) 클로백, 402(x) 옵션 부여 시점, 408(a) 10b5-1 계획, 408(b) 내부자거래 정책. Schedule 14A 에는 `ecd-sub` 진입점.
- 주요 요소: `PvpTableTextBlock`, `PeoTotalCompAmt`, `PeoActuallyPaidCompAmt`, `TotalShareholderRtnAmt`, `CoSelectedMeasureAmt`, `ErrCompRecoveryTable`, `AwardTmgMnpiCnsdrdFlag`, `InsiderTrdPoliciesProcAdoptedFlag` 등.
- 근거 규칙: 보수 대 성과 Release 34-95607(2022), 클로백 33-11126(2022), 내부자거래 33-11138(2022).
- **주총 안건(proposal) 개념이 없다.**

### Form N-PX XML (기술명세 v3.1, 2025.2)
- 명세 https://www.sec.gov/files/edgar/filer-information/specifications/edgar-form-n-px-xml-technical-specification-31.zip
- 근거 Release 33-11131 / IC-34745, 2024.7.1 시행(2023.7.1 이후 표결분). 기관 운용사(13F 제출자)도 say-on-pay 표결을 보고.
- 표결표 XML(네임스페이스 `http://www.sec.gov/edgar/document/npxproxy/informationtable`)의 `proxyTable` 한 행 = 표결 사안 하나:
  `issuerName`, `cusip`, `isin`, `figi`, `meetingDate`, `voteDescription`(자유 텍스트), `voteCategories/voteCategory/categoryType`(**사안당 1~14개 복수 선택**), `voteSource`(ISSUER / SECURITY HOLDER), `sharesVoted`, `howVoted`(FOR/AGAINST/ABSTAIN/WITHHOLD), `managementRecommendation`.
- `CATEGORY_TYPE` 열거값 14개:
  DIRECTOR ELECTIONS · SECTION 14A SAY-ON-PAY VOTES · AUDIT-RELATED · INVESTMENT COMPANY MATTERS · SHAREHOLDER RIGHTS AND DEFENSES · EXTRAORDINARY TRANSACTIONS · CAPITAL STRUCTURE · COMPENSATION · CORPORATE GOVERNANCE · ENVIRONMENT OR CLIMATE · HUMAN RIGHTS OR HUMAN CAPITAL/WORKFORCE · DIVERSITY, EQUITY, AND INCLUSION · OTHER SOCIAL ISSUES · OTHER

## 4. DART 와 비교

| | DART 소집공고 XML | SEC |
|---|---|---|
| 분류 주체 | 발행회사(공시 작성 시) | 회사는 분류 안 함. N-PX 는 표결한 펀드·운용사 |
| 단위 | 안건유형 절 (`L0-0-2-N-0`) — 의안 단위 아님 | N-PX 표결 1행 (이사 선임은 후보별 1행) — 의안 단위 |
| 분류 체계 | 법령 호 번호 20종 (재무제표 승인, 정관 변경, 이사 선임 …) | 14개 대분류, 복수 선택, 세부 코드 없음 |
| 범위 | 모든 소집공고 | 펀드·운용사가 보유해 표결한 종목만 |
| 표결 결과 | 별도 공시(주총결과) | 8-K 5.07 HTML 표(태그 없음), N-PX 는 기관 자신의 표만 |

대응 관계 메모
- 재무제표 승인(1호)은 미국에 대응 안건이 없다. 이사 보수한도(9호)는 대체로 COMPENSATION, say-on-pay 는 별도 범주.
- 정관 변경(2호)은 내용에 따라 CORPORATE GOVERNANCE / SHAREHOLDER RIGHTS AND DEFENSES / CAPITAL STRUCTURE 로 흩어진다.
- 합병·분할·영업양수도·주식교환(12~15호)은 EXTRAORDINARY TRANSACTIONS, 자본 감소·신주(16~19호)는 CAPITAL STRUCTURE.
- 같은 안건이라도 N-PX 제출 기관마다 범주가 다를 수 있어, cusip + meetingDate + voteDescription 으로 묶고 다수결 등으로 조정해야 한다.
- 회사 단위로 전 안건·결과를 갖춘 데이터는 상업용(ISS Voting Analytics, Proxy Insight, FactSet SharkRepellent 등)에 의존한다.
