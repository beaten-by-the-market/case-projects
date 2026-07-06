"""
SEIBRO 외화증권 '일별' 결제대금/보관잔고 수집 (국가=HK).

두 화면 모두 영업일마다 단일일(start=end 또는 기준일) 1콜을 날려 일별 시계열을 만든다.
공휴일·미posting일은 빈 응답 → 스킵. 단위 USD. 출처: 한국예탁결제원 증권정보포털(SEIBro).

  --kind settlement : 결제대금 (매수/매도/합계/순매수). 결제완료일(T+2) 기준.
  --kind holdings   : 보관잔고 (기준일 스냅샷 잔고). 최근 1~2일은 지연.

I/O 바운드라 스레드 병렬 유효하나 SEIBRO 단일 서버라 동시성은 낮게(기본 5)+재시도.

사용:
    python seibro_daily.py --kind settlement --start 2025-05-26 --end 2026-07-03
    python seibro_daily.py --kind holdings   --start 2025-05-26 --end 2026-07-03
"""

import argparse
import concurrent.futures as cf
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import pandas as pd
import requests

# 어디서 실행하든 프로젝트 루트 기준으로 data/ 접근 (이 파일은 scripts/ 한 단계 아래)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

URL = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"
TASK = "ksd.safe.bip.cnts.OvsSec.process.OvsSecIsinPTask"
W2X = "/IPORTAL/user/ovsSec/BIP_CNTS10013V.xml"
MENU_NO = "921"
CMM_BTN = "total_search,openall,print,hwp,word,pdf,seach,"
_COMMON = {"NATION_NM": "국가명", "ISIN": "ISIN", "KOR_SECN_NM": "종목명"}

# 화면별 설정
KINDS = {
    "settlement": {
        "action": "getImptFrcurStkSetlAmtList", "s_type": "2", "d_type": "3",
        "rename": {**_COMMON, "SUM_FRSEC_BUY_AMT": "매수대금", "SUM_FRSEC_SELL_AMT": "매도대금",
                   "SUM_FRSEC_TOT_AMT": "매수매도대금", "SUM_FRSEC_NET_BUY_AMT": "순매수대금"},
        "amt_cols": ["매수대금", "매도대금", "매수매도대금", "순매수대금"],
        "sort_col": "매수매도대금",
    },
    "holdings": {
        "action": "getImptFrcurStkCusRemaList", "s_type": "1", "d_type": "3",
        "rename": {**_COMMON, "SUM_FRSEC_AMT": "보관잔고금액"},
        "amt_cols": ["보관잔고금액"],
        "sort_col": "보관잔고금액",
    },
}
# 관심 종목(레버리지 ETP): 삼성=7747/9747(ISIN 공유), 하이닉스=7709
LEVERAGE_ISINS = {"HK0001121349": "삼성 2x (7747/9747)", "HK0001205258": "SK하이닉스 2x (7709)"}


def _headers(action: str) -> dict:
    return {
        "Content-Type": 'application/xml; charset="UTF-8"', "Accept": "application/xml",
        "Origin": "https://seibro.or.kr",
        "Referer": f"https://seibro.or.kr/websquare/control.jsp?w2xPath={W2X}&menuNo={MENU_NO}",
        "submissionid": "submission_" + action,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
    }


def fetch_day(day: str, country: str, cfg: dict, retries: int = 3):
    """day='YYYYMMDD' 하루치 rows. 실패 시 재시도. 빈 날은 []."""
    payload = (
        f'<reqParam action="{cfg["action"]}" task="{TASK}">'
        f'<MENU_NO value="{MENU_NO}"/><CMM_BTN_ABBR_NM value="{CMM_BTN}"/>'
        f'<W2XPATH value="{W2X}"/><PG_START value="1"/><PG_END value="50"/>'
        f'<START_DT value="{day}"/><END_DT value="{day}"/>'
        f'<S_TYPE value="{cfg["s_type"]}"/><S_COUNTRY value="{country}"/>'
        f'<D_TYPE value="{cfg["d_type"]}"/></reqParam>'
    )
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(URL, data=payload.encode("utf-8"),
                              headers=_headers(cfg["action"]), timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.content.decode("utf-8", "replace"))
            out = []
            for res in root.findall(".//data/result"):
                row = {c.tag: c.attrib.get("value", "") for c in res}
                rec = {"Date": f"{day[:4]}-{day[4:6]}-{day[6:]}"}
                rec.update({cfg["rename"].get(k, k): v for k, v in row.items() if k in cfg["rename"]})
                out.append(rec)
            return out
        except Exception as e:
            last = e
            time.sleep(0.8 * (attempt + 1))
    print(f"[실패] {day}: {last}", file=sys.stderr)
    return []


def business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:            # 우리 거래일 캘린더 없이 월~금 전부 조회
            yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser(description="SEIBRO 외화증권 일별 결제대금/보관잔고 (HK)")
    ap.add_argument("--kind", choices=list(KINDS), default="settlement")
    ap.add_argument("--start", default="2025-05-26")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m-%d"))
    ap.add_argument("--country", default="HK")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()
    cfg = KINDS[args.kind]

    s = datetime.strptime(args.start, "%Y-%m-%d").date()
    e = datetime.strptime(args.end, "%Y-%m-%d").date()
    days = list(business_days(s, e))
    print(f"[SEIBRO] {args.country} 일별 {args.kind}: {len(days)}영업일 "
          f"({args.start}~{args.end}), 동시성 {args.workers}", flush=True)

    all_rows, done, empty = [], 0, 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_day, d, args.country, cfg): d for d in days}
        for fut in cf.as_completed(futs):
            rows = fut.result()
            all_rows.extend(rows)
            done += 1
            empty += (not rows)
            if done % 25 == 0 or done == len(days):
                print(f"  진행 {done}/{len(days)} (빈날 {empty}, 누적행 {len(all_rows)})", flush=True)

    if not all_rows:
        sys.exit("수집된 행이 없습니다.")
    df = pd.DataFrame(all_rows)
    for c in cfg["amt_cols"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df = df.sort_values(["Date", cfg["sort_col"]], ascending=[True, False]).reset_index(drop=True)

    os.makedirs(args.outdir, exist_ok=True)
    full = os.path.join(args.outdir, f"seibro_{args.country}_{args.kind}_daily.csv")
    df.to_csv(full, index=False, encoding="utf-8-sig")
    print(f"[완료] 전체 top50/일: {len(df)}행 -> {full}")

    lev = df[df["ISIN"].isin(LEVERAGE_ISINS)].copy()
    lev["종목구분"] = lev["ISIN"].map(LEVERAGE_ISINS)
    levout = os.path.join(args.outdir, f"seibro_{args.country}_{args.kind}_leverage_daily.csv")
    lev.to_csv(levout, index=False, encoding="utf-8-sig")
    print(f"[완료] 레버리지 2종목: {len(lev)}행 -> {levout}")
    print(lev.groupby("종목구분")[cfg["amt_cols"][-1]].agg(["count", "min", "max"]).to_string())


if __name__ == "__main__":
    main()
