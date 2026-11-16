"""코스닥 확장 공용 — 코스피 단계(s03~s06, s04b~s04d)를 코스닥 행에 같은 규칙으로 쓰기 위한 경로·대상

코스피 스크립트는 시장('코스피')과 출력 위치(data/charter/, data/agm/, data/interim/sNN_*.json)가 코드에 들어 있다.
코스닥 단계 스크립트(sNNk_kosdaq_*.py)는 그 함수들을 import 해 **같은 규칙**으로 돌리고, 출력만 아래 코스닥 전용
위치에 쓴다. 공용 파일(_common.py · 코스피 sNN 스크립트)은 고치지 않는다 (2026-11-16, 다른 세션과 나눠 작업).

입력은 코스피와 같다 — data/interim/s01_reports.json(사업보고서 최종본, 모든 시장) · s02_market.json(KIND 기준일 현재 시장).

  코스닥 위치                         코스피 위치
  data/interim/kosdaq/sNN_*.json     data/interim/sNN_*.json   (파일 이름은 같다)
  data/charter_kosdaq/               data/charter/
  data/agm_kosdaq/                   data/agm/
  data/raw/llm_ocr_kosdaq/           data/raw/llm_ocr/         (Opus 요청 ID p00001… 가 시장마다 따로 매겨지므로 분리)
  data/raw/opendart_absent_kosdaq/   data/raw/opendart_absent/
  DART 화면 캐시 data/raw/dart_main · dart_att 는 접수번호·문서번호로 이름이 붙어 겹치지 않으므로 같이 쓴다.
"""
from __future__ import annotations

from _common import INTERIM, RAW, ROOT, read_json

MARKET = "코스닥"
KQ_INTERIM = INTERIM / "kosdaq"
KQ_CHARTER = ROOT / "data" / "charter_kosdaq"
KQ_AGM = ROOT / "data" / "agm_kosdaq"
KQ_LLM = RAW / "llm_ocr_kosdaq"


def kosdaq_rows() -> tuple[list[dict], dict]:
    """s01 사업보고서 행 중 s02 시장이 코스닥인 것 (s01 순서 그대로) · s02 시장 표."""
    reports = read_json(INTERIM / "s01_reports.json")
    market = read_json(INTERIM / "s02_market.json")
    return [r for r in reports if market[r["rcept_no"]]["market"] == MARKET], market


def patch(mod, **extra):
    """코스피 스크립트 모듈의 전역 경로(CHARTER·INTERIM 등)를 코스닥 위치로 바꾼다.

    그 모듈의 함수는 부를 때마다 모듈 전역을 읽으므로, import 뒤 바꿔 두면 같은 코드가 코스닥 위치에 읽고 쓴다.
    main() 이 공용 입력(s01_reports.json 등)을 INTERIM 에서 읽는 모듈에는 INTERIM 을 바꾸지 않는다(호출부에서 고른다).
    """
    KQ_INTERIM.mkdir(parents=True, exist_ok=True)
    for k, v in extra.items():
        if not hasattr(mod, k):
            raise AttributeError(f"{mod.__name__} 에 {k} 가 없다 — 코스피 스크립트가 바뀌었는지 확인")
        setattr(mod, k, v)
    return mod
