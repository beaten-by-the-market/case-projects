"""s09 웹페이지 데이터 → site/data.js  (화면 틀 site/index.html·app.js·style.css 는 고정)

있는 데이터만으로 만든다. 단계가 아직 안 끝났으면 status 에 그렇게 적고 화면은 '수집 중'으로 보인다.
데이터가 늘 때마다 다시 실행하면 된다:
    python scripts/s09_site.py            # 한 번
    python scripts/s09_site.py --watch 600   # 10분마다 다시 (수집 중 띄워 두기)

담는 것
  status    단계별 진행(행 수·커버리지·갱신 시각)
  rounds    13개 회차 일정, 회차별 모집단 사수
  press     보도자료 정답지(붙임1 업종 표·본문 총계·붙임2 명단)
  kind      KIND 저PBR 공표 151사 ↔ 보도자료 명단 매칭
  plans     PBR 개선계획 제출 62사(10.22까지) + 공시 URL
  firms     기업 상세(현재: KIND 151 + 계획 62 = 198사; 재현이 끝나면 캡처 범위 ~400사)
            회차별 시가총액(CHECK)·근거 보고서(DART 접수번호·목차 경로·뷰어 링크)·자본총계(DART 원문, CHECK IFRS)·PBR·캡처
  replica   s06 결과가 있으면 업종 표·선정 결과·KIND 대조
"""
import argparse
import csv
import difflib
import json
import math
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _db import get_conn  # noqa: E402
from _rules import DART_MAIN, DART_VIEWER, ROOT, choose_filing, load_rounds, periodic_filings  # noqa: E402

INTER, FINAL, SITE = ROOT / "data/interim", ROOT / "data/final", ROOT / "site"
KIND_GICS = {"커뮤니케이션서비스": "커뮤니케이션"}


def trunc2(x):
    return math.floor(x * 100 + 1e-9) / 100


