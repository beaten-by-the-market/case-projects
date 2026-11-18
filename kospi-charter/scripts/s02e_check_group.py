"""s02e 확인그룹 · 상장공시시스템 배당기준일 신고 — 사용자가 준 코스피 종목별 엑셀

사용자 지시(2026-11-17): 확인그룹을 웹페이지 필터로 둔다(코스닥 등은 '-').
사용자 지시(2026-11-17, v2): 회사가 상장공시시스템에 신고한 배당기준일(엑셀 I열 '신고' · J열 '배당기준일')을 배당기준일 탭에 정관 태그와
나란히 보여 불일치를 바로 찾게 한다. 엑셀은 확인자 이름(K~N열)만 빼고 공개해도 된다 → 이름을 뺀 사본
`source/유가증권시장_확인그룹v2_이름제외.xlsx` 를 커밋하고, 이 스크립트는 그 사본을 읽는다(이름 열은 사본에 없다).

입력  source/유가증권시장_확인그룹v2_이름제외.xlsx (--src 로 바꿈) — 열 '종목코드' · '확인자그룹' · '배당기준일 조건' · '신고' · '배당기준일'
출력  data/interim/s02e_check_group.json
      {source, sha256, n, groups: {그룹: 회사 수}, check_group: {종목코드: 그룹(정수)},
       filed_n: {신고값: 회사 수}, filed: {종목코드: {filed: Y|N|YorN|미입력, filed_date: YYYY-MM-DD|"", filed_cond: H열}}}
      → s08 이 data.js 의 check_group 으로, s10 이 dividend.js 배당기준일 표의 filed* 열로 넣는다

사용자 지시(2026-11-17): 코스닥도 같은 방식 — `2026_코스닥_배당기준일.xlsx`(상장공시시스템 배당기준일 현황, 1,840종목)는 회사 담당자
이름·직위·전화·휴대폰·이메일(L·M·V~Z열)을 뺀 사본 `source/코스닥_배당기준일_2026_담당자제외.xlsx` 를 커밋하고 그 사본을 읽는다.
'배당기준일조건' 이 '이사회 결의로 정한 날' = N, '특정일' = Y, 빈칸 = 미입력(코스피 엑셀의 '신고' 열과 같은 규칙), '배당기준일' 은 그대로.
확인그룹은 코스피만.

신고 값: 엑셀 I열 그대로(Y · N · 미입력). 상장공시시스템에 아직 없는 'Y/N'(택일)이 나중에 들어오면 화면 표기와 같은 YorN 으로 읽는다.
배당기준일(J열)은 '-'·빈칸이면 빈 값.

    python -X utf8 scripts/s02e_check_group.py [--src 경로]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import INTERIM, ROOT, read_json, write_json  # noqa: E402

DEFAULT = ROOT / "source" / "유가증권시장_확인그룹v2_이름제외.xlsx"
KOSDAQ = ROOT / "source" / "코스닥_배당기준일_2026_담당자제외.xlsx"
COND = {"이사회 결의로 정한 날": "N", "특정일": "Y", "": "미입력"}      # 코스닥 '배당기준일조건' → 신고 값
OUT = INTERIM / "s02e_check_group.json"
FILED = {"Y": "Y", "N": "N", "Y/N": "YorN", "YORN": "YorN", "미입력": "미입력", "": "미입력"}   # 키는 대문자·공백 없앤 값


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT))
    ap.add_argument("--src-kosdaq", default=str(KOSDAQ))
    a, _ = ap.parse_known_args()
    src = Path(a.src)
    df = pd.read_excel(src, dtype=str, usecols=["종목코드", "확인자그룹", "배당기준일 조건", "신고", "배당기준일"]).fillna("")
    groups, filed = {}, {}
    for _, r in df.iterrows():
        code = str(r["종목코드"]).strip().zfill(6)
        if not code.strip("0"):
            continue
        g = str(r["확인자그룹"]).strip()
        if g:
            groups[code] = int(float(g))
        raw = str(r["신고"]).strip()
        f = FILED.get(raw.upper().replace(" ", ""))
        if f is None:
            raise SystemExit(f"s02e: 알 수 없는 신고 값 {raw!r} ({code})")
        d = str(r["배당기준일"]).strip()
        d = d[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", d) else ""
        filed[code] = {"filed": f, "filed_date": d, "filed_cond": str(r["배당기준일 조건"]).strip()}
    for _, x in filed.items():
        x["market"] = "코스피"
    kq = Path(a.src_kosdaq)
    if kq.exists():                              # 코스닥 (상장공시시스템 배당기준일 현황, 2줄 머리 — 둘째 줄은 기준일·공시일 작은 머리)
        dk = pd.read_excel(kq, dtype=str, header=0, skiprows=[1]).fillna("")
        dk.columns = [re.sub(r"\s+", "", str(c)) for c in dk.columns]
        for _, r in dk.iterrows():
            code = str(r["종목코드"]).strip()
            if not code:
                continue
            cond = str(r["배당기준일조건"]).strip()
            if cond not in COND:
                raise SystemExit(f"s02e: 알 수 없는 코스닥 배당기준일조건 {cond!r} ({code})")
            d = str(r["배당기준일"]).strip()
            filed[code] = {"filed": COND[cond], "filed_date": d[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", d) else "",
                           "filed_cond": cond, "market": "코스닥"}
    out = {"source": src.name, "source_kosdaq": kq.name if kq.exists() else None,
           "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
           "sha256_kosdaq": hashlib.sha256(kq.read_bytes()).hexdigest() if kq.exists() else None, "n": len(groups),
           "groups": {str(k): v for k, v in sorted(Counter(groups.values()).items())}, "check_group": dict(sorted(groups.items())),
           "filed_n": {m: dict(Counter(x["filed"] for x in filed.values() if x["market"] == m).most_common()) for m in ("코스피", "코스닥")},
           "filed": dict(sorted(filed.items()))}
    if (read_json(OUT) if OUT.exists() else None) != out:
        write_json(OUT, out)
    print(f"s02e 확인그룹 {out['n']}사 {out['groups']} · 신고 {out['filed_n']} → {OUT.name}")
    return out


if __name__ == "__main__":
    main()
