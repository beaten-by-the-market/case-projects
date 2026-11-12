"""s15 DataGuide 6 원본(엑셀) → 계산용 CSV. s06 --src dg 의 입력이다.

입력 (data/raw/dataguide, git 제외 — DataGuide 구독자만 다시 받을 수 있다. 받는 법은 docs/04)
  DG_시총.xlsx           달력기준 · 일간 · S410001250 시가총액(백만원) · 종목 행 × 날짜 열
  DG_자본_회계기준.xlsx   회계기준 · 분기 누적 · 자본총계(지배)[C]·자본총계[C]·자본총계[S](천원) · 코드·결산월·회계연도·분기 행
  DG_상태_*.xlsx         달력기준 · COM 6개 아이템 · 종목·아이템 행 × 날짜 열 (기준일 하루 또는 기간)

출력 (data/interim, DataGuide 값이라 git 제외)
  dg_mcap_window.csv  code, date, mktcap_mn       회차 20거래일 구간 날짜만
  dg_mcap_round.csv   round, code, n_days, mktcap_common, mktcap_pref, mktcap_avg (원) — s03 mktcap_round 와 같은 열
  dg_equity.csv       code, name, fye, fy, q, yymm, con_parent, con_total, sep_total (천원)
  dg_status.csv       base_date, code, name, 시장구분, 상장일, 관리종목여부, 관리종목지정사유, 거래정지여부, 거래정지사유

재무년월(yymm) = 결산일(회계연도 + (결산월 ≤ 5 ? 1 : 0)년 결산월)에서 분기마다 3개월씩 앞으로.
DataGuide 결산월은 지금 결산월이지만 옛 기간 값도 재무년월 자리에 놓여 있어 (종목, 재무년월)로 찾으면 맞다(docs/04 §2-3).
"""
import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _rules import ROOT  # noqa: E402

INTER, RAW = ROOT / "data/interim", ROOT / "data/raw/dataguide"
Q_OFF = {"1st-Quarter": 9, "Semi-Annual": 6, "3rd-Quarter": 3, "결산": 0}


def windows() -> tuple[list[dict], dict[str, list[str]]]:
    rounds = list(csv.DictReader(open(INTER / "rounds.csv", encoding="utf-8")))
    cal = [r["date"] for r in csv.DictReader(open(INTER / "calendar.csv", encoding="utf-8"))]
    win = {}
    for r in rounds:
        i = cal.index(r["base_date"])
        win[r["round"]] = cal[i - 19: i + 1]
    return rounds, win


def sheet_rows(path: Path):
    return openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True)


def date_cols(hdr) -> dict[str, int]:
    return {str(h)[:10].replace("-", ""): j for j, h in enumerate(hdr) if j >= 6 and h is not None}


def mcap(rounds, win):
    rows = sheet_rows(RAW / "DG_시총.xlsx")
    for _ in range(8):
        next(rows)
    col = date_cols(next(rows))
    need = sorted(set().union(*map(set, win.values())))
    miss = [d for d in need if d not in col]
    if miss:
        raise SystemExit(f"DG_시총 에 없는 구간 날짜 {miss[:5]}")
    out = []
    for r in rows:
        if r[0]:
            out += [(r[0][1:], d, float(r[col[d]])) for d in need if r[col[d]] not in (None, "")]
    D = pd.DataFrame(out, columns=["code", "date", "mktcap_mn"])
    D.to_csv(INTER / "dg_mcap_window.csv", index=False)

    by = defaultdict(dict)
    for x in D.itertuples():
        by[x.code][x.date] = x.mktcap_mn * 1e6
    pref_of = defaultdict(list)
    for p in csv.DictReader(open(INTER / "pref_map.csv", encoding="utf-8")):
        pref_of[p["common_code"]].append(p["pref_code"])
    snap = pd.read_csv(INTER / "universe_snap.csv", dtype=str)
    res = []
    for r in rounds:
        days = win[r["round"]]
        for code in sorted(set(snap[snap["round"] == r["round"]].code)):
            c = [by[code][d] for d in days if d in by.get(code, {})]
            pv = [sum(by[p].get(d, 0) for p in pref_of.get(code, [])) for d in days if d in by.get(code, {})]
            res.append({"round": r["round"], "code": code, "n_days": len(c),
                        "mktcap_common": round(sum(c) / len(c)) if c else "",
                        "mktcap_pref": round(sum(pv) / len(pv)) if pv else 0,
                        "mktcap_avg": round((sum(c) + sum(pv)) / len(c)) if c else ""})
    pd.DataFrame(res).to_csv(INTER / "dg_mcap_round.csv", index=False)
    print(f"시가총액: 종목 {D.code.nunique()} · 구간 값 {len(D)} · 회차행 {len(res)}")


def equity():
    rows = sheet_rows(RAW / "DG_자본_회계기준.xlsx")
    for _ in range(11):
        next(rows)
    A = pd.DataFrame([r[:8] for r in rows if r[0]],
                     columns=["code", "name", "fye", "fy", "q", "con_parent", "con_total", "sep_total"])
    A["code"] = A.code.str[1:]
    for c in ["con_parent", "con_total", "sep_total"]:
        A[c] = pd.to_numeric(A[c], errors="coerce")
    fye = pd.to_numeric(A.fye, errors="coerce")
    mon = (A.fy.astype(int) + (fye <= 5).astype(int)) * 12 + fye - 1 - A.q.map(Q_OFF)
    A["yymm"] = ((mon // 12) * 100 + mon % 12 + 1).astype("Int64")
    A = A.dropna(subset=["con_parent", "con_total", "sep_total"], how="all")
    A.to_csv(INTER / "dg_equity.csv", index=False)
    print(f"자본: 종목 {A.code.nunique()} · 값 있는 기간 {len(A)}")


def status(rounds):
    bases = {r["base_date"] for r in rounds}
    got = {}
    for f in sorted(glob.glob(str(RAW / "DG_상태_*.xlsx"))):
        rows = list(sheet_rows(Path(f)))
        col = date_cols(rows[8])
        for d in sorted(bases & set(col) - set(got)):
            j = col[d]
            L = pd.DataFrame([(r[0], r[1], r[4], r[j]) for r in rows[9:] if r[0]], columns=["code", "name", "item", "v"])
            W = L.pivot_table(index=["code", "name"], columns="item", values="v", aggfunc="first").reset_index()
            W.insert(0, "base_date", d)
            W["code"] = W.code.str[1:]
            got[d] = W
            print(f"상태 {d}: {Path(f).name} · 종목 {len(W)}")
    miss = sorted(bases - set(got))
    if miss:
        raise SystemExit(f"상태 파일에 없는 기준일 {miss}")
    cols = ["base_date", "code", "name", "시장구분", "상장일", "관리종목여부", "관리종목지정사유", "거래정지여부", "거래정지사유"]
    S = pd.concat(got.values(), ignore_index=True).reindex(columns=cols)
    S.to_csv(INTER / "dg_status.csv", index=False)


def main():
    rounds, win = windows()
    status(rounds)
    equity()
    mcap(rounds, win)


if __name__ == "__main__":
    main()
