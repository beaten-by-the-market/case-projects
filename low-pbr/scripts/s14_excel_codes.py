"""s14 엑셀 재현본용 종목코드 목록 — DataGuide 코드 입력과 '종목' 시트에 쓴다.

범위: 13개 회차 중 한 번이라도 KIND 상장종목현황(증권구분 주권, ST)에 있던 보통주 + 그 회사의 우선주(종류주)
      중 2020-09-21 이후 상장돼 있던 것. 스팩·외국주권·리츠·투자회사는 증권구분이 달라 처음부터 빠진다(R12 일부).
원천: data/interim/universe_snap.csv (KIND) · pref_map.csv (KRX)

출력: data/final/excel_codes.csv (utf-8-sig, 공개 자료라 git 에 둔다)
  종목코드(A+6자리), 종목명, 구분(보통주|우선주), 보통주코드, 우선주종류, 상장일, 상장폐지일
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _rules import ROOT  # noqa: E402

WIN_START = "2020-09-21"   # 첫 회차(2020.11) 20거래일 구간 시작


def main():
    snap = pd.read_csv(ROOT / "data/interim/universe_snap.csv", dtype=str)
    pref = pd.read_csv(ROOT / "data/interim/pref_map.csv", dtype=str, keep_default_na=False)
    last = snap.sort_values("round").groupby("code").last()
    rows = [{"종목코드": "A" + c, "종목명": r.corp_name, "구분": "보통주", "보통주코드": "A" + c,
             "우선주종류": "", "상장일": r.list_date, "상장폐지일": ""} for c, r in last.iterrows()]
    pp = pref[pref.common_code.isin(last.index) & ((pref.delist_date == "") | (pref.delist_date >= WIN_START))]
    rows += [{"종목코드": "A" + r.pref_code, "종목명": r.pref_name, "구분": "우선주",
              "보통주코드": "A" + r.common_code, "우선주종류": r.kind, "상장일": r.list_date,
              "상장폐지일": r.delist_date} for r in pp.itertuples()]
    df = pd.DataFrame(rows)
    out = ROOT / "data/final/excel_codes.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(out, df["구분"].value_counts().to_dict())


if __name__ == "__main__":
    main()
