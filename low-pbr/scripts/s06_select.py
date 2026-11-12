"""s06 PBR 산정 · 업종 컷 · 저PBR 선정 · 공표 면제 → 보도자료·KIND 대조.

입력 (모두 data/interim, data/final)
  rounds.csv · universe_snap.csv · mktcap_round.csv (s03) · equity_hist.csv · comp_basic.csv (s05)
  pr_filing (MySQL, s04) · kind_lowpbr_20261102.csv · kind_valueup_discl.csv (s10) · press_*.csv (s00)

규칙 번호는 docs/01-재현사양.md. 가정은 --equity / --cut / --excl 로 바꿔 가며 민감도를 본다.
  --equity con_parent(기본, A2 확정: 지배지분, 연결 없으면 별도) | con_total | sep_total
  --cut    floor(기본, A4: 순위 ≤ floor(N×p), 최소 1) | ceil | round
  --excl   nomcap(기본: 시총·주가 미달 단독 사유가 아닌 관리종목 제외) | none | admin
  --src    check(기본: CHECK 시세·재무) | dg (DataGuide 6 — s15 출력. 자본·시가총액을 DataGuide 값으로 쓰고,
           2026.11 앞 12개 회차는 그 기준일 DataGuide 관리종목·거래정지로 산정 제외(G2안). 2026.11 은 KIND 관리종목 목록)

출력
  data/final/replica_firm_round.csv   회차 × 기업: 시가총액·자본·근거보고서·PBR·업종·순위·컷·해당여부
  data/final/replica_selection.csv    2026.11 기업별 판정 (선정·면제불가·면제·공표) + KIND 대조 열
  data/final/replica_sector.csv       시장 × 업종 재현값 vs 보도자료 붙임1
  --src dg 이면 파일 이름 끝에 _dg 가 붙는다 (replica_firm_round_dg.csv 등)
"""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _db import get_conn  # noqa: E402
from _rules import DART_MAIN, ROOT, choose_filing, load_rounds, periodic_filings  # noqa: E402

INTER, FINAL = ROOT / "data/interim", ROOT / "data/final"
P = {"KOSPI": 0.25, "KOSDAQ": 0.10}
SMALL = {"KOSPI": 4, "KOSDAQ": 10}          # R8: 업종 내 사수가 이보다 적으면 PBR 최저 1사
WICS2GICS = {"G10": "에너지", "G15": "소재", "G20": "산업재", "G25": "자유소비재", "G30": "필수소비재",
             "G35": "헬스케어", "G40": "금융", "G45": "정보기술", "G50": "커뮤니케이션", "G55": "유틸리티",
             "G60": "부동산"}
KIND_GICS = {"커뮤니케이션서비스": "커뮤니케이션"}


def trunc2(x: float) -> float:
    return math.floor(x * 100 + 1e-9) / 100


def load_gics() -> dict[str, str]:
    """종목코드 → GICS 섹터. WICS 대분류 근사 위에 KIND 공표 151사 GICS 를 덮어쓴다 (A3)."""
    from _gics import to_gics
    basic = pd.read_csv(INTER / "comp_basic.csv", dtype=str, keep_default_na=False)
    g = {r.code: to_gics(r.wics, r.name) for r in basic.itertuples()}
    kind = pd.read_csv(FINAL / "kind_lowpbr_20261102.csv", dtype=str)
    snap = pd.read_csv(INTER / "universe_snap.csv", dtype=str)
    c5 = {c[:5]: c for c in snap.code.unique() if c.endswith("0")}
    n_over = 0
    for r in kind.itertuples():
        code = c5.get(r.corp5)
        if code:
            new = KIND_GICS.get(r.gics, r.gics)
            n_over += g.get(code) != new
            g[code] = new
    print(f"GICS: WICS 근사 {len(basic)}사, KIND 표기로 바뀐 회사 {n_over}")
    return g


def equity_table_dg(kind: str) -> dict[tuple[str, int], float]:
    """DataGuide 자본 (s15 dg_equity.csv). 연결 값이 없으면 개별 자본총계 (A2)."""
    eq = pd.read_csv(INTER / "dg_equity.csv", dtype={"code": str})
    res = {}
    for r in eq.itertuples():
        v = getattr(r, kind)
        if kind != "sep_total" and v != v:
            v = r.sep_total
        if v == v:
            res[(r.code, int(r.yymm))] = float(v)
    return res


