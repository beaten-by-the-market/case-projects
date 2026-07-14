"""부록 B '사유별 제외 규모' 표를 재현한다.

`status.py` 는 편입가능 마스크(합집합)만 만든다. 사유별로 **몇 건의 지정 공시가**
**몇 종목에** 걸려 **며칠을 제외시켰는지**는 어디에도 남지 않아, 보고서 표를 검증할 수
없었다. 이 스크립트가 그 표를 만든다.

⚠ **제외 종목-일은 두 가지로 센다.**
  · `raw`      = 마스크의 (종목, 거래일) 쌍 전부. 상장 전·상폐 후 날짜도 포함된다.
  · `listed`   = 그중 **실제로 그 종목이 상장돼 거래된 날**과 겹치는 것만.
    분모(코스닥 전체 종목-일)와 같은 기준이므로 **비율은 반드시 이쪽으로 낸다.**
  status.py 가 찍던 비율은 분모가 하드코딩 1,800종목이라 어느 쪽과도 맞지 않았다.

출력: output/exclusions_by_reason.txt · output/exclusions_by_reason.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
END = "20260630"
_SP = re.compile(r"\s+")


def _gongsi() -> pd.DataFrame:
    g = pd.read_csv(DATA / "gongsi.csv", dtype={"code": str, "date": str, "time": str})
    g = g[(g.mtvcd == 320) & g.code.notna()].copy()
    g["n"] = g.title.fillna("").map(lambda t: _SP.sub("", t))
    return g


def _spans_for(g: pd.DataFrame, kw: str, days: list[str], idx: dict[str, int]):
    """status.py 규칙 A 와 동일한 로직을 **한 유형만** 돌려 구간과 이벤트 수를 함께 낸다."""
    sub = g[g.n.str.contains(kw, na=False)].copy()
    total_related = len(sub)

    sub = sub[~sub.n.str.contains("기타시장안내|우려", na=False)]          # A-0
    sub = sub[~sub.n.str.contains(r"\(정정\)", na=False)]                 # A-1

    sub["release"] = (sub.n.str.contains("해제", na=False)
                      & ~sub.n.str.contains("일부해제", na=False))         # A-3
    partial = int((sub.n.str.contains("해제", na=False)
                   & sub.n.str.contains("일부해제", na=False)).sum())
    sub["forecast"] = ~sub.release & sub.n.str.contains("예고", na=False)  # A-4
    n_forecast = int(sub.forecast.sum())
    sub = sub[~sub.forecast].sort_values(["code", "date", "time"])

    desig = sub[~sub.release]
    spans: list[tuple[str, str, str]] = []
    left_censored: set[str] = set()
    for code, ev in sub.groupby("code"):
        open_at = None
        for r in ev.itertuples():
            if not r.release:
                if open_at is None:
                    open_at = r.date
            elif open_at is not None:
                spans.append((code, open_at, r.date))
                open_at = None
            else:                                                          # A-9 좌측절단
                left_censored.add(code)
                spans.append((code, days[0], r.date))
        if open_at is not None:
            spans.append((code, open_at, END))                             # A-8

    bad: set[tuple[str, str]] = set()
    lengths: list[int] = []
    for code, s, e in spans:
        i = idx.get(s)
        if i is None:
            i = next((k for k, d in enumerate(days) if d >= s), None)
            if i is None:
                continue
            i -= 1
        j = idx.get(e, len(days) - 1)
        span_days = days[i + 1:j + 1] if s != days[0] else days[:j + 1]
        lengths.append(len(span_days))
        bad |= {(code, d) for d in span_days}

    return {
        "관련 공시": total_related,
        "지정 공시": len(desig),
        "종목": desig.code.nunique(),
        "전체해제": int(sub.release.sum()),
        "일부해제": partial,
        "지정예고": n_forecast,
        "구간": len(spans),
        "중앙 지정기간(거래일)": int(pd.Series(lengths).median()) if lengths else 0,
        "좌측절단 종목": len(left_censored),
        "bad": bad,
    }


def main() -> None:
    d = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str},
                    usecols=["fam", "code", "date"])
    d = d[d.fam == "m003"]
    days = sorted(d.date.unique())
    idx = {x: i for i, x in enumerate(days)}
    listed = set(map(tuple, d[["code", "date"]].values))     # 실제 상장·거래일 (분모)
    g = _gongsi()

    rows, masks = [], {}
    for label, kw in status.TYPES.items():
        r = _spans_for(g, kw, days, idx)
        masks[label] = r.pop("bad")
        r["제외 종목-일(raw)"] = len(masks[label])
        r["제외 종목-일(상장일 교집합)"] = len(masks[label] & listed)
        rows.append({"사유": label, **r})

    # ── 매매거래정지 ──
    h = g[g.n.str.contains("주권매매거래정지", na=False)]
    n_halt = len(h[~h.n.str.contains(r"기간변경|해제|\(정정\)", na=False)])
    n_chg = len(h[h.n.str.contains("기간변경", na=False)])
    n_rel = len(h[h.n.str.contains("해제", na=False)
                  & ~h.n.str.contains(r"기간변경|\(정정\)", na=False)])   # B-1 과 같은 기준
    halt_mask = status.halt_days(days)
    masks["매매거래정지"] = halt_mask
    rows.append({
        "사유": "매매거래정지", "관련 공시": len(h), "지정 공시": n_halt,
        "종목": h[~h.n.str.contains(r"기간변경|해제|\(정정\)", na=False)].code.nunique(),
        "전체해제": n_rel, "일부해제": 0, "지정예고": n_chg, "구간": n_halt,
        "중앙 지정기간(거래일)": 0, "좌측절단 종목": 0,
        "제외 종목-일(raw)": len(halt_mask),
        "제외 종목-일(상장일 교집합)": len(halt_mask & listed),
    })

    # ── 합집합 (status.ineligible_days 와 동일) ──
    union = status.ineligible_days(days)
    u_listed = union & listed
    t = pd.DataFrame(rows).set_index("사유")

    lines = []
    P = lines.append
    P("=== 부록 B. 사유별 제외 규모 (실측 재계산) ===")
    P(f"코스닥 전체 종목-일(m003, 상장·거래일 기준): {len(listed):,}  "
      f"[{d.code.nunique():,}종목 × 거래일 {len(days)}]")
    P("")
    P(t.to_string())
    P("")
    P(f"합집합(raw)             : {len(union):,} 쌍 · 영향 {len({c for c, _ in union}):,}종목")
    P(f"합집합(상장일 교집합)   : {len(u_listed):,} 쌍 · 영향 {len({c for c, _ in u_listed}):,}종목")
    P(f"  → 코스닥 전체 종목-일의 {len(u_listed) / len(listed) * 100:.1f}%")
    P("  ※ raw 에는 상장 전·상폐 후 날짜가 섞인다(마스크를 전 거래일에 대해 만들기 때문).")
    P("     비율은 분모와 기준이 같은 '상장일 교집합'으로만 낸다.")
    P("")

    # ── 함정 3: 지정예고를 지정으로 세면? ──
    warn = g[g.n.str.contains("투자경고종목", na=False)]
    warn_c = warn[~warn.n.str.contains("기타시장안내|우려", na=False)]
    warn_c = warn_c[~warn_c.n.str.contains(r"\(정정\)", na=False)]
    rel = warn_c.n.str.contains("해제") & ~warn_c.n.str.contains("일부해제")
    fc = ~rel & warn_c.n.str.contains("예고")
    n_fc_raw = int(warn.n.str.contains("예고", na=False).sum())
    P("=== 함정 3. '지정예고'를 지정으로 세면 (투자경고) ===")
    P(f"투자경고 관련 공시 {len(warn):,}건 중 제목에 '예고'가 든 것 {n_fc_raw:,}건 "
      f"({n_fc_raw / len(warn) * 100:.0f}%)")
    P(f"  올바른 지정 종목 수      : {warn_c[~rel & ~fc].code.nunique():,}개")
    P(f"  예고까지 지정으로 세면   : {warn_c[~rel].code.nunique():,}개")
    P("")

    # ── 함정 5: 정지 구간을 통째로 빼면? ──
    dd = pd.read_csv(DATA / "daily_krx.csv", dtype={"code": str, "date": str})
    dd = dd[dd.fam == "m003"].copy()
    dd["vol"] = dd[["vol_sell", "vol_buy"]].fillna(0).max(axis=1)
    traded = {(r.code, r.date) for r in dd.itertuples() if r.vol > 0}
    hh = h[~h.n.str.contains(r"기간변경|\(정정\)", na=False)].copy()
    hh["release"] = hh.n.str.contains("해제", na=False)
    hh = hh.sort_values(["code", "date", "time"])
    naive: set[tuple[str, str]] = set()
    for c, x in hh.groupby("code"):
        open_at = None
        for r in x.itertuples():
            if not r.release:
                if open_at is None:
                    open_at = r.date
            elif open_at is not None:
                naive |= {(c, t) for t in days if open_at <= t <= r.date}
                open_at = None
        if open_at is not None:
            naive |= {(c, t) for t in days if t >= open_at}
    over = (naive - halt_mask) & listed
    P("=== 함정 5. 정지 '구간 전체'를 빼면 (규칙 B를 안 쓰면) ===")
    P(f"구간 통째 제외          : {len(naive & listed):,} 종목-일")
    P(f"규칙 B(공시일+무거래일) : {len(halt_mask & listed):,} 종목-일")
    P(f"  → 과다 제외 {len(over):,} 종목-일 · 그중 실제로 거래가 있던 날 "
      f"{len(over & traded):,}건 ({len(over & traded) / len(over) * 100:.0f}%)")

    # ── 왜 종목 단위로 빼지 않는가: 민감도 검정 ──
    # "한 번이라도 지정·정지 이력이 있으면 종목을 통째로 제외"하면 무슨 일이 벌어지는가.
    # ⚠ 반드시 **분석 유니버스(1,683종목) 안에서** 세야 한다. 유니버스 밖 종목을 섞으면
    #    배제+잔존이 1,683을 넘어간다.
    liq = pd.read_csv(OUT / "h1_stock_liquidity.csv", dtype={"code": str},
                      encoding="utf-8-sig").set_index("code")
    D = [f"D{i}" for i in range(1, 11)]
    P("")
    P("=== 왜 종목 단위로 빼지 않는가: 민감도 검정 (유니버스 1,683종목 기준) ===")
    P(f"{'배제 방식':22s} {'배제':>5} {'잔존':>6} {'포기 거래대금':>12}   배제 decile 분포 (D1→D10)")
    combos = [(k, {c for c, _ in masks[k]}) for k in ("투자경고", "투자위험", "관리종목", "환기종목")]
    combos.append(("넷 다 + 매매거래정지",
                   set().union(*[{c for c, _ in masks[k]} for k in masks])))
    for name, codes in combos:
        drop = liq[liq.index.isin(codes)]
        dist = drop.decile.value_counts().reindex(D).fillna(0).astype(int)
        P(f"{name:22s} {len(drop):5,} {len(liq) - len(drop):6,} "
          f"{drop.amt_sum.sum() / liq.amt_sum.sum() * 100:11.1f}%   "
          + "·".join(str(x) for x in dist))

    txt = "\n".join(lines)
    OUT.mkdir(exist_ok=True)
    (OUT / "exclusions_by_reason.txt").write_text(txt + "\n", encoding="utf-8")
    t.to_csv(OUT / "exclusions_by_reason.csv", encoding="utf-8-sig")
    print(txt)
    print(f"\n저장: {OUT}/exclusions_by_reason.txt · .csv")


if __name__ == "__main__":
    sys.path.insert(0, r"C:\Users\Peter\github\check-api-krx-dl\.claude\skills\checkapi-data\scripts")
    from _common import _force_utf8_stdout
    _force_utf8_stdout()
    main()
