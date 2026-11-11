"""s11 회차별 GICS 업종 — KRX 지수 사이트 'GICS 산업분류 › 산업별 종목현황'.

화면: https://index.krx.co.kr/contents/MKD/03/0303/03030204/MKD03030204.jsp  (사용자 제공, 2026-11-11)
백엔드: OTP 발급 GET /contents/COM/GenerateOTP.jspx?bld=/IDX/03/0303/03030204/mkd03030204_03&name=tablesubmit
        → POST /contents/IDX/99/IDX99000001.jspx  code·bldcode·mkt_tp_cd(STK|KSQ)·gics_ind_grp_cd(10~60)·date(YYYYMMDD)
        응답 block1 = 종목코드(isu_cd)·종목약명·시세. 조회일자를 과거로 주면 그날의 분류가 나온다
        (2020.10.22 유가 에너지에 GS 포함 9종목, 2026.10.22 은 10종목 = 보도자료 붙임1).

지침: 소속업종은 PBR 기준일 당시의 업종(김앤장 해설) → 회차마다 그 기준일로 받는다.
어느 섹터 목록에도 없는 회사 = 업종미분류.

GICS 는 MSCI·S&P 의 분류라 종목별 매핑 파일은 공개 레포에 올리지 않는다(.gitignore). 다시 받으면 된다.

출력: data/interim/gics_krx.csv  round, base_date, market, sector_cd, sector, code, name
"""
import csv
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _rules import ROOT, load_rounds  # noqa: E402

B = "https://index.krx.co.kr"
PAGE = B + "/contents/MKD/03/0303/03030204/MKD03030204.jsp"
BLD = "/IDX/03/0303/03030204/mkd03030204_03"
SECTORS = {"10": "에너지", "15": "소재", "20": "산업재", "25": "자유소비재", "30": "필수소비재", "35": "헬스케어",
           "40": "금융", "45": "정보기술", "50": "커뮤니케이션", "55": "유틸리티", "60": "부동산"}
RAW = ROOT / "data/raw/krx_gics"
OUT = ROOT / "data/interim/gics_krx.csv"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": PAGE})
    s.get(PAGE, timeout=30)
    return s


def fetch(s, mk, sec, date):
    f = RAW / f"{date}_{mk}_{sec}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            time.sleep(0.5)
            otp = s.get(B + "/contents/COM/GenerateOTP.jspx", params={"bld": BLD, "name": "tablesubmit"}, timeout=30).text
            j = s.post(B + "/contents/IDX/99/IDX99000001.jspx", timeout=60,
                       data={"code": otp, "bldcode": BLD, "mkt_tp_cd": mk, "gics_ind_grp_cd": sec, "date": date}).json()
            rows = j[next(iter(j))]
            RAW.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            return rows
        except (requests.RequestException, ValueError, StopIteration):
            time.sleep(5 * (attempt + 1))
            s = session()
    raise RuntimeError(f"GICS 조회 실패 {date} {mk} {sec}")


def main():
    s = session()
    out = []
    for r in load_rounds():
        for mk, mkt in (("STK", "KOSPI"), ("KSQ", "KOSDAQ")):
            n = 0
            for cd, nm in SECTORS.items():
                for x in fetch(s, mk, cd, r["base_date"]):
                    out.append({"round": r["round"], "base_date": r["base_date"], "market": mkt, "sector_cd": cd,
                                "sector": nm, "code": x["isu_cd"], "name": x["isu_abbr"]})
                    n += 1
            print(r["round"], mkt, n, flush=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{OUT.relative_to(ROOT)} {len(out)}행")


if __name__ == "__main__":
    main()