def dg_excluded(last_round: str) -> dict[str, set[str]]:
    """회차 → 산정 제외 종목 (G2안, docs/04 §3). 마지막 회차는 KIND 관리종목 목록(admin_excluded)을 쓰므로 비운다.
    관리종목: 사유에 시가총액·주가·동전주·거래실적·거래량(종류주식 요건 제외)이 있거나 빈칸(2026 동전주 지정)이면 남긴다.
    거래정지: 사유에 주식 병합·분할 또는 시가총액·주가가 있으면 남긴다."""
    st = pd.read_csv(INTER / "dg_status.csv", dtype=str)
    r, hr = st["관리종목지정사유"].fillna(""), st["거래정지사유"].fillna("")
    keep_adm = (r.str.contains("시가총액|주가|동전주|거래실적|거래량") & ~r.str.contains("종류주식")) | (r == "")
    adm = (st["관리종목여부"] == "관리") & ~keep_adm
    hal = (st["거래정지여부"] == "정지") & ~hr.str.contains("병합|분할|시가총액|주가")
    out = defaultdict(set)
    for rd, code in zip(st.base_date[adm | hal], st.code[adm | hal]):
        out[rd].add(code)
    out[last_round] = set()
    return out


def equity_table(kind: str) -> dict[tuple[str, int], float]:
    """(종목코드, 결산년월) → 자본(천원).
    con_parent(기본, 확정 2026-11-10): 연결 지배기업 소유주지분, 그 기간 연결이 없으면 별도 자본총계 —
    KIND 공표 PBR 과 119/119 일치(docs/03). con_total·sep_total 은 민감도 비교용."""
    scope, item = {"con_total": ("con", "total"), "con_parent": ("con", "parent"), "sep_total": ("sep", "total")}[kind]
    eq = pd.read_csv(INTER / "equity_hist.csv", dtype={"code": str})
    val = {(r.code, int(r.yymm), r.scope, r.item): r.value_k for r in eq.itertuples()}
    has_con = {(c, y) for (c, y, sc, it) in val if sc == "con"}
    res = {}
    for (c, y, sc, it), v in val.items():
        if sc == scope and it == item:
            res[(c, y)] = v
        elif scope == "con" and sc == "sep" and it == "total" and (c, y) not in has_con:
            res[(c, y)] = v
    return res


