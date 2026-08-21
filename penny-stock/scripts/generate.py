"""penny-stock 대시보드 데이터 생성 파이프라인.

공유 패키지를 import해서 사용한다(이 프로젝트는 판정 엔진을 중복 두지 않음):
  - krx-data-api      : 전종목시세 캐시·스크리너·판정 로직·대시보드 artifacts 생성기
  - krx-kind-data-api : KIND 상장종목현황(유니버스)·관리종목 지정일·변경상장
  - seibro-api        : 예탁결제원 권리일정(액면병합·자본감소 비율)
세 패키지 모두 editable 설치되어 있어야 한다(pip install -e <repo>).

사용:
  python scripts/generate.py                # 캐시가 있으면 그대로, 데이터만 재생성
  python scripts/generate.py --refresh      # 스냅샷·유니버스까지 새로 수집 후 재생성
  python scripts/generate.py --refresh 20260901      # 종료일을 특정 날짜로 고정(선택)
  python scripts/generate.py --refresh --force-today # 마감 전 가드를 무시하고 당일 포함
종료일(END)은 기본 '오늘'이며, update_cache가 실제 최신 매매거래일까지만 증분 수집한다.
단 종가 확정 시각(16:00) 전에 돌리면 당일을 수집 대상에서 제외한다(resolve_end 참조).
결과: data/dashboard_data.json (프론트가 embed). 이후 web/build.py로 배포본 생성.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from krx_data_api import daily_snapshots as ds, screener as scr, dashboard
from krx_data_api import corporate_actions as ca
from krx_data_api.client import fetch
from krx_kind_data_api import fetch as kfetch

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = str(DATA / "snapshots.csv")
UNI = str(DATA / "target_universe.csv")
OUT = str(DATA / "dashboard_data.json")

# 스냅샷 수집 시작일(90거래일 이상 이력 확보를 위한 역사 앵커). 종료일은 실행 시 자동 산정.
START = "20260401"

# 당일 종가가 확정되는 시각(정규장 마감 15:30 + 시세 정리 여유). 이 시각 전에는 당일을 수집하지 않는다.
SETTLE_HM = (16, 0)


def resolve_end(argv=(), now=None):
    """수집 종료일(YYYYMMDD).

    - 8자리 날짜를 인자로 주면 그 값을 그대로 쓴다(명시 지정이므로 가드 미적용).
    - 없으면 '오늘'. 단 종가 확정 시각(SETTLE_HM) 전이면 전일로 당긴다.

    가드가 필요한 이유: 장중에 호출하면 KRX가 당일 행을 '현재가'로 내려주는데,
    update_cache는 증분이라 한 번 캐시에 들어간 날짜를 다시 받지 않는다. 그대로 두면
    장중가가 확정 종가 자리에 영구히 고정되어 그 날의 미달 판정·연속일 카운트가
    계속 틀어진다(2026-08-20 10:43 실행에서 실제로 발생, 삼성전자 거래량이 전일의
    35%인 장중 스냅샷이 수집됨 → 해당 행을 제거하고 재생성해 복구).

    휴장일·주말에 전일로 당겨도 무해하다. update_cache가 [START, end] 안의 실제
    매매거래일만 수집하므로 최신 거래일까지는 그대로 들어온다.
    --force-today 를 주면 가드를 건너뛴다(의도적 장중 조회용).
    """
    argv = list(argv)
    for a in argv:
        if a.isdigit() and len(a) == 8:
            return a
    now = now or datetime.now()
    if "--force-today" not in argv and (now.hour, now.minute) < SETTLE_HM:
        end = (now - timedelta(days=1)).strftime("%Y%m%d")
        print(f"[가드] 현재 {now:%H:%M} — 당일 종가 미확정({SETTLE_HM[0]:02d}:{SETTLE_HM[1]:02d} 이후 확정). "
              f"종료일을 {end}로 당깁니다. 장중 데이터가 필요하면 --force-today.")
        return end
    return now.strftime("%Y%m%d")


def retry(fn, *a, **k):
    last = None
    for _ in range(4):
        try:
            return fn(*a, **k)
        except Exception as e:
            last = e
            print("  retry:", str(e)[:60])
            time.sleep(3)
    print("  실패:", last)
    return None


def _ymd(s):
    return str(s).replace("/", "").replace("-", "").strip()[:8]


def build_actions(rows):
    """kind 변경상장(일자·사유, 전종목 1콜) + SEIBro(발행일·비율, 대상만) 병합."""
    name2srt = {r["name"]: r["code"] for r in rows}
    important = {r["code"] for r in rows if r["state"] != "below"}  # SEIBro 조회 대상
    k = retry(kfetch, "stock_issue_list", fromDate="2025-05-01",
              toDate="2026-07-31", listingType="3")
    if k is None:
        return {}
    k = k[k["발행사유"].str.contains("병합|감자", na=False)]
    kind_ev = {}
    for _, r in k.iterrows():
        nm = str(r["회사명"]).strip()
        if nm not in name2srt:
            continue
        kind_ev.setdefault(name2srt[nm], []).append(
            {"krx_list_date": _ymd(r["상장(예정)일"]), "krx_reason": str(r["발행사유"]).strip()}
        )
    seibro = {}
    for srt in (set(kind_ev) & important):
        seibro[srt] = retry(ca.reverse_split_events, srt, "20250101", "20260731") or []

    actions = {}
    for srt, kevs in kind_ev.items():
        ks = seibro.get(srt, [])
        merged = []
        for ke in kevs:
            ev = {"krx_list_date": ke["krx_list_date"], "krx_reason": ke["krx_reason"],
                  "ksd_issue_date": None, "ksd_list_date": None,
                  "ksd_reason": None, "ksd_ratio": None}
            best, bd = None, 99
            for s in ks:
                try:
                    diff = abs((pd.to_datetime(s["date"]) - pd.to_datetime(ke["krx_list_date"])).days)
                except Exception:
                    diff = 99
                if diff < bd:
                    bd, best = diff, s
            if best and bd <= 10:
                ev.update({"ksd_issue_date": best.get("issue_date"), "ksd_list_date": best.get("date"),
                           "ksd_reason": best.get("type"),
                           "ksd_ratio": round(best["ratio"], 3) if best.get("ratio") else None})
            merged.append(ev)
        merged.sort(key=lambda e: e["krx_list_date"])
        actions[srt] = merged
    return actions


def main(refresh=False, end=None):
    end = end or resolve_end()
    if refresh:
        print(f"스냅샷 증분 수집 (…~{end}, 실제 최신 매매거래일까지)…")
        ds.update_cache(START, end, CACHE)
        print("유니버스 갱신…")
        scr.build_target_universe(end, save_csv=UNI)

    cache = ds.load_cache(CACHE)
    uni = scr.target_codes(scr.load_target_universe(UNI))
    print(f"캐시 {cache['일자'].nunique()}거래일 · 유니버스 {len(uni)}종목")

    sup = retry(fetch, "supervised")            # KRX 공식 관리종목현황(대조·지정일)
    adm = retry(kfetch, "admin_issue")          # KIND 관리종목 지정일(종목명 매칭)

    art0 = dashboard.build_dashboard_artifacts(cache, uni, supervised=sup, admin_issue=adm)
    actions = build_actions(art0["rows"])
    codes = sorted({r["code"] for r in art0["rows"]})

    art = dashboard.build_dashboard_artifacts(
        cache, uni, supervised=sup, admin_issue=adm,
        actions_by_code=actions, series_codes=codes, out_json=OUT,
    )
    print(f"생성 완료: {OUT}  ({len(art['rows'])}행, 시계열 {len(art['series'])}종목, "
          f"actions {sum(1 for v in art['series'].values() if v.get('actions'))}종목)")


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv, end=resolve_end(sys.argv[1:]))