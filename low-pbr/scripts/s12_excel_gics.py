"""s12 엑셀 재현본용 업종 시트 — 회차 × 종목 GICS 섹터.

엑셀(DataGuide 6) 재현본은 업종을 DataGuide 에서 받을 수 없다(KRX GICS 미제공). 이 시트를 그대로 붙인다.
s06 의 업종 규칙 A3 중 ②·③을 미리 적용한 값이다.
  ② 그 회차 기준일의 KRX 지수 사이트 GICS 분류 (s11, 출처 = KRX)
  ③ KRX 목록에 없는 예전 상장사 = WICS 세부 산업 근사 + KIND 공표 151사 표기 (출처 = WICS근사)
  ①  기준일 달 2개월 전 1일 이후 상장한 코스닥사 = 업종미분류 — 상장일(DataGuide)로 엑셀 수식에서 판정하므로
     여기서는 적용하지 않는다. 그래도 둘 다 없으면 업종미분류(출처 = 없음).

출력: data/interim/excel_gics.csv (utf-8-sig, 엑셀에서 바로 열림). GICS 매핑이라 git 에서 제외한다.
  회차, 기준일, 시장, 종목코드(DataGuide 형식 A+6자리), 종목명, GICS, 출처
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from s06_select import INTER, load_gics  # noqa: E402


def main():
    snap = pd.read_csv(INTER / "universe_snap.csv", dtype=str)
    krx = pd.read_csv(INTER / "gics_krx.csv", dtype=str)
    krx = {(r.round, r.code): r.sector for r in krx.itertuples()}
    approx = load_gics()
    rows = []
    for x in snap.itertuples():
        if (x.round, x.code) in krx:
            g, src = krx[(x.round, x.code)], "KRX"
        elif approx.get(x.code):
            g, src = approx[x.code], "WICS근사"
        else:
            g, src = "업종미분류", "없음"
        rows.append({"회차": x.round, "기준일": x.base_date, "시장": x.market, "종목코드": "A" + x.code,
                     "종목명": x.corp_name, "GICS": g, "출처": src})
    df = pd.DataFrame(rows)
    out = INTER / "excel_gics.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(out, len(df))
    print(df.pivot_table(index="회차", columns="출처", values="종목코드", aggfunc="count", fill_value=0))


if __name__ == "__main__":
    main()
