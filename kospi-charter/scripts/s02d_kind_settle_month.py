"""s02d 현재 결산월 — KIND 상장법인목록(corp_list)의 '결산월'

사업보고서 행의 결산월(settle_month)은 그 사업보고서의 결산기에서 딴 값이라, 제출 뒤 결산월을 바꾼 회사는 지금과 다르다.
사용자 지시(2026-11-16): 현재 기준 결산월을 KRX 데이터로 붙이고, 웹페이지 배당기준일 탭에서 다르면 표시한다.

  · krx_kind_data_api.fetch("corp_list", marketType=stockMkt / kosdaqMkt) — KIND 상장법인목록 다운로드 (요청 2건)
    열: 회사명 · 종목코드 · 업종 · 주요제품 · 상장일 · 결산월('12월') · 대표자명 · 홈페이지 · 지역
  · 받은 표는 data/raw/kind/corplist_YYYYMMDD_{stockMkt|kosdaqMkt}.csv 로 두고, 있으면 다시 받지 않는다 (--force 로 다시)
  · 상장법인목록은 '지금' 목록만 준다(날짜 지정 없음). 받은 날을 fetched 로 남긴다.

출력
  data/interim/s02d_settle_month.json   {as_of, fetched, source, n: {시장: 회사 수}, settle_month: {종목코드: 월(정수)}}

    python -X utf8 scripts/s02d_kind_settle_month.py
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, INTERIM, RAW, read_json, write_json  # noqa: E402

OUT = INTERIM / "s02d_settle_month.json"
MARKETS = {"stockMkt": "코스피", "kosdaqMkt": "코스닥"}


def raw_path(mkt: str) -> Path:
    return RAW / "kind" / f"corplist_{AS_OF:%Y%m%d}_{mkt}.csv"


def corp_list(mkt: str, force: bool) -> pd.DataFrame:
    p = raw_path(mkt)
    if p.exists() and not force:
        return pd.read_csv(p, dtype=str, encoding="utf-8-sig")
    from krx_kind_data_api import fetch
    df = fetch("corp_list", marketType=mkt).astype(str)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"  KIND 상장법인목록 {mkt}: {len(df)}행 → {p.relative_to(RAW.parent.parent)}")
    return df


def month(v) -> int | None:
    m = re.search(r"(\d{1,2})", str(v or ""))
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 12 else None


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="KIND 에서 다시 받는다")
    a, _ = ap.parse_known_args()
    by, n, fetched = {}, {}, {}
    for mkt, name in MARKETS.items():
        df = corp_list(mkt, a.force)
        assert {"종목코드", "결산월"} <= set(df.columns), list(df.columns)
        fetched[name] = datetime.fromtimestamp(raw_path(mkt).stat().st_mtime).isoformat(timespec="seconds")
        n[name] = len(df)
        for code, mm in zip(df["종목코드"], df["결산월"]):
            code = str(code).strip().zfill(6)
            if month(mm):
                by[code] = month(mm)
    out = {"as_of": AS_OF.isoformat(), "fetched": fetched,
           "source": "KIND 상장법인목록 corpgeneral/corpList.do?method=download (krx_kind_data_api corp_list)",
           "n": n, "settle_month": dict(sorted(by.items()))}
    old = read_json(OUT) if OUT.exists() else None
    if old != out:
        write_json(OUT, out)
    print(f"s02d 현재 결산월: {n} · 결산월 있는 종목 {len(by)} → {OUT.relative_to(INTERIM.parent.parent)}")
    return out


if __name__ == "__main__":
    main()
