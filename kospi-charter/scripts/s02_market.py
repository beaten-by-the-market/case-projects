"""s02 소속시장 — KIND 상장종목현황, 기준일(AS_OF) 현재 목록 한 번만

결정(2026-11-16, 사용자): 접수일마다 받지 않고 **기준일 현재 상장사 목록을 한 번만** 받아 그 시장을 쓴다.
한계 — 제출 뒤 상장폐지·이전상장·신규상장된 회사는 제출 당시가 아니라 현재 시장으로 분류된다
(예: 한창 005110 은 2026-03-26 제출 때 유가증권시장 상장사였지만 지금 목록에 없어 '기타').

  · KIND listed_issue_status(selDate=AS_OF, mktId, secugrpId)  — krx-kind-data-api 패키지
  · 같은 날 한 번에: 유가(STK) 주권·외국주권·투자회사·부동산투자회사·DR / 코스닥(KSQ) 주권·외국주권·스팩·DR / 코넥스(KNX) 주권
  · 기준일이 휴장일이면 목록이 비어 있다 → 직전 영업일 목록을 쓴다 (snap_date 에 남김)
  · 종목코드로 먼저 맞추고, 없으면 회사명(공백·(주) 제거)으로 맞춘다

출력
  data/interim/s02_listed_now.csv  기준일 현재 상장사 목록 (시장·증권구분·회사명·종목코드·상장일)
  data/interim/s02_market.json     rcept_no → market·sec_group·snap_date·match_by
  logs/s02_market_vs_corp_cls.csv  KIND 현재 시장과 OpenDART corp_cls 가 다른 행 (둘 다 '현재' 기준이라 거의 없어야 한다)
"""
import csv
import re
import sys
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, INTERIM, LOGS, RAW, read_json, write_json  # noqa: E402

MKT = {"STK": "코스피", "KSQ": "코스닥", "KNX": "코넥스"}
GROUPS = {"STK": ["ST", "FS", "MF", "RT", "DR"], "KSQ": ["ST", "FS", "SP", "DR"], "KNX": ["ST"]}
GRP = {"ST": "주권", "FS": "외국주권", "MF": "투자회사", "RT": "부동산투자회사", "DR": "주식예탁증권",
       "SP": "기업인수목적회사"}
CLS = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "기타"}
EMPTY_MARK = "조회된 결과값이 없습니다"


def norm_name(s: str) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").upper()


def snapshot(d, mkt: str, grp: str) -> pd.DataFrame:
    f = RAW / "kind" / f"listed_{d:%Y%m%d}_{mkt}_{grp}.csv"
    if f.exists():
        return pd.read_csv(f, dtype=str, keep_default_na=False)
    from krx_kind_data_api import fetch

    for i in range(4):
        try:
            df = fetch("listed_issue_status", selDate=f"{d:%Y%m%d}", mktId=mkt, secugrpId=grp).astype(str)
            break
        except Exception as e:  # noqa: BLE001
            print(f"  KIND 재시도 {i + 1}: {e}", flush=True)
            time.sleep(5 * (i + 1))
    else:
        raise SystemExit(f"KIND 실패 {d} {mkt} {grp}")
    if "구분" in df and df["구분"].str.contains(EMPTY_MARK).any():
        df = df.iloc[0:0]
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False, encoding="utf-8")
    time.sleep(0.5)
    return df


def listed_now() -> tuple[pd.DataFrame, str]:
    for k in range(10):                          # 휴장일이면 직전 영업일
        d = AS_OF - timedelta(days=k)
        if len(snapshot(d, "STK", "ST")) > 0:
            break
    else:
        raise SystemExit(f"{AS_OF} 이전 10일간 KIND 목록이 비어 있음")
    parts = []
    for mkt, grps in GROUPS.items():
        for g in grps:
            df = snapshot(d, mkt, g)
            if len(df):
                parts.append(df.assign(market=MKT[mkt], sec_group=GRP[g]))
    allx = pd.concat(parts, ignore_index=True)
    allx["종목코드"] = allx["종목코드"].str.zfill(6)
    return allx, f"{d:%Y%m%d}"


def main():
    reports = read_json(INTERIM / "s01_reports.json")
    now, snap = listed_now()
    now[["market", "sec_group", "회사명", "종목코드", "상장일"]].to_csv(
        INTERIM / "s02_listed_now.csv", index=False, encoding="utf-8-sig")
    print(f"KIND {snap} 현재 상장 목록 {len(now)}사:",
          now.groupby(["market", "sec_group"]).size().to_dict())

    by_code, by_name = {}, {}
    for _, x in now.iterrows():
        rec = {"market": x["market"], "sec_group": x["sec_group"], "kind_name": x["회사명"], "kind_code": x["종목코드"]}
        by_code.setdefault(x["종목코드"], rec)
        by_name.setdefault(norm_name(x["회사명"]), rec)

    out = {}
    for r in reports:
        rec, how = None, ""
        if r["stock_code"] and r["stock_code"] in by_code:
            rec, how = by_code[r["stock_code"]], "code"
        elif norm_name(r["corp_name"]) in by_name:
            rec, how = by_name[norm_name(r["corp_name"])], "name"
        out[r["rcept_no"]] = {"market": rec["market"] if rec else "기타", "sec_group": rec["sec_group"] if rec else "",
                              "snap_date": snap, "match_by": how,
                              "kind_name": rec["kind_name"] if rec else "", "kind_code": rec["kind_code"] if rec else ""}
    write_json(INTERIM / "s02_market.json", out)

    diff = [{"rcept_no": r["rcept_no"], "rcept_dt": r["rcept_dt"], "corp_name": r["corp_name"],
             "stock_code": r["stock_code"], "corp_cls": r["corp_cls"], **out[r["rcept_no"]]}
            for r in reports if CLS.get(r["corp_cls"]) != out[r["rcept_no"]]["market"]]
    LOGS.mkdir(exist_ok=True)
    with open(LOGS / "s02_market_vs_corp_cls.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(diff[0]) if diff else ["rcept_no"])
        w.writeheader()
        w.writerows(diff)

    print("소속시장(현재 기준):", dict(Counter(v["market"] for v in out.values())))
    print("증권구분:", dict(Counter(v["sec_group"] or "-" for v in out.values())))
    print("매칭 방법:", dict(Counter(v["match_by"] or "-" for v in out.values())))
    print(f"corp_cls 와 다른 행 {len(diff)}건 → logs/s02_market_vs_corp_cls.csv")
    return out


if __name__ == "__main__":
    main()