def admin_excluded(rule: str, snap26: pd.DataFrame) -> set[str]:
    if rule == "none":
        return set()
    adm = pd.read_csv(INTER / "admin_flags.csv", dtype=str)
    adm = adm[adm["지정일"] <= "2026-10-22"]
    if rule == "nomcap":
        only = adm["지정사유"].str.fullmatch(r"(시가총액 미달|주가 미달\(동전주\))(,(시가총액 미달|주가 미달\(동전주\)))*")
        adm = adm[~only]
    names = set(adm["종목명"])
    return set(snap26[snap26.corp_name.isin(names)].code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", default="con_parent")
    ap.add_argument("--cut", default="floor")
    ap.add_argument("--excl", default="nomcap")
    ap.add_argument("--src", default="check", choices=["check", "dg"])
    args = ap.parse_args()
    dg = args.src == "dg"
    sfx = "_dg" if dg else ""

    rounds = load_rounds()
    snap = pd.read_csv(INTER / "universe_snap.csv", dtype=str)
    mc = pd.read_csv(INTER / ("dg_mcap_round.csv" if dg else "mktcap_round.csv"), dtype={"code": str, "round": str})
    mc = {(r.round, r.code): r.mktcap_avg for r in mc.itertuples() if pd.notna(r.mktcap_avg)}
    eqt = equity_table_dg(args.equity) if dg else equity_table(args.equity)
    dgx = dg_excluded(rounds[-1]["base_date"]) if dg else defaultdict(set)
    gics = load_gics()
    krx_gics, krx_rounds = {}, set()
    if (INTER / "gics_krx.csv").exists():
        for gr in pd.read_csv(INTER / "gics_krx.csv", dtype=str).itertuples():
            krx_gics[(gr.round, gr.code)] = gr.sector
            krx_rounds.add(gr.round)
        print(f"GICS: KRX 지수 사이트 분류 {len(krx_rounds)}개 회차 사용")
    conn = get_conn()
    fil = periodic_filings(conn)
    excl26 = admin_excluded(args.excl, snap[snap["round"] == "2026.11"])
    # 거래정지 제외 (2026-11-11 실측): 20거래일 구간 내내 종가가 한 번도 안 변한 종목 = 거래정지로 본다.
    # 2026.11 회차에 유가 7·코스닥 2사 → 모집단이 보도자료 779·1,652 와 맞는다 (docs/03).
    # --src dg 는 종가 대신 DataGuide 일간 시가총액이 20일 내내 같은지로 본다.
    halted = defaultdict(set)
    dly_path = INTER / ("dg_mcap_window.csv" if dg else "mktcap_daily.csv")
    if dly_path.exists():
        cal = [r["date"] for r in csv.DictReader(open(INTER / "calendar.csv", encoding="utf-8"))]
        dly = pd.read_csv(dly_path, dtype={"code": str, "date": str})
        px = "mktcap_mn" if dg else "close"
        for r in rounds:
            i = cal.index(r["base_date"])
            w = dly[dly.date.isin(cal[i - 19: i + 1])].groupby("code")[px].agg(["size", "nunique"])
            halted[r["round"]] = set(w[(w["size"] >= 15) & (w["nunique"] == 1)].index)

    rows = []
    for r in rounds:
        s = snap[snap["round"] == r["round"]]
        for x in s.itertuples():
            if r["round"] == "2026.11" and x.code in excl26:
                continue
            if x.code in halted[r["round"]] or x.code in dgx[r["base_date"]]:
                continue
            f = choose_filing(fil.get(x.code, []), r["base_date"])
            yymm = int(f[3].strftime("%Y%m")) if f else None
            eq_k = eqt.get((x.code, yymm)) if yymm else None
            m = mc.get((r["round"], x.code))
            pbr = trunc2(m / (eq_k * 1000)) if (m and eq_k and eq_k > 0) else None
            # 업종 (A3, 2026-11-11 갱신)
            #  ① 기준일 달 2개월 전 1일 이후 상장한 코스닥사 = 업종미분류 (2026.11: 8.1 이후 16사 = 보도자료 16)
            #  ② 그 회차 기준일의 KRX GICS 분류 (index.krx.co.kr, s11)
            #  ③ KRX 지수 사이트 목록에 없는 예전 상장사(14사, 2026.11) = WICS 세부 산업 근사로 보완
            y, mo = int(r["base_date"][:4]), int(r["base_date"][4:6]) - 2
            if mo <= 0:
                y, mo = y - 1, mo + 12
            # 스냅샷 상장일은 지금 KIND 값이라, 뒤에 유가로 옮긴 회사(파라다이스·포스코DX 등)는 이전상장일(기준일보다 뒤)이 들어 있다.
            # 기준일보다 뒤 날짜는 그 회차의 신규 상장이 아니므로 제외한다 (엑셀 재현본이 DataGuide 상장일로 찾아낸 차이, 2026-11-12).
            ld = str(x.list_date)
            fresh = x.market == "KOSDAQ" and f"{y}-{mo:02d}-01" <= ld <= f"{r['base_date'][:4]}-{r['base_date'][4:6]}-{r['base_date'][6:]}"
            if fresh:
                g_here = "업종미분류"
            elif (r["round"], x.code) in krx_gics:
                g_here = krx_gics[(r["round"], x.code)]
            else:
                g_here = gics.get(x.code, "") or "업종미분류"
            rows.append({"round": r["round"], "seq": int(r["seq"]), "market": x.market, "code": x.code,
                         "name": x.corp_name, "gics": g_here,
                         "mktcap_avg": m, "equity_k": eq_k, "rcept_no": f[0] if f else "",
                         "report_nm": f[4] if f else "", "period": yymm, "pbr": pbr})
    df = pd.DataFrame(rows)

    # 업종 컷 (R6~R9)
    df["rank"], df["n_grp"], df["cut"], df["low"] = None, None, None, False
    for (rd, mk, g), grp in df[df.pbr.notna()].groupby(["round", "market", "gics"]):
        if g == "업종미분류":
            continue
        grp = grp.sort_values("pbr")
        n = len(grp)
        if n < SMALL[mk]:
            k = 1
        else:
            k = {"floor": math.floor, "ceil": math.ceil, "round": round}[args.cut](n * P[mk])
            k = max(1, k)
        cut = grp.pbr.iloc[k - 1]
        df.loc[grp.index, "rank"] = range(1, n + 1)
        df.loc[grp.index, "n_grp"] = n
        df.loc[grp.index, "cut"] = cut
        df.loc[grp.index, "low"] = grp.pbr <= cut
    # 업종미분류: 소속시장 전체를 모집단 (R9)
    for (rd, mk), grp in df[df.pbr.notna()].groupby(["round", "market"]):
        allm = grp.sort_values("pbr")
        k = max(1, math.floor(len(allm) * P[mk]))
        cut = allm.pbr.iloc[k - 1]
        un = grp[grp.gics == "업종미분류"]
        df.loc[un.index, "cut"] = cut
        df.loc[un.index, "low"] = un.pbr <= cut
    df.to_csv(FINAL / f"replica_firm_round{sfx}.csv", index=False, encoding="utf-8-sig")

    # 선정 (R10·R11) · 면제 불가 (R14)
    last = df[df["round"] == "2026.11"]
    low = defaultdict(dict)
    for x in df.itertuples():
        low[x.code][x.seq] = bool(x.low)
    sel = []
    for x in last.itertuples():
        L = low[x.code]
        six = [L.get(s, False) for s in range(8, 14)]
        c6 = all(six) or (sum(six) == 5 and L.get(7, False))
        twelve = [L.get(s, False) for s in range(2, 14)]
        c12 = all(twelve) or (sum(twelve) == 11 and L.get(1, False))
        un = x.gics == "업종미분류"
        selected = (all(six) if un else c6) and L.get(13, False)        # R11 최초 공표 특례
        sel.append({"code": x.code, "corp5": x.code[:5], "name": x.name, "market": x.market, "gics": x.gics,
                    "pbr": x.pbr, "cut": x.cut, "rank": x.rank, "n_grp": x.n_grp,
                    "flags_1_13": "".join("1" if L.get(s) else ("0" if s in L else "·") for s in range(1, 14)),
                    "n_low_last6": sum(six), "n_low_last12": sum(twelve), "selected": selected,
                    "chronic": c12, "rcept_no": x.rcept_no, "report_nm": x.report_nm,
                    "dart_url": DART_MAIN.format(x.rcept_no) if x.rcept_no else ""})
    sd = pd.DataFrame(sel)

    # 밸류업(PBR 개선계획) 공시 · KIND 대조 (사양 §4)
    v = pd.read_csv(FINAL / "kind_valueup_discl.csv", dtype=str)
    vb = v[v.disc_dt <= "2026-10-22 23:59"]
    plan = vb[vb.title.str.contains("PBR")].sort_values("disc_dt").groupby("corp5").last()
    anyv = vb.sort_values("disc_dt").groupby("corp5").last()
    sd["pbr_plan"] = sd.corp5.isin(plan.index)
    sd["pbr_plan_dt"] = sd.corp5.map(plan.disc_dt)
    sd["pbr_plan_url"] = sd.corp5.map(plan.kind_url)
    sd["valueup_any"] = sd.corp5.isin(anyv.index)
    sd["valueup_last_title"] = sd.corp5.map(anyv.title)
    sd["valueup_last_dt"] = sd.corp5.map(anyv.disc_dt)
    sd["valueup_last_url"] = sd.corp5.map(anyv.kind_url)
    sd["exempt"] = sd.selected & sd.pbr_plan & ~sd.chronic
    sd["published"] = sd.selected & ~sd.exempt
    kind = pd.read_csv(FINAL / "kind_lowpbr_20261102.csv", dtype=str)
    sd["in_kind"] = sd.corp5.isin(kind.corp5)
    sd["kind_pbr"] = sd.corp5.map(kind.set_index("corp5").pbr)
    sd["match"] = sd.apply(lambda r: "일치" if r.published and r.in_kind else
                           ("재현에만" if r.published else ("KIND에만" if r.in_kind else "")), axis=1)
    sd.to_csv(FINAL / f"replica_selection{sfx}.csv", index=False, encoding="utf-8-sig")

    # 요약
    press = pd.read_csv(FINAL / "press_sector.csv")
    sec = []
    for (mk, g), grp in last.groupby(["market", "gics"]):
        s2 = sd[(sd.market == mk) & (sd.gics == g)]
        p = press[(press.market == mk) & (press.gics == g)]
        sec.append({"market": mk, "gics": g, "cut": grp.cut.dropna().iloc[0] if grp.cut.notna().any() else None,
                    "press_cut": p.cut_pbr.iloc[0] if len(p) else None, "n_univ": len(grp),
                    "press_univ": p.n_univ.iloc[0] if len(p) else None, "n_sel": int(s2.selected.sum()),
                    "press_sel": p.n_sel.iloc[0] if len(p) else None, "n_exempt": int(s2.exempt.sum()),
                    "press_exempt": p.n_exempt.iloc[0] if len(p) else None, "n_pub": int(s2.published.sum()),
                    "press_pub": p.n_pub.iloc[0] if len(p) else None})
    pd.DataFrame(sec).to_csv(FINAL / f"replica_sector{sfx}.csv", index=False, encoding="utf-8-sig")

    tot = lambda col: sd.groupby("market")[col].sum().to_dict()
    print(f"[{args.src}·{args.equity}·{args.cut}·{args.excl}] 모집단 {last.groupby('market').size().to_dict()} (목표 779/1652) · "
          f"PBR 없음 {int(last.pbr.isna().sum())}")
    print(f"  선정 {tot('selected')} (115/70) · 면제 {tot('exempt')} (19/15) · 공표 {tot('published')} (96/55)")
    print(f"  KIND 대조: {sd.match.value_counts().to_dict()}")
    m = sd[sd.in_kind & sd.kind_pbr.notna() & sd.pbr.notna()]
    print(f"  KIND PBR 소수2자리 일치 {(m.pbr.round(2) == m.kind_pbr.astype(float)).sum()}/{len(m)}")


if __name__ == "__main__":
    main()
