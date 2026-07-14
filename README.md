# case-projects

데이터 분석 케이스 프로젝트 모음. 각 폴더가 독립적인 하나의 케이스다.

## 케이스

### [ssetf/](ssetf/) — 삼성전자·SK하이닉스 레버리지 상품 데이터셋
한국(KRX)·홍콩(HKEX)·런던(LSE)에 상장된 삼성·하이닉스 **레버리지 ETP/ETF**의
거래데이터·AUM·NAV, 그리고 한국인 보유·결제(SEIBRO)를 각 거래소 네이티브 소스에서
수집·통합한다. 재현 런북·소스별 API 문서·데이터 사전 포함. → [ssetf/README.md](ssetf/README.md)

### [kosdaq-afterhours/](kosdaq-afterhours/) — 애프터마켓 저유동성 종목 배제 기준
애프터마켓(NXT) 대상을 **코스닥 전체로 열어야 하는가**. 2024-01~2026-06 코스닥 보통주
1,683종목의 거래대금·유동성(Amihud)·공시 부담·거래정지 사건을 CHECK API로 수집해
배제 기준과 히스테리시스를 설계한다. 근거는 [REPORT.md](kosdaq-afterhours/REPORT.md),
제안은 [PROPOSAL.md](kosdaq-afterhours/PROPOSAL.md), 인수인계는
[HANDOFF.md](kosdaq-afterhours/HANDOFF.md).
수집 스크립트는 외부 레포 `check-api-krx-dl`의 checkapi-data 스킬에 의존한다(HANDOFF §7).

### [us-extended-hours/](us-extended-hours/) — 미국 거래시간 연장 사례조사
NYSE·NASDAQ이 거래시간을 늘리면서 **저유동성 종목과 공시·감시 부담을 어떻게 다뤘는지**
조사한다. 배경(레거시 프리·애프터, ATS 야간거래)과 본론(2024-11~ 정규거래소 연장)을 분리하고,
NASDAQ 거래정지 데이터로 검증한다. → [00-SUMMARY.md](us-extended-hours/00-SUMMARY.md)
