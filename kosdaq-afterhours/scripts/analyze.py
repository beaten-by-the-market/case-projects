"""H1. 코스닥 유동성 분포·집중도·NXT 침투율.

유니버스: 코스닥 보통주(F34501='ST'). ETF/ETN/리츠/외국주식/DR 제외.
상폐 종목은 master 에 없어 증권그룹을 모른다 → 별도 표기하되 분석엔 포함한다
(상폐 종목이야말로 저유동성·부실 종목의 전형이므로 빼면 생존편향).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import status

sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
from _common import _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()
ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 200)

억 = 1e8
조 = 1e12


def load():
    """일자별 '애프터 편입 가능' 마스크를 씌워 로드한다.

    투자경고·투자위험·관리종목·투자주의환기 지정일은 애프터마켓에서 거래하지 않으므로,
    그날의 거래대금·공시는 애프터 사업의 수익·비용 어느 쪽에도 들어가면 안 된다.
    **종목 단위가 아니라 일자 단위**로 걸러야 한다(경고·위험은 1~2주짜리 일시 지정이다).
    """
    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    d["amt"] = (d.amt_sell.fillna(0) + d.amt_buy.fillna(0)) / 2
    d["traded"] = (d[["vol_sell", "vol_buy"]].fillna(0).max(axis=1) > 0)

    days = sorted(d[d.fam == "m003"].date.unique())
    bad = status.ineligible_days(days)
    key = pd.MultiIndex.from_arrays([d.code, d.date])
    d["eligible"] = ~key.isin(bad)
    n_all = (d.fam == "m003").sum()
    print(f"[편입가능일] 코스닥 종목-일 {n_all:,} 중 지정상태 "
          f"{(~d.eligible & (d.fam == 'm003')).sum():,} 제외 "
          f"({(~d.eligible & (d.fam == 'm003')).sum()/n_all*100:.1f}%)")

    m = pd.read_csv(DATA / "master.csv", dtype={"code": str})
    grp = m.set_index("code").group.to_dict()
    cap = m.set_index("code").mktcap.to_dict()
    nm = m.set_index("code").name.to_dict()
    spac = m.set_index("code").spac.to_dict()          # F33792 기업인수목적회사여부

    n = pd.read_csv(DATA / "daily_nxt.csv", dtype={"code": str, "date": str})
    n["amt"] = (n.amt_sell.fillna(0) + n.amt_buy.fillna(0)) / 2
    n["traded"] = (n[["vol_sell", "vol_buy"]].fillna(0).max(axis=1) > 0)
    nkey = pd.MultiIndex.from_arrays([n.code, n.date])
    n = n[~nkey.isin(bad)]                             # NXT 거래대금도 같은 기준으로

    pd.DataFrame(list(bad), columns=["code", "date"]).to_csv(
        DATA / "ineligible_days.csv", index=False)
    return d[d.eligible], n, grp, cap, nm, spac


MIN_DAYS = 120   # 관측 최소 거래일 (약 6개월)


def _spac_by_gongsi() -> set[str]:
    """공시 제목의 **회사명**으로 스팩을 판정한다 (상장폐지 스팩용).

    `F33792`는 현재 상장분에만 있어 **합병으로 소멸한 스팩을 못 잡는다.**
    공시 제목은 회사명으로 시작하므로("유안타제14호기업인수목적 주식회사 …"), 앞머리 28자에
    `기업인수목적`·`스팩`이 든 공시가 **과반**이면 스팩으로 본다.

    ⚠ 제목 전체를 보면 안 된다. **스팩 합병으로 상장한 정상 기업**(티앤알바이오팹 등)의 합병 공시에도
    '기업인수목적'이 등장한다. 회사명 위치(앞머리)로 한정해야 한다.
    검증: F33792 스팩 73종목 중 68개 포착, 일반 종목 오판 1건(현재 상장분엔 이 규칙을 안 쓰므로 무해).
    """
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    head = g.title.fillna("").str.slice(0, 28)
    frac = head.str.contains("기업인수목적|스팩", na=False).groupby(g.code).mean()
    return set(frac[frac > 0.5].index)


def per_stock(daily, fam):
    """종목별: 상장일수 · 거래일수 · 총거래대금 · 일평균 거래대금.

    ⚠ 관측일이 극히 짧은 종목을 그대로 두면 안 된다.
    기간 말미에 신규상장한 종목은 **상장 첫날 폭발적 거래**만 잡히고(예: 하루 7,950억),
    그걸 '등장한 날 수'로 나누면 일평균이 수천억이 되어 D1(상위 10%)에 들어앉는다.
    게다가 이런 종목은 공시를 낼 시간도 없어 공시 건수가 0에 가까워, D1의 공시 평균을 끌어내린다.
    → 관측 거래일 MIN_DAYS 미만은 제외한다.
    """
    x = daily[daily.fam == fam]
    g = x.groupby("code").agg(listed=("date", "nunique"),
                              traded_days=("traded", "sum"),
                              amt_sum=("amt", "sum"))
    g["amt_avg"] = g.amt_sum / g.listed          # 상장돼 있던 날 기준 일평균
    g["no_trade_pct"] = (1 - g.traded_days / g.listed) * 100
    g["years"] = g.listed / 242                  # 종목별 연율화 계수 (공시 건수용)
    return g


def gini(x):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return np.nan
    return (2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())


def main():
    d, n, grp, cap, nm, spac = load()

    kq = per_stock(d, "m003")
    kp = per_stock(d, "m001")
    nx = per_stock(n, "m223")

    for g, name in [(kq, "코스닥"), (kp, "코스피")]:
        g["group"] = [grp.get(c, "?") for c in g.index]
        g["mktcap"] = [cap.get(c, np.nan) for c in g.index]
        g["name"] = [nm.get(c, "") for c in g.index]
        g["spac"] = [spac.get(c, "N") for c in g.index]

    print("\n=== 애프터마켓 편입 후보 유니버스 ===")
    print(f"  코스닥 (편입가능일 기준): {len(kq):,}종목")

    # 보통주(ST)만. ETF/ETN/리츠/외국주식/DR 제외. 상폐 종목('?')은 남긴다.
    kq = kq[kq.group.isin(["ST", "?"])]
    kp = kp[kp.group.isin(["ST", "?"])]

    # ── 스팩 제외 ──
    # ⚠ F33792(기업인수목적회사여부)는 `code_info`(**현재 상장분**)에서 온다.
    #   → **합병으로 소멸한 스팩은 플래그가 없어 그대로 남는다.** 실제로 상장폐지 78종목 중 64개가
    #     스팩이었고, 전부 D10에 깔려 "저유동성 종목"으로 집계되고 있었다.
    #   → 상폐 종목은 **공시 제목의 회사명**으로 판정한다: 제목 앞머리(28자)에 `기업인수목적`·`스팩`이
    #     들어간 공시가 **과반**이면 스팩. (현재 상장분은 F33792가 정답이므로 이 규칙을 적용하지 않는다
    #     . 스팩 합병으로 상장한 정상 기업이 오판되는 것을 막는다.)
    spac_named = _spac_by_gongsi()
    is_spac = [(kq.spac[c] == "Y") or (kq.spac[c] != "Y" and c not in nm and c in spac_named)
               for c in kq.index]
    n_named = sum(1 for c, s in zip(kq.index, is_spac) if s and kq.spac[c] != "Y")
    kq = kq[[not s for s in is_spac]]
    kp = kp[kp.spac != "Y"]
    print(f"  − 스팩 제외 → {len(kq):,}종목  (F33792 플래그 + **상폐 스팩 {n_named}종목**)")

    # 우선주 제외. 분석 대상은 **보통주**다.
    # ⚠ F34501(증권그룹ID)은 우선주도 'ST'로 준다. CHECK API엔 보통주/우선주 플래그가 없다.
    #   → KRX 코드 규약(보통주 = 끝자리 0 · 우선주 = 5/7/9 또는 K/L/M)으로 판정한다.
    #   KRX `listed_stocks`의 KIND_STKCERT_TP_NM 과 **100% 일치** 확인
    #   (코스닥 우선주는 3종목뿐: 대호특수강우 021045 · 소프트센우 032685 · 해성산업1우 03481K).
    pref = [c for c in kq.index if c[-1] not in "0"]
    kq = kq[~kq.index.isin(pref)]
    kp = kp[[c[-1] in "0" for c in kp.index]]
    print(f"  − 우선주 제외 → {len(kq):,}종목  ({', '.join(str(nm.get(c, c)) for c in pref)})")

    # 편입가능일이 짧은 종목 제외. 두 부류가 걸린다:
    #   ① 기간 말미 신규상장. 상장 첫날 폭발 거래만 잡혀 일평균이 왜곡된다(하루 7,950억 사례).
    #   ② 대부분의 기간을 관리종목·환기종목으로 보낸 종목. 애프터 대상이 아니다.
    # 매매거래정지일은 status.py 에서 이미 제외됐다(공시+거래량 복원 + KRX 현재정지 보정).
    # 정지가 길었던 종목은 편입가능일이 짧아져 아래 필터에 자연히 걸린다.
    kq = kq[kq.listed >= MIN_DAYS]
    kp = kp[kp.listed >= MIN_DAYS]
    print(f"  − 편입가능일 {MIN_DAYS}일 미만 제외 → {len(kq):,}종목")

    # 마지막 가드: 편입가능일이 충분한데도 **체결이 단 한 건도 없는** 종목.
    # 2024-01-01 이전부터 정지돼 있어 정지 시작점을 잡을 수 없는 종목이다(좌측 절단 잔여분).
    # KRX '현재 정지' 목록에도 없어 보정되지 않는다. 사실상 정지 상태이므로 제외한다.
    dead = kq[kq.traded_days == 0]
    kq = kq[kq.traded_days > 0]
    print(f"  − 전 기간 체결 0건(좌측절단 정지) 제외 → **{len(kq):,}종목** (최종)")
    if len(dead):
        print(f"    {', '.join(str(n) for n in dead.name.head(4))}")
    print(f"\n[검증] 무거래일 50% 초과 종목: {(kq.no_trade_pct > 50).sum()}개\n")

    kq = kq.sort_values("amt_avg", ascending=False)

    N = len(kq)
    print(f"=== H1. 코스닥 유동성 분포 (보통주+상폐 {N:,}종목 · 606거래일) ===\n")

    # ── 1. decile 표 ──
    kq["decile"] = pd.qcut(kq.amt_avg.rank(method="first", ascending=False),
                           10, labels=[f"D{i}" for i in range(1, 11)])
    tbl = kq.groupby("decile", observed=True).agg(
        종목수=("amt_avg", "size"),
        일평균거래대금_억=("amt_avg", lambda s: s.mean() / 억),
        중간_일평균_억=("amt_avg", lambda s: s.median() / 억),
        무거래일_pct=("no_trade_pct", "mean"),
        중간시총_억=("mktcap", lambda s: s.median() / 억),
    )
    tbl["거래대금점유_pct"] = kq.groupby("decile", observed=True).amt_sum.sum() / kq.amt_sum.sum() * 100
    print("--- 유동성 decile (D1=상위 10%) ---")
    print(tbl.round(2).to_string())

    # ── 2. 집중도 ──
    share = kq.amt_sum / kq.amt_sum.sum()
    cum = share.cumsum().values
    print(f"\n--- 집중도 ---")
    for k in [50, 100, 200, 300, 500, 800, 1000]:
        if k <= N:
            print(f"  상위 {k:5,}종목 ({k/N*100:4.1f}%) → 거래대금의 {cum[k-1]*100:5.1f}%")
    print(f"  지니계수: 코스닥 {gini(kq.amt_sum):.3f}  |  코스피 {gini(kp.amt_sum):.3f}")

    # ── 3. 절대 컷 ──
    print(f"\n--- 절대 컷 (일평균 거래대금) ---")
    for cut, lab in [(1e8, "1억"), (5e7, "5천만"), (1e7, "1천만")]:
        s = kq[kq.amt_avg < cut]
        print(f"  < {lab:>4}원: {len(s):5,}종목 ({len(s)/N*100:4.1f}%) · "
              f"이들의 거래대금 합계 점유 {s.amt_sum.sum()/kq.amt_sum.sum()*100:4.2f}%")

    # ── 4. NXT 침투율 ──
    print(f"\n--- NXT (영리 ATS의 선별) ---")
    nxt_days = n[n.fam == "m223"].date.nunique()
    traded_per_day = n[(n.fam == "m223") & n.traded].groupby("date").code.nunique()
    print(f"  NXT 코스닥 거래일 {nxt_days} · 일평균 실거래 종목수 {traded_per_day.mean():.0f} "
          f"(최소 {traded_per_day.min()} / 최대 {traded_per_day.max()})")
    ever = n[(n.fam == "m223") & n.traded].code.nunique()
    print(f"  기간 중 한 번이라도 NXT에서 거래된 코스닥 종목: {ever:,}개 "
          f"(같은 기간 KRX 상장 {N:,}종목의 {ever/N*100:.1f}%)")

    # 침투율 = NXT 총거래대금 / KRX 총거래대금 (같은 NXT 기간으로 KRX 잘라서 비교)
    nxt_start = n.date.min()
    dk = d[(d.fam == "m003") & (d.date >= nxt_start)].groupby("code").amt.sum()
    dn = n[n.fam == "m223"].groupby("code").amt.sum()
    pen = pd.DataFrame({"krx": dk, "nxt": dn}).fillna(0)
    pen = pen.join(kq[["decile"]], how="inner")
    print(f"\n  시장 전체 침투율 = NXT {dn.sum()/조:,.0f}조 ÷ KRX {dk.sum()/조:,.0f}조 "
          f"= {dn.sum()/dk.sum()*100:.1f}%")
    p = pen.groupby("decile", observed=True).apply(
        lambda g: pd.Series({
            "KRX거래대금_조": g.krx.sum() / 조,
            "NXT거래대금_조": g.nxt.sum() / 조,
            "침투율_pct": g.nxt.sum() / g.krx.sum() * 100 if g.krx.sum() else 0,
            "NXT거래종목수": (g.nxt > 0).sum(),
            "종목수": len(g),
        }), include_groups=False)
    p["NXT거래종목_pct"] = p.NXT거래종목수 / p.종목수 * 100
    print("\n--- decile별 NXT 침투율 ---")
    print(p.round(2).to_string())

    kq.to_csv(OUT / "h1_stock_liquidity.csv", encoding="utf-8-sig")
    tbl.round(3).to_csv(OUT / "h1_decile.csv", encoding="utf-8-sig")
    p.round(3).to_csv(OUT / "h1_nxt_penetration.csv", encoding="utf-8-sig")
    print(f"\n저장: {OUT}/h1_*.csv")


if __name__ == "__main__":
    main()
