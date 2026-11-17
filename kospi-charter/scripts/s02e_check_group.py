"""s02e 확인그룹 — 사용자가 준 '유가증권시장_확인자그룹.xlsx' 의 종목별 확인자그룹 번호

사용자 지시(2026-11-17): 확인그룹 칼럼을 웹페이지 각 탭에 넣는다. 코스닥(과 그 밖의 시장)은 비어 있으므로 '-'.
엑셀에는 확인자 이름도 있으나 웹페이지는 공개라 **그룹 번호만** 옮긴다(이름은 읽지도 쓰지도 않는다). 엑셀 파일은 커밋하지 않는다.

입력  엑셀 경로 (기본 C:/Users/Peter/Downloads/유가증권시장_확인자그룹.xlsx, --src 로 바꿈) — 열 '종목코드' · '확인자그룹'
출력  data/interim/s02e_check_group.json  {source, sha256, n, groups: {그룹: 회사 수}, check_group: {종목코드: 그룹(정수)}}
      → s08 이 data.js 의 check_group 으로 넣는다

    python -X utf8 scripts/s02e_check_group.py [--src 경로]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import INTERIM, read_json, write_json  # noqa: E402

DEFAULT = Path(r"C:/Users/Peter/Downloads/유가증권시장_확인자그룹.xlsx")
OUT = INTERIM / "s02e_check_group.json"


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT))
    a, _ = ap.parse_known_args()
    src = Path(a.src)
    df = pd.read_excel(src, dtype=str, usecols=["종목코드", "확인자그룹"])
    groups = {}
    for code, g in zip(df["종목코드"], df["확인자그룹"]):
        code, g = str(code).strip().zfill(6), str(g).strip()
        if code and g and g.lower() != "nan":
            groups[code] = int(float(g))
    out = {"source": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "n": len(groups),
           "groups": {str(k): v for k, v in sorted(Counter(groups.values()).items())}, "check_group": dict(sorted(groups.items()))}
    if (read_json(OUT) if OUT.exists() else None) != out:
        write_json(OUT, out)
    print(f"s02e 확인그룹 {out['n']}사 {out['groups']} → {OUT.name}")
    return out


if __name__ == "__main__":
    main()
