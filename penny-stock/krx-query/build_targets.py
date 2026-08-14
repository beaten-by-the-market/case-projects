# -*- coding: utf-8 -*-
"""
================================================================================
targets.py 생성기 — 조사 대상 (종목 × 사유발생일 × 공시시각) 목록 만들기
================================================================================

  ▸ 외부망(인터넷 PC)에서 실행한다. 거래소 내부 DB 는 쓰지 않는다.
  ▸ 입력  : ../proposal/data/cap_price_designations.csv  (KIND 공시 수집본)
            ../data/snapshots.csv                        (단축코드·표준코드 매핑)
  ▸ 출력  : ./targets.py   ← offhour_impact_query.py 가 import 하는 대상 목록
                             (폐쇄망에는 이 파일만 들고 들어가면 된다)

  Spyder F5 로 실행.
================================================================================
"""

from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent

SRC_DESIGN = PROJ / "proposal" / "data" / "cap_price_designations.csv"
SRC_SNAP   = PROJ / "data" / "snapshots.csv"
OUT_PY     = HERE / "targets.py"


def main():
    d = pd.read_csv(SRC_DESIGN, encoding="utf-8-sig", dtype=str)

    # 단축코드·표준코드(12자리 ISU_CD) 매핑 — 스냅샷 최종일 기준
    snap = pd.read_csv(SRC_SNAP, dtype=str, usecols=["일자", "단축코드", "표준코드", "종목명", "시장"])
    last = snap[snap["일자"] == snap["일자"].max()]
    m = last.drop_duplicates("종목명").set_index("종목명")

    d["단축코드"] = d["회사명"].map(m["단축코드"])
    d["표준코드"] = d["회사명"].map(m["표준코드"])

    miss = d[d["단축코드"].isna()]
    if len(miss):
        print(f"⚠ 코드 매핑 실패 {len(miss)}건 — 회사코드+'0' 규칙으로 보정 시도")
        print(miss[["공시일", "시장", "회사코드", "회사명"]].to_string())
        d.loc[d["단축코드"].isna(), "단축코드"] = (
            d.loc[d["단축코드"].isna(), "회사코드"].str.zfill(5) + "0"
        )

    d = d.sort_values(["공시일", "공시시각", "회사명"]).reset_index(drop=True)

    lines = []
    for _, r in d.iterrows():
        lines.append(
            "    dict(dd=%r, tm=%r, mkt=%r, srt=%r, isu=%r, nm=%r, rsn=%r, typ=%r),"
            % (
                str(r["공시일"]).replace("-", ""),   # YYYYMMDD  (= 사유발생일 = 종가 확정일)
                str(r["공시시각"]).replace(":", ""),  # HHMM      (= 공시 발표 시각)
                str(r["시장"]),
                str(r["단축코드"]),
                str(r["표준코드"]) if pd.notna(r["표준코드"]) else "",
                str(r["회사명"]),
                str(r["사유"]),
                str(r["유형"]),
            )
        )

    body = "\n".join(lines)
    src = f'''# -*- coding: utf-8 -*-
"""
조사 대상 — 시가총액 미달 / 주가 미달(동전주) 사유 관리종목 지정 공시 전수.

  build_targets.py 가 자동 생성. 직접 고치지 말 것.

  dd  : 지정사유 발생일 (= 15:30 종가를 마지막으로 반영하는 날, YYYYMMDD)
        KRX 는 이 날 장 마감 후 지정을 공시하고, 지정 효력은 다음 거래일부터다.
  tm  : 공시 발표 시각 (HHMM, KIND 접수시각)
  mkt : 시장 (유가증권 / 코스닥)
  srt : 종목 단축코드 6자리
  isu : 종목 표준코드 12자리 (DB 의 ISU_CD)
  nm  : 종목명
  rsn : 지정사유
  typ : 신규지정 / 사유추가 / 사유변경

  출처: KIND 공시 상세검색 (2026-02-12 ~ 2026-08-13, 전수 {len(d)}건)
"""

TARGETS = [
{body}
]
'''
    OUT_PY.write_text(src, encoding="utf-8")
    print(f"✅ {OUT_PY}  ({len(d)}건)")
    print(d.groupby(["시장", "사유"]).size().to_string())


if __name__ == "__main__":
    main()
