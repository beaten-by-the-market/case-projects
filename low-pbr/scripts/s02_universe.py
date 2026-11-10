"""s02 회차별 산정 대상(모집단) 스냅샷 + 종류주 매핑.

원천
  · KIND 상장종목현황 상세(listed_issue_status) — 기준일 스냅샷, secugrpId=ST(주권).
    스팩(SP)·외국주권(FS)·리츠·투자회사(MF)·DR 은 증권구분이 달라 여기서 이미 빠진다 (R12 일부).
  · KRX 정보데이터시스템 전종목기본정보(listed_stocks)·상장폐지종목(delisted) — 종류주(우선주) 목록.
    시가총액에 "상장된 종류주권의 시가총액 포함"(보도자료 주1) 이라 보통주 회사에 붙여야 한다.

관리종목·환기종목·실질심사 제외(R12 나머지)는 여기서 하지 않고 플래그만 단다 —
어떤 제외 조합이 779/1,652 를 맞추는지 s06 에서 판정한다 (docs/01-재현사양.md A5).

출력
  data/interim/universe_snap.csv   round, market, corp_name, code, list_date, shares_k
  data/interim/pref_map.csv        pref_code, pref_name, common_code, kind, list_date, delist_date
  data/interim/admin_flags.csv     현재 관리종목 목록(지정일·사유) — 2026.11 회차 판정용
"""
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ROOT  # noqa: E402

INTER = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw" / "kind"


def cached(name: str, fn):
    """KIND/KRX 응답을 data/raw/kind 에 CSV 로 캐시한다."""
    f = RAW / f"{name}.csv"
    if f.exists():
        return pd.read_csv(f, dtype=str, keep_default_na=False)
    df = fn().astype(str)
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False, encoding="utf-8")
    return df


def main():
    from krx_kind_data_api import fetch as kind
    from krx_data_api import fetch as krx

    rounds = list(csv.DictReader(open(INTER / "rounds.csv", encoding="utf-8")))
    snaps = []
    for r in rounds:
        for mk, mkt in (("STK", "KOSPI"), ("KSQ", "KOSDAQ")):
            df = cached(f"listed_{mk}_{r['base_date']}",
                        lambda: kind("listed_issue_status", selDate=r["base_date"], mktId=mk, secugrpId="ST"))
            for _, x in df.iterrows():
                snaps.append({"round": r["round"], "base_date": r["base_date"], "market": mkt,
                              "corp_name": x["회사명"], "code": x["종목코드"].zfill(6),
                              "list_date": x["상장일"], "shares_k": x["상장주식수(천주)"]})
            print(r["round"], mkt, len(df))
    pd.DataFrame(snaps).to_csv(INTER / "universe_snap.csv", index=False, encoding="utf-8")

    # 종류주: 현재 상장분 + 2020.09 이후 상장폐지분
    cur = cached("krx_listed_stocks", lambda: krx("listed_stocks"))
    dl = cached("krx_delisted_20200901_20261110", lambda: krx("delisted", strtDd="20200901", endDd="20261110"))
    commons = {s["code"] for s in snaps}
    pref = []
    for _, x in cur[(cur["KIND_STKCERT_TP_NM"] != "보통주") & (cur["SECUGRP_NM"] == "주권")].iterrows():
        pref.append({"pref_code": x["ISU_SRT_CD"], "pref_name": x["ISU_ABBRV"], "kind": x["KIND_STKCERT_TP_NM"],
                     "list_date": x["LIST_DD"].replace("/", "-"), "delist_date": ""})
    for _, x in dl[(dl["주식종류"] != "보통주") & (dl["증권구분"] == "주권")].iterrows():
        pref.append({"pref_code": x["종목코드"], "pref_name": x["종목명"], "kind": x["주식종류"],
                     "list_date": x["상장일"].replace("/", "-"), "delist_date": x["폐지일"].replace("/", "-")})
    # 종류주 코드 → 보통주 코드: 앞 5자리가 같고 끝자리가 0 인 보통주 (005935 → 005930, 00088K → 000880)
    for p in pref:
        cand = p["pref_code"][:5] + "0"
        p["common_code"] = cand if cand in commons else ""
    pdf = pd.DataFrame(pref).drop_duplicates("pref_code")
    pdf.to_csv(INTER / "pref_map.csv", index=False, encoding="utf-8")
    print(f"종류주 {len(pdf)}종목, 보통주 매핑 {(pdf['common_code'] != '').sum()} / 미매핑 {(pdf['common_code'] == '').sum()}")

    adm = cached("kind_admin_issue_20261110", lambda: kind("admin_issue"))
    adm.to_csv(INTER / "admin_flags.csv", index=False, encoding="utf-8")
    print("관리종목(현재)", len(adm))


if __name__ == "__main__":
    main()
