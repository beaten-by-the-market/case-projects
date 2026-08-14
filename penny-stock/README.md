# penny-stock — 관리종목·상장폐지(시총·주가 미달) 스크리너 & 대시보드

KRX 코스닥·유가시장에서 **시가총액 미달 / 주가 미달(동전주)** 사유로 관리종목
지정·상장폐지에 이르는 종목을 규정대로 판정하고, 무료·정적 HTML 대시보드로
시각화한다. KRX 공식 지정 종목의 **지정일까지 전건 일치**하도록 규정을 복제했다
(그날의 실제 수치·대조 결과는 대시보드 화면과 `data/dashboard_data.json`에서 확인).

판정 엔진은 이 저장소에 두지 않는다. `krx-data-api` 패키지에 라이브러리로 있으며
이 프로젝트는 그것을 **import해서** 데이터만 생성한다(엔진 단일 출처 원칙).

## 구조

```
penny-stock/
├─ data/
│  ├─ snapshots.csv          # 전종목 일별 시세 캐시(종가·시총·거래량), 증분 누적
│  ├─ target_universe.csv    # KIND listed_issue_status 화이트리스트(대상 유니버스)
│  └─ dashboard_data.json    # 대시보드가 embed하는 산출물(generate.py 출력)
├─ scripts/
│  └─ generate.py            # 데이터 파이프라인(공유 패키지 import → dashboard_data.json)
├─ web/
│  ├─ dashboard.html         # 프론트 템플릿(`__DATA__` 자리표시자, 단일 HTML)
│  ├─ build.py               # 템플릿 + json → dashboard_final.html(배포본)
│  └─ dashboard_final.html   # 배포본(외부 의존성 없음, 그대로 열거나 GitHub Pages 배포)
└─ docs/
   └─ regulations.md         # 복제 대상 규정 원문 요약(근거)
```

## 의존 패키지(editable 설치 필요)

| 패키지 | 역할 |
|---|---|
| `krx-data-api` | 시세 캐시·**스크리너·판정 상태기계**·대시보드 artifacts 생성기 |
| `krx-kind-data-api` | KIND 상장종목현황(유니버스)·관리종목 지정일·변경상장 |
| `seibro-api` | 예탁결제원 권리일정(액면병합·자본감소 비율) |

```bash
pip install -e ../../krx-data-api
pip install -e ../../krx-kind-data-api   # 실제 경로에 맞게
pip install -e ../../seibro-api
```

## 워크플로

```bash
# 1) 데이터 생성 (캐시 그대로, 판정·병합만 재계산)
python scripts/generate.py
#    스냅샷·유니버스까지 새로 수집하려면:
python scripts/generate.py --refresh

# 2) 배포본 빌드 (템플릿 + json → 단일 HTML)
python web/build.py

# 3) web/dashboard_final.html 을 브라우저로 열거나 GitHub Pages로 배포
```

## 대시보드 기능

- **사유×단계 매트릭스**(시총 미달 / 동전주 × 현재미달·지정임박 D-10·임박 D-5·지정,
  그리고 해제임박·상폐위험). 숫자 클릭 → 해당 종목 필터.
- 종목별 **시총·주가 사유 한 줄 병합** 표시, 클릭 시 그 행 아래로 **인라인 드릴다운
  차트**(계단식 기준선, 미달시작·지정·병합/감자 vline, 호버 툴팁).
- KRX/KSD **변경상장(병합·감자) 상세 표**(일자·사유·비율), 규정 원문 모달, 시장 탭,
  파스텔 시장 태그, "현재기준 미달 종목 전체 조회" 토글.
- 주가미달 지정·상폐는 **신설 규정 예측**이므로 디스클레이머 표기.

## 판정 요약

관리종목: 기준 미달 **연속 30거래일** → 익일 지정, 기준 이상 **연속 45거래일** →
해제. 거래량 0(정지)일은 카운트 제외. 기준은 부칙 기간별 계단식(시총) / 종가
1,000원·2026-07-01 시작(주가). 상장폐지 회복조건은 시장별 상이. 자세한 근거는
[docs/regulations.md](docs/regulations.md).
