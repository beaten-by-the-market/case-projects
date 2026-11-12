"""s13 엑셀 재현본용 기준 보고서 시트 — 회차 × 종목의 "기준일 전 마지막 정기보고서" (DART).

엑셀 재현본은 기준 보고서를 법정 제출기한(반기 45일·사업 90일) 규칙으로 계산한다. 이 시트는 그 계산을
DART 실제 접수 기록과 맞춰 보는 대조 열이다(2026-11-11 시험: 29,648건 중 29,586건 일치, 선정 관련 2건 차이).
고르는 규칙은 s06 과 같다(_rules.choose_filing).

출력: data/final/excel_dart_filings.csv (utf-8-sig, DART 공개 자료라 git 에 둔다)
  회차, 기준일, 시장, 종목코드(A+6자리), 종목명, 재무년월, 보고서, 접수일, 접수번호, DART
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _db import get_conn  # noqa: E402
from _rules import DART_MAIN, ROOT, choose_filing, periodic_filings  # noqa: E402


def main():
    snap = pd.read_csv(ROOT / "data/interim/universe_snap.csv", dtype=str)
    fil = periodic_filings(get_conn(), list(snap.code.unique()))
    rows = []
    for x in snap.itertuples():
        f = choose_filing(fil.get(x.code, []), x.base_date)
        rows.append({"회차": x.round, "기준일": x.base_date, "시장": x.market, "종목코드": "A" + x.code,
                     "종목명": x.corp_name,
                     "재무년월": f[3].strftime("%Y%m") if f else "",
                     "보고서": f[4] if f else "", "접수일": f[1] if f else "",
                     "접수번호": f[0] if f else "", "DART": DART_MAIN.format(f[0]) if f else ""})
    df = pd.DataFrame(rows)
    out = ROOT / "data/final/excel_dart_filings.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(out, len(df), "보고서 없음", (df["접수번호"] == "").sum())


if __name__ == "__main__":
    main()
