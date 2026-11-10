"""WICS(CHECK comp_basic) → GICS 섹터 근사 (가정 A3).

GICS 종목 매핑은 공개 데이터에 없다. WICS 는 GICS 와 같은 2자리 섹터 코드를 쓰지만 산업 배치가 다르다.
세부 산업(6자리) 단위로 GICS 정의에 맞춰 옮기고, 회사 단위 예외는 이름 규칙으로 둔다.
최종적으로는 KIND 공표 151사의 GICS 표기가 이 규칙보다 우선한다(s06.load_gics).

검증: 보도자료 붙임1 의 시장×업종 산정대상 사수 (docs/03-검증기록.md).
"""
import re

SECTOR = {"G10": "에너지", "G15": "소재", "G20": "산업재", "G25": "자유소비재", "G30": "필수소비재",
          "G35": "헬스케어", "G40": "금융", "G45": "정보기술", "G50": "커뮤니케이션", "G55": "유틸리티"}

# 세부 산업 → GICS (WICS 와 배치가 다른 곳만)
INDUSTRY = {
    "G101010": "산업재",      # 에너지장비·신재생(풍력타워·발전정비) — GICS 에너지장비는 시추·유전 서비스뿐
    "G252065": "필수소비재",   # 화장품 — GICS Personal Care Products
    "G405020": "부동산",      # 부동산 신탁·개발 — WICS 에 부동산 섹터 없음
    "G453520": "산업재",      # 2차전지 셀·장비 — GICS Electrical Components (소재사는 아래 이름 규칙)
}

# (세부 산업, 이름 정규식) → GICS
NAME_RULES = [
    ("G453520", r"소재|케미|머티|화학|비엠|퓨처엠|엔켐|천보|솔루스|에코프로$|나노|금속", "소재"),   # 양극재·전해질 등 소재
    ("G201025", r"시멘트|양회|C&E|레미콘|유진기업|아세아|동양$", "소재"),                     # 시멘트·레미콘 = Construction Materials
    ("G255030", r"리테일|이마트|마트|편의|코리아세븐", "필수소비재"),                            # 편의점·대형마트 = Staples Retail
    ("G551020", r"^E1$|SK가스|가스공사$", "에너지"),                                       # LPG 수입·유통 = Oil & Gas Storage
    ("G201030", r"개발$|디앤디|토지신탁|자산신탁", "부동산"),                                 # 주택개발 시행사
]


def to_gics(wics: str, name: str) -> str:
    w = (wics or "").strip()
    if not w:
        return ""
    for ind, rx, g in NAME_RULES:
        if w == ind and re.search(rx, name or ""):
            return g
    if w in INDUSTRY:
        return INDUSTRY[w]
    return SECTOR.get(w[:3], "")