def exists(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 0


def mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if p.exists() else ""


def nname(s: str) -> str:
    return re.sub(r"[\s()（）㈜]|주식회사", "", s or "").upper()


def main_once():
    t0 = time.time()
    rounds = load_rounds()
    snap = pd.read_csv(INTER / "universe_snap.csv", dtype=str)
    snap26 = snap[snap["round"] == "2026.11"]
    c5_to_code = {c[:5]: c for c in snap.code.unique() if c.endswith("0")}
    name_of = snap.drop_duplicates("code", keep="last").set_index("code").corp_name.to_dict()
    mkt_of = snap.drop_duplicates("code", keep="last").set_index("code").market.to_dict()

    # ---------- 보도자료 정답지 ----------
    p_sector = pd.read_csv(FINAL / "press_sector.csv").fillna("").to_dict("records")
    p_tot = pd.read_csv(FINAL / "press_totals.csv").to_dict("records")
    p_list = pd.read_csv(FINAL / "press_list151.csv", dtype=str).to_dict("records")

    # ---------- KIND ----------
    kind = pd.read_csv(FINAL / "kind_lowpbr_20261102.csv", dtype=str)
    kind["gics"] = kind.gics.map(lambda g: KIND_GICS.get(g, g))
    kind["code"] = kind.corp5.map(c5_to_code)
    # 보도자료 명단 ↔ KIND (시장·업종·PBR 가 같은 후보 중 이름이 가장 비슷한 것)
    used, pmatch = set(), {}
    for p in p_list:
        cand = kind[(kind.market == p["market"]) & (kind.gics == p["gics"]) & (kind.pbr == p["pbr"])]
        cand = [c for c in cand.itertuples() if c.corp5 not in used] or \
               [c for c in kind[kind.market == p["market"]].itertuples() if c.corp5 not in used]
        best = max(cand, key=lambda c: difflib.SequenceMatcher(None, nname(p["name"]), nname(c.name)).ratio())
        used.add(best.corp5)
        pmatch[best.corp5] = p
    kind_rows = []
    for k in kind.itertuples():
        p = pmatch.get(k.corp5, {})
        kind_rows.append({"corp5": k.corp5, "code": k.code or "", "name": k.name, "market": k.market, "gics": k.gics,
                          "pbr": k.pbr, "fye": k.fye_month, "flags": k.flags, "press_name": p.get("name", ""),
                          "press_pbr": p.get("pbr", ""), "press_no": p.get("no", ""),
                          "same": bool(p) and p.get("pbr") == k.pbr and p.get("gics") == k.gics})

    # ---------- 밸류업 공시 (10.22 까지) ----------
    v = pd.read_csv(FINAL / "kind_valueup_discl.csv", dtype=str)
    vb = v[v.disc_dt <= "2026-10-22 23:59"]
    planv = vb[vb.title.str.contains("PBR")].sort_values("disc_dt")
    plans = []
    for c5, g in planv.groupby("corp5", sort=False):
        last = g.iloc[-1]
        prior = vb[(vb.corp5 == c5) & ~vb.title.str.contains("PBR")]
        plans.append({"corp5": c5, "code": c5_to_code.get(c5, ""), "name": last["name"], "market": last.market,
                      "disc_dt": last.disc_dt, "title": last.title, "url": last.kind_url,
                      "n_plan_discl": len(g), "n_other_valueup": len(prior),
                      "published": c5 in set(kind.corp5)})
    vall = defaultdict(list)
    for r in v.sort_values("disc_dt").itertuples():
        vall[r.corp5].append({"dt": r.disc_dt, "title": r.title, "url": r.kind_url})

    # ---------- 시가총액 (CHECK) ----------
    mc = {}
    if exists(INTER / "mktcap_round.csv"):
        for r in pd.read_csv(INTER / "mktcap_round.csv", dtype={"code": str, "round": str}).itertuples():
            if pd.notna(r.mktcap_avg):
                mc[(r.round, r.code)] = (int(r.mktcap_avg), int(r.mktcap_common), int(r.mktcap_pref), int(r.n_days))
    n_codes = snap.code.nunique() + len(pd.read_csv(INTER / "pref_map.csv"))
    gw_files = sum(1 for _ in (ROOT / "data/raw/gw/stock_m001_hist_info").glob("*.json")) + \
        sum(1 for _ in (ROOT / "data/raw/gw/stock_m003_hist_info").glob("*.json"))

    # ---------- CHECK IFRS (있으면) ----------
    chk = {}
    if exists(INTER / "equity_hist.csv"):
        for r in pd.read_csv(INTER / "equity_hist.csv", dtype={"code": str}).itertuples():
            chk[(r.code, int(r.yymm), r.scope, r.item)] = float(r.value_k)

    # ---------- DART ----------
    conn = get_conn()
    cur = conn.cursor()
    firm_codes = sorted({k["code"] for k in kind_rows if k["code"]} | {p["code"] for p in plans if p["code"]})
    if exists(INTER / "capture_scope.csv"):
        firm_codes = sorted(set(firm_codes) | {r["code"] for r in csv.DictReader(open(INTER / "capture_scope.csv",
                                                                                       encoding="utf-8"))})
    fil = periodic_filings(conn, firm_codes)
    ev = {}
    for f in ("equity_source_kind.csv", "equity_source_scope.csv"):
        if exists(INTER / f):
            for r in csv.DictReader(open(INTER / f, encoding="utf-8")):
                if r.get("evidence_rcept_no"):
                    ev[r["rcept_no"]] = r["evidence_rcept_no"]
    cur.execute("SELECT rcept_no, fs_scope, item, value_won, unit_text, toc_no FROM pr_fs_value")
    fsv = defaultdict(dict)
    for rcp, sc, it, val, unit, toc in cur.fetchall():
        fsv[rcp][(sc, it)] = (val, unit, toc)
    cur.execute("SELECT rcept_no, toc_no, parent_toc_no, title, dcm_no, ele_id, offset, length, dtd FROM pr_filing_toc "
                "WHERE rcept_no IN (SELECT DISTINCT rcept_no FROM pr_fs_value)")
    toc = defaultdict(dict)
    for rcp, tno, par, title, dcm, ele, off, ln, dtd in cur.fetchall():
        toc[rcp][tno] = (par, title, dcm, ele, off, ln, dtd)
    cur.execute("SELECT rcept_no, toc_no, image_path FROM pr_capture WHERE item='equity_total'")
    caps = {(r, t): p for r, t, p in cur.fetchall()}
    cur.execute("SELECT rcept_no, rcept_dt, report_nm FROM pr_filing WHERE rcept_no IN "
                "(SELECT DISTINCT rcept_no FROM pr_fs_value)")
    fmeta = {r: (d, n) for r, d, n in cur.fetchall()}

    def toc_path(rcp, tno):
        out, t = [], tno
        while t and t in toc[rcp]:
            out.append(toc[rcp][t][1])
            t = toc[rcp][t][0]
        return " > ".join(reversed(out))

    firms = {}
    kind_c5 = set(kind.corp5)
    plan_c5 = {p["corp5"] for p in plans}
    for code in firm_codes:
        rows = []
        for r in rounds:
            f = choose_filing(fil.get(code, []), r["base_date"])
            rec = {"round": r["round"], "base": r["base_date"], "win": [r["win_start"], r["win_end"]],
                   "listed": bool(((snap["round"] == r["round"]) & (snap.code == code)).any())}
            m = mc.get((r["round"], code))
            if m:
                rec.update(mktcap=m[0], mk_common=m[1], mk_pref=m[2], n_days=m[3])
            if f:
                rcp = f[0]
                e = ev.get(rcp, rcp)
                rec.update(rcept_no=rcp, report_nm=f[4], rcept_dt=f[1], period=f[3].strftime("%Y-%m"),
                           main_url=DART_MAIN.format(rcp), evidence=e, evidence_url=DART_MAIN.format(e))
                vals = fsv.get(e, {})
                for sc in ("consolidated", "separate"):
                    for it in ("equity_total", "equity_parent", "equity_nci"):
                        if (sc, it) in vals:
                            rec[f"{sc[:3]}_{it[7:]}"] = vals[(sc, it)][0]
                tv = vals.get(("consolidated", "equity_total")) or vals.get(("separate", "equity_total"))
                if tv:
                    tno = tv[2]
                    n = toc[e].get(tno)
                    rec["eq_scope"] = "연결" if ("consolidated", "equity_total") in vals else "별도"
                    rec["unit"] = tv[1]
                    if n:
                        rec["toc_path"] = toc_path(e, tno)
                        rec["viewer_url"] = DART_VIEWER.format(rcp=e, dcm=n[2], ele=n[3], off=n[4], len=n[5], dtd=n[6])
                    cp = caps.get((e, tno))
                    if cp:
                        rec["capture"] = cp
                    # PBR 분모 = 연결 지배기업 소유주지분, 연결이 없으면 별도 자본총계 (KIND 119/119 일치, docs/03)
                    par = vals.get(("consolidated", "equity_parent"))
                    has_con = ("consolidated", "equity_total") in vals
                    base = par if has_con else vals.get(("separate", "equity_total"))
                    rec["eq_basis"] = "연결 지배기업 소유주지분" if has_con else "별도 자본총계"
                    if base:
                        rec["eq_base"] = base[0]
                    if m and base and base[0] and base[0] > 0:
                        rec["pbr_dart"] = trunc2(m[0] / base[0])
                    elif has_con and not par:
                        rec["eq_note"] = "지배지분 행 미추출(재추출 대기)"
                    if m and tv[0] and tv[0] > 0:
                        rec["pbr_total"] = trunc2(m[0] / tv[0])
                yymm = int(f[3].strftime("%Y%m"))
                for sc in ("con", "sep"):
                    for it in ("total", "parent"):
                        if (code, yymm, sc, it) in chk:
                            rec[f"chk_{sc}_{it}"] = round(chk[(code, yymm, sc, it)] * 1000)
            rows.append(rec)
        kr = next((k for k in kind_rows if k["code"] == code), None)
        firms[code] = {"code": code, "name": name_of.get(code, ""), "market": mkt_of.get(code, ""),
                       "kind": kr, "plan": next((p for p in plans if p["code"] == code), None),
                       "valueup": vall.get(code[:5], []), "rounds": rows}

    # ---------- 재현 결과 (있으면) ----------
    replica = None
    if exists(FINAL / "replica_selection.csv"):
        replica = {"sector": pd.read_csv(FINAL / "replica_sector.csv").fillna("").to_dict("records"),
                   "selection": pd.read_csv(FINAL / "replica_selection.csv", dtype={"code": str, "corp5": str})
                   .fillna("").to_dict("records"),
                   "updated": mtime(FINAL / "replica_selection.csv")}

    # ---------- 진행 상황 ----------
    cur.execute("SELECT doc_class, COUNT(*) FROM pr_filing GROUP BY doc_class")
    pf = dict(cur.fetchall())
    cur.execute("SELECT COUNT(DISTINCT rcept_no) FROM pr_filing_xml")
    n_xml = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT rcept_no) FROM pr_filing_toc")
    n_toc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT rcept_no) FROM pr_fs_value")
    n_val = cur.fetchone()[0]
    status = [
        {"step": "① 회차 일정", "src": "CHECK", "state": "done", "detail": "13개 회차 · 2026.11 = 공표 11.2 / 기준 10.22 / 9.21~10.22 (보도자료 일치)",
         "updated": mtime(INTER / "rounds.csv")},
        {"step": "② 산정 대상", "src": "KIND·KRX", "state": "done",
         "detail": f"회차별 주권 스냅샷 · 2026.11 유가 {len(snap26[snap26.market == 'KOSPI'])} · 코스닥 {len(snap26[snap26.market == 'KOSDAQ'])} (제외 규칙 판정 전)",
         "updated": mtime(INTER / "universe_snap.csv")},
        {"step": "③ 시가총액", "src": "CHECK", "state": "done" if gw_files >= n_codes else "running",
         "detail": f"{gw_files:,} / {n_codes:,} 종목 수집 · 회차 평균 {len(mc):,}행", "updated": mtime(INTER / "mktcap_round.csv"),
         "pct": round(100 * min(gw_files, n_codes) / n_codes)},
        {"step": "④ 정기보고서 목록", "src": "OpenDART → MySQL", "state": "done",
         "detail": f"사업 {pf.get('annual', 0):,} · 반기 {pf.get('semi', 0):,} · 분기 {pf.get('quarter', 0):,}", "updated": ""},
        {"step": "⑤ 순자산(CHECK IFRS)", "src": "CHECK", "state": "done" if chk else "waiting",
         "detail": f"{len({k[0] for k in chk}):,}사" if chk else "시가총액 수집 뒤 시작 (CHECK 순차 호출)",
         "updated": mtime(INTER / "equity_hist.csv")},
        {"step": "⑥ 근거 보고서(DART)", "src": "DART", "state": "running",
         "detail": f"원문 {n_xml:,}건 · 목차 {n_toc:,}건 · 재무상태표 값 {n_val:,}건 · 캡처 {len(caps):,}장", "updated": ""},
        {"step": "⑦ 선정·면제 판정", "src": "재현",
         "state": ("done" if len({k[0] for k in chk}) >= snap.code.nunique() - 5 else "running") if replica else "waiting",
         "detail": (("185 → 151 재현 · KIND 대조" if len({k[0] for k in chk}) >= snap.code.nunique() - 5 else
                     f"부분 판정 — 순자산 확보 {len({k[0] for k in chk}):,}/{snap.code.nunique():,}사 기준 (업종 순위가 아직 불완전)")
                    if replica else "시가총액·순자산·업종 확보 후"), "updated": replica["updated"] if replica else ""},
    ]

    # ---------- 재현 격자: 전 기업 × 13회차 (기업 추적·업종 점그림·13칸 띠) ----------
    # r[seq] = [PBR, 업종내 순위, 업종 사수, 기준선, 저PBR여부, 시총(억), 분모(억)]
    grid = {}
    if exists(FINAL / "replica_firm_round.csv"):
        fr = pd.read_csv(FINAL / "replica_firm_round.csv", dtype={"code": str, "round": str})
        nz = lambda v, nd=2: None if pd.isna(v) else round(float(v), nd)
        for r in fr.itertuples():
            g = grid.setdefault(r.code, {"n": r.name, "m": r.market, "g": r.gics, "r": {}})
            if r.round == "2026.11":      # 이전상장사는 최근 회차 시장·업종으로 표시
                g["g"], g["m"] = r.gics, r.market
            g["r"][int(r.seq)] = [nz(r.pbr), None if pd.isna(r.rank) else int(r.rank),
                                  None if pd.isna(r.n_grp) else int(r.n_grp), nz(r.cut), bool(r.low),
                                  nz(r.mktcap_avg / 1e8 if pd.notna(r.mktcap_avg) else None, 0),
                                  nz(r.equity_k / 1e5 if pd.notna(r.equity_k) else None, 0)]

    # ---------- 2026.11 모집단 차감 (상장 주권 → 산정 대상) ----------
    from s06_select import admin_excluded
    adm = pd.read_csv(INTER / "admin_flags.csv", dtype=str)
    excl = admin_excluded("nomcap", snap26)
    reason = adm.drop_duplicates("종목명").set_index("종목명")
    univ26 = {"listed": snap26.groupby("market").size().to_dict(),
              "excluded": [{"code": x.code, "name": x.corp_name, "market": x.market,
                            "reason": reason["지정사유"].get(x.corp_name, ""), "date": reason["지정일"].get(x.corp_name, "")}
                           for x in snap26[snap26.code.isin(excl)].itertuples()],
              "kept_admin": [{"code": x.code, "name": x.corp_name, "market": x.market,
                              "reason": reason["지정사유"].get(x.corp_name, ""), "date": reason["지정일"].get(x.corp_name, "")}
                             for x in snap26[snap26.corp_name.isin(adm[adm["지정일"] <= "2026-10-22"]["종목명"])
                                             & ~snap26.code.isin(excl)].itertuples()]}

    # ---------- 계산 예시: 광동제약 2026.11 ----------
    example = None
    ex_code = "009290"
    if exists(INTER / "mktcap_daily.csv") and ex_code in firms:
        r26 = next(r for r in rounds if r["round"] == "2026.11")
        cal = [r["date"] for r in csv.DictReader(open(INTER / "calendar.csv", encoding="utf-8"))]
        i = cal.index(r26["base_date"])
        days = cal[i - 19: i + 1]
        dly = pd.read_csv(INTER / "mktcap_daily.csv", dtype={"code": str, "date": str})
        pref = pd.read_csv(INTER / "pref_map.csv", dtype=str)
        pcodes = list(pref[pref.common_code == ex_code].pref_code)
        sub = dly[dly.code.isin([ex_code, *pcodes]) & dly.date.isin(days)]
        rows_ex = [{"date": d, "common": int(sub[(sub.code == ex_code) & (sub.date == d)].mktcap.sum()),
                    "pref": int(sub[(sub.code != ex_code) & (sub.date == d)].mktcap.sum()),
                    "close": int(sub[(sub.code == ex_code) & (sub.date == d)].close.sum())} for d in days]
        example = {"code": ex_code, "name": firms[ex_code]["name"], "days": rows_ex, "round": firms[ex_code]["rounds"][-1]}

    vu_all = {c5: [{"dt": r.disc_dt, "title": r.title, "url": r.kind_url} for r in g.sort_values("disc_dt").itertuples()]
              for c5, g in v.groupby("corp5")}

    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "status": status, "rounds": rounds,
            "universe": snap.groupby(["round", "market"]).size().unstack().reset_index().to_dict("records"),
            "press": {"sector": p_sector, "totals": p_tot, "list": p_list}, "kind": kind_rows, "plans": plans,
            "firms": firms, "replica": replica, "grid": grid, "univ26": univ26, "example": example,
            "valueup": vu_all,
            "coverage": {"equity": len({k[0] for k in chk}), "universe": int(snap.code.nunique())}}
    SITE.mkdir(exist_ok=True)
    js = "window.DATA = " + json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":")) + ";\n"
    (SITE / "data.js").write_text(js, encoding="utf-8")
    print(f"site/data.js {len(js) / 1e6:.1f}MB · 기업 {len(firms)} · 캡처 {len(caps)} · {time.time() - t0:.0f}초")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=0, help="초. 0 이면 한 번만")
    args = ap.parse_args()
    while True:
        try:
            if args.watch:
                # 수집 중인 시가총액은 캐시분으로 회차 평균을 다시 집계한다 (네트워크 없음)
                import subprocess
                env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
                here = Path(__file__).parent
                for cmd in (["s03_mktcap.py", "--cache-only"], ["s05_equity.py", "--cache-only"], ["s06_select.py"]):
                    r = subprocess.run([sys.executable, str(here / cmd[0]), *cmd[1:]], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", env=env)
                    tail = (r.stdout or "").strip().splitlines()[-3:]
                    print(f"  {cmd[0]} rc={r.returncode}", *tail, sep=" | ")
            main_once()
        except Exception as e:  # 수집 중 파일이 쓰이는 순간 등 — 다음 주기에 다시
            print("빌드 실패:", type(e).__name__, e)
        if not args.watch:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
