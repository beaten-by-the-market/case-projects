# -*- coding: utf-8 -*-
"""후속 분석 — 공시 지연·집중일·제도 대안 효과.

`offhour_impact_*_ticks.txt`(체결 단위, 코스콤 체결장)를 읽어 세 가지를 산출한다.

  1. 공시 지연(정보 공백 분)과 시간외 거래대금·손실률의 상관
  2. 2026-08-12 집중일(38건이 18:00~19:11에 몰림) 별도 분석
  3. 제도 대안별 효과 — 공표 시각을 앞당길 때 정보 공백 체결이 얼마나 사라지는가

주의
----
- 입력·출력 모두 `results/` 아래다. 이 디렉터리는 gitignore 대상이며 체결 상세를
  추적 대상 파일로 옮기지 않는다(저장소가 public).
- 같은 (종목, 사유발생일)에 공시가 2건인 재공시 건은 체결이 중복 수록돼 있으므로
  체결 키로 dedup 한 뒤 집계한다.

사용:
    python krx-query/analyze_followups.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PROPOSAL_DATA = ROOT.parent / "proposal" / "data"

CLOSE_MIN = 15 * 60 + 30          # 15:30 종가 확정
OFFHOUR_OPEN = 15 * 60 + 40       # 15:40 시간외 개시


def latest(pattern: str) -> Path:
    files = sorted(glob.glob(str(RESULTS / pattern)))
    if not files:
        raise SystemExit(f"입력 없음: {pattern}")
    return Path(files[-1])


def load_ticks() -> pd.DataFrame:
    path = latest("offhour_impact_*_ticks.txt")
    df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    for c in ("체결가", "체결수량", "체결대금", "기준시가", "수익률(%)", "정지영업일수"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # 체결시각 HHMMSSmmm → 자정 기준 분
    t = df["체결시각"].astype(str).str.zfill(9)
    df["체결분"] = t.str[:2].astype(int) * 60 + t.str[2:4].astype(int)
    df["체결초"] = t.str[:2].astype(int) * 3600 + t.str[2:4].astype(int) * 60 + t.str[4:6].astype(int)
    # 공시시각 HHMM → 분, 정보 공백
    d = df["공시시각"].astype(str).str.zfill(4)
    df["공시분"] = d.str[:2].astype(int) * 60 + d.str[2:].astype(int)
    df["정보공백"] = df["공시분"] - CLOSE_MIN
    df["키"] = df["사유발생일"] + "_" + df["단축코드"]
    # 재공시 중복 제거 — 같은 (종목, 사유발생일)에 공시가 2건이면 동일한 체결 집합이
    # 공시마다 한 벌씩 실려 있다. 체결 행 자체로 dedup 하면 같은 시각·같은 수량의
    # 별개 체결까지 지워지므로, '가장 이른 공시 한 건'의 행만 남긴다.
    before = len(df)
    first = df.groupby("키")["공시분"].transform("min")
    df = df[df["공시분"] == first].copy()
    print(f"[ticks] {path.name}: {before}행 → dedup {len(df)}행 "
          f"(재공시 중복 {before - len(df)}행 제거)")
    return df


def per_case(df: pd.DataFrame) -> pd.DataFrame:
    """(종목, 사유발생일) 단위 집계 — 가장 이른 공시 기준."""
    g = df.groupby("키")
    out = pd.DataFrame({
        "사유발생일": g["사유발생일"].first(),
        "종목명": g["종목명"].first(),
        "단축코드": g["단축코드"].first(),
        "시장": g["시장"].first(),
        "사유": g["사유"].first(),
        "유형": g["유형"].first(),
        "공시분": g["공시분"].min(),
        "정보공백": g["정보공백"].min(),
        "체결건수": g.size(),
        "거래량": g["체결수량"].sum(),
        "거래대금": g["체결대금"].sum(),
        "정지영업일수": g["정지영업일수"].max(),
        "기준시가": g["기준시가"].first(),
    })
    # 대금가중 수익률(VWAP 기준과 동일한 정의)
    vw = df.assign(_w=df["체결대금"] * df["수익률(%)"]).groupby("키")["_w"].sum()
    out["수익률"] = (vw / out["거래대금"]).round(4)
    out["평가손익"] = (df.assign(
        _p=(df["기준시가"] - df["체결가"]) * df["체결수량"]).groupby("키")["_p"].sum())
    return out.reset_index(drop=True)


def corr_block(case: pd.DataFrame) -> dict:
    print("\n" + "=" * 74)
    print("[1] 공시 지연(정보 공백)과 피해 규모의 상관")
    print("=" * 74)
    c = case[case["거래대금"] > 0].copy()
    print(f"대상 {len(c)}건 (시간외 체결이 있었던 건)")
    print(f"정보 공백(분): 중앙값 {c['정보공백'].median():.0f} / "
          f"최소 {c['정보공백'].min():.0f} / 최대 {c['정보공백'].max():.0f}")

    res = {}
    for y, label in [("거래대금", "시간외 거래대금"),
                     ("체결건수", "체결건수"),
                     ("수익률", "수익률(%)")]:
        sub = c.dropna(subset=[y])
        pear = sub["정보공백"].corr(sub[y])
        spear = sub["정보공백"].corr(sub[y], method="spearman")
        res[y] = {"n": int(len(sub)), "pearson": round(float(pear), 3),
                  "spearman": round(float(spear), 3)}
        print(f"  정보공백 ↔ {label:16s} n={len(sub):3d}  "
              f"Pearson {pear:+.3f}  Spearman {spear:+.3f}")

    # 한탑 제외 재산출(이상치)
    c2 = c[c["단축코드"] != "002680"]
    p2 = c2.dropna(subset=["거래대금"])["정보공백"].corr(c2.dropna(subset=["거래대금"])["거래대금"])
    s2 = c2["정보공백"].corr(c2["거래대금"], method="spearman")
    res["거래대금_한탑제외"] = {"n": int(len(c2)), "pearson": round(float(p2), 3),
                            "spearman": round(float(s2), 3)}
    print(f"  (한탑 제외) 정보공백 ↔ 시간외 거래대금  n={len(c2)}  "
          f"Pearson {p2:+.3f}  Spearman {s2:+.3f}")

    print("\n  정보 공백 구간별 평균:")
    bins = [0, 120, 150, 180, 210, 999]
    labels = ["~120분", "120~150분", "150~180분", "180~210분", "210분~"]
    c["구간"] = pd.cut(c["정보공백"], bins=bins, labels=labels, right=False)
    tab = c.groupby("구간", observed=False).agg(
        건수=("거래대금", "size"),
        거래대금중앙값=("거래대금", "median"),
        거래대금평균=("거래대금", "mean"),
        수익률중앙값=("수익률", "median"))
    print(tab.round(2).to_string())
    res["구간별"] = tab.round(2).to_dict(orient="index")
    return res


def day_block(df: pd.DataFrame, case: pd.DataFrame) -> dict:
    print("\n" + "=" * 74)
    print("[2] 2026-08-12 집중일 분석")
    print("=" * 74)
    D = "20260812"
    d = case[case["사유발생일"] == D]
    o = case[case["사유발생일"] != D]
    tot = case["거래대금"].sum()
    print(f"집중일 {len(d)}건 / 그 외 {len(o)}건 (고유 종목×사유발생일 기준)")
    print(f"  거래대금  집중일 {d['거래대금'].sum():>14,.0f}원 "
          f"({d['거래대금'].sum()/tot*100:.1f}%) / 그 외 {o['거래대금'].sum():>14,.0f}원")
    print(f"  체결건수  집중일 {d['체결건수'].sum():>6,}건 / 그 외 {o['체결건수'].sum():>6,}건")
    print(f"  공시시각  {d['공시분'].min()//60:02d}:{d['공시분'].min()%60:02d} ~ "
          f"{d['공시분'].max()//60:02d}:{d['공시분'].max()%60:02d} "
          f"(중앙값 {int(d['공시분'].median())//60:02d}:{int(d['공시분'].median())%60:02d})")
    print(f"  정보공백  중앙값 {d['정보공백'].median():.0f}분 (그 외 {o['정보공백'].median():.0f}분)")

    dd = d.dropna(subset=["수익률"])
    oo = o.dropna(subset=["수익률"])
    print(f"  수익률    집중일 중앙값 {dd['수익률'].median():+.2f}% "
          f"(손실 {int((dd['수익률']<0).sum())}/{len(dd)}) / "
          f"그 외 중앙값 {oo['수익률'].median():+.2f}% "
          f"(손실 {int((oo['수익률']<0).sum())}/{len(oo)})")
    d_ex = dd[dd["단축코드"] != "002680"]
    print(f"  (한탑 제외) 집중일 중앙값 {d_ex['수익률'].median():+.2f}%, "
          f"평가손익 {d_ex['평가손익'].sum():+,.0f}원")

    print("\n  집중일 시장별:")
    mk = d.groupby("시장").agg(건수=("거래대금", "size"), 거래대금=("거래대금", "sum"),
                              수익률중앙값=("수익률", "median"), 평가손익=("평가손익", "sum"))
    print(mk.round(2).to_string())

    print("\n  공시 시각대별 분포(집중일):")
    d2 = d.assign(시각대=(d["공시분"] // 30 * 30))
    for k, grp in d2.groupby("시각대"):
        print(f"    {k//60:02d}:{k%60:02d}~{(k+30)//60:02d}:{(k+30)%60:02d}  "
              f"{len(grp):2d}건  {grp['거래대금'].sum():>12,.0f}원")
    return {
        "집중일_건수": int(len(d)), "집중일_거래대금": int(d["거래대금"].sum()),
        "집중일_비중": round(float(d["거래대금"].sum() / tot * 100), 1),
        "집중일_수익률중앙값": float(dd["수익률"].median()),
        "집중일_수익률중앙값_한탑제외": float(d_ex["수익률"].median()),
        "집중일_평가손익_한탑제외": int(d_ex["평가손익"].sum()),
        "시장별": mk.round(2).to_dict(orient="index"),
    }


def scenario_block(df: pd.DataFrame, case: pd.DataFrame) -> dict:
    print("\n" + "=" * 74)
    print("[3] 제도 대안별 효과 — 공표 시각을 앞당길 때 사라지는 정보 공백 체결")
    print("=" * 74)
    tot_amt = df["체결대금"].sum()
    tot_cnt = len(df)
    print(f"기준: 정보 공백 체결 전량 {tot_cnt:,}건 · {tot_amt:,.0f}원\n")

    # (가) 공표 시각을 X로 앞당김 → X 이후 체결은 '공표된 상태'가 되어 공백에서 빠진다
    print("  (가) 종가 확정 직후 공표 — 공표 시각별 공백 해소율")
    rows = []
    for hh, mm, note in [(15, 40, "시간외 개시 직전"), (16, 0, "G3 종료"),
                         (16, 30, ""), (17, 0, ""), (17, 30, ""),
                         (18, 0, "시간외 종료(현행 최빈)")]:
        x = hh * 60 + mm
        cov = df[df["체결분"] >= x]
        amt, cnt = cov["체결대금"].sum(), len(cov)
        rows.append({"공표시각": f"{hh:02d}:{mm:02d}", "해소건수": cnt,
                     "해소대금": int(amt),
                     "해소율(%)": round(amt / tot_amt * 100, 1), "비고": note})
        print(f"    {hh:02d}:{mm:02d} 공표 → 해소 {cnt:5,}건 {amt:>13,.0f}원 "
              f"({amt/tot_amt*100:5.1f}%)  {note}")

    # (나) 판정일 시간외거래 정지 — 체결 자체가 소멸
    print(f"\n  (나) 판정일 시간외거래 정지 → 체결 소멸 {tot_cnt:,}건 "
          f"{tot_amt:,.0f}원 (100.0%)")
    print("       단, 정보 공백 해소가 아니라 거래 기회 자체를 없애는 방식이다.")
    g3 = df[df["보드ID"] == "G3"]
    g4 = df[df["보드ID"] == "G4"]
    print(f"       G3(15:40~16:00) {len(g3):,}건 {g3['체결대금'].sum():,.0f}원 / "
          f"G4(16:00~18:00) {len(g4):,}건 {g4['체결대금'].sum():,.0f}원")

    # (다) 지정 예정 리스트 상시 공개 — 사전예고 공시가 이미 나갔던 종목의 비중
    print("\n  (다) 지정 예정(임박) 리스트 상시 공개")
    pw_path = PROPOSAL_DATA / "prewarning_disclosures.csv"
    covered = set()
    if pw_path.exists():
        pw = pd.read_csv(pw_path, dtype=str)
        pw = pw[pw["공시제목"].str.contains("시가총액|주가", na=False)]
        pw["일자"] = pd.to_datetime(pw["시간"], errors="coerce").dt.strftime("%Y%m%d")
        for _, r in case.iterrows():
            hit = pw[(pw["회사명"] == r["종목명"]) & (pw["일자"] < r["사유발생일"])]
            if len(hit):
                covered.add(r["키"] if "키" in case.columns else
                            f"{r['사유발생일']}_{r['단축코드']}")
        cov_case = case[case.apply(
            lambda r: f"{r['사유발생일']}_{r['단축코드']}" in covered, axis=1)]
        amt = cov_case["거래대금"].sum()
        print(f"    사유발생일 이전에 '관리종목지정우려' 공시가 있었던 건: "
              f"{len(cov_case)}/{len(case)}건")
        print(f"    그 건들의 시간외 거래대금 {amt:,.0f}원 "
              f"({amt/case['거래대금'].sum()*100:.1f}%)")
        print("    → 우려 명단을 장중 상시 공개했다면 이만큼은 사전 인지가 가능했다.")

        # 예고를 못 받은 건이 어느 시장에 몰려 있는가 — 유가증권은 사전예고 자체가 없다
        case = case.assign(사전예고=case.apply(
            lambda r: f"{r['사유발생일']}_{r['단축코드']}" in covered, axis=1))
        print("\n    사전예고 유무 × 시장:")
        print(pd.crosstab(case["시장"], case["사전예고"], margins=True)
              .to_string().replace("\n", "\n      "))
        print(f"    수집된 시총·주가 사전예고 {len(pw)}건의 시장: "
              f"{pw['시장'].value_counts().to_dict()}")
        print("    → 유가증권시장은 이 사유의 사전예고를 하지 않는다. (다)안의 사각지대다.")
    else:
        print(f"    사전예고 데이터 없음: {pw_path}")
        amt = 0
    return {
        "전체": {"건수": int(tot_cnt), "대금": int(tot_amt)},
        "공표시각별": rows,
        "보드별": {"G3": {"건수": len(g3), "대금": int(g3["체결대금"].sum())},
                 "G4": {"건수": len(g4), "대금": int(g4["체결대금"].sum())}},
        "사전예고_커버": {"건수": len(covered), "대금": int(amt)},
    }


def main() -> int:
    df = load_ticks()
    case = per_case(df)
    case["키"] = case["사유발생일"] + "_" + case["단축코드"]

    out = {
        "상관": corr_block(case),
        "집중일": day_block(df, case),
        "대안": scenario_block(df, case),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "followup_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n저장: {RESULTS / 'followup_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
