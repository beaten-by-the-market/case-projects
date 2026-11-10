"""s10 KIND 밸류업 페이지 — 저PBR 공표 목록 · 기업가치 제고계획 공시 목록 (최종 대조 기준).

KIND 화면 백엔드 (kind.krx.co.kr, 2026-11-10 확인)
  저PBR기업        POST /valueup/lowpbr.do     method=valueupLowpbrSub    forward=valueupLowpbr_sub
                   appldDd=YYYYMMDD(공표일), marketType, gicsSectCd(10~60)
                   열: 번호 · 회사명(시장 아이콘·법인코드 5자리·환기종목 아이콘) · 공표일자 · PBR · GICS업종 · PBR기준일 · 결산월
  밸류업 공시현황  POST /valueup/disclsstat.do method=valueupDisclsStatSub forward=valueupDisclsStat_sub
                   fromDate/toDate(YYYY-MM-DD) · 열: 번호 · 공시일시 · 회사명 · 공시제목(openDisclsViewer('접수번호'))

법인코드 5자리 = 보통주 종목코드 앞 5자리 (광동제약 00929 ↔ 009290).

출력
  data/final/kind_lowpbr_20261102.csv
  data/final/kind_valueup_discl.csv     (kind_url = KIND 공시뷰어)
"""
import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ROOT  # noqa: E402

RAW = ROOT / "data" / "raw" / "kind"
OUT = ROOT / "data" / "final"
UA = {"User-Agent": "Mozilla/5.0"}
KIND_VIEWER = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={}"

ROW_LOWPBR = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(\d+)</td>\s*<td>(.*?)</td>\s*<td[^>]*>([\d-]+)</td>\s*<td[^>]*>([\d.]+)</td>\s*"
    r"<td[^>]*>([^<]+)</td>\s*<td[^>]*>([\d-]+)</td>\s*<td[^>]*>(\d+)</td>", re.S)
ROW_DISCL = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>([\d\- :]+)</td>\s*<td>(.*?)</td>\s*<td>.*?"
    r"openDisclsViewer\('(\d+)'.*?title='([^']*)'", re.S)
CORP = re.compile(r"companysummary_open\('(\w+)'\)")
NAME = re.compile(r"title='([^']*)'")


def post(path: str, data: dict, cache: str) -> str:
    f = RAW / cache
    if f.exists():
        return f.read_text(encoding="utf-8")
    r = requests.post("https://kind.krx.co.kr" + path, data=data, headers=UA, timeout=120)
    r.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    f.write_text(r.text, encoding="utf-8")
    return r.text


def cell_corp(html: str) -> dict:
    alts = re.findall(r"alt='([^']+)'", html)
    return {"corp5": CORP.search(html)[1], "name": NAME.search(html)[1].replace("&amp;", "&"),
            "market": "KOSPI" if "유가증권" in alts else "KOSDAQ" if "코스닥" in alts else "",
            "flags": "|".join(a for a in alts if a not in ("유가증권", "코스닥"))}


def main():
    html = post("/valueup/lowpbr.do", {
        "method": "valueupLowpbrSub", "forward": "valueupLowpbr_sub", "currentPageSize": "3000",
        "pageIndex": "1", "orderMode": "0", "orderStat": "D", "marketType": "", "gicsSectCd": "",
        "appldDd": "20261102", "searchCorpName": ""}, "kind_lowpbr_20261102.html")
    rows = [{"no": int(m[1]), **cell_corp(m[2]), "pub_date": m[3], "pbr": m[4], "gics": m[5].strip(),
             "base_date": m[6], "fye_month": int(m[7])} for m in ROW_LOWPBR.finditer(html)]
    df = pd.DataFrame(rows)
    assert len(df) == 151, len(df)
    assert (df.market.value_counts().to_dict() == {"KOSPI": 96, "KOSDAQ": 55})
    df.to_csv(OUT / "kind_lowpbr_20261102.csv", index=False, encoding="utf-8-sig")
    print("KIND 저PBR", len(df), df.market.value_counts().to_dict(), "· 플래그:", df.loc[df["flags"] != "저PBR", ["name", "flags"]].values.tolist())

    html = post("/valueup/disclsstat.do", {
        "method": "valueupDisclsStatSub", "forward": "valueupDisclsStat_sub", "currentPageSize": "5000",
        "pageIndex": "1", "orderMode": "0", "orderStat": "D", "marketType": "", "fromDate": "2024-05-01",
        "toDate": "2026-11-10", "searchCorpName": ""}, "kind_valueup_discl_20240501_20261110.html")
    rows = []
    for m in ROW_DISCL.finditer(html):
        c = cell_corp(m[3])
        rows.append({"no": int(m[1]), "disc_dt": m[2].strip(), **c, "acptno": m[4],
                     "title": m[5].replace("&amp;", "&"), "kind_url": KIND_VIEWER.format(m[4])})
    dd = pd.DataFrame(rows)
    dd.to_csv(OUT / "kind_valueup_discl.csv", index=False, encoding="utf-8-sig")
    print("KIND 밸류업 공시", len(dd), "· 기간", dd.disc_dt.min(), "~", dd.disc_dt.max(),
          "· 10.22 이전", (dd.disc_dt <= "2026-10-22 23:59").sum())
    print(dd.title.str.replace(r"^\[[^\]]*\]", "", regex=True).value_counts().head(8).to_string())


if __name__ == "__main__":
    main()
