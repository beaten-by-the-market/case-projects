"""s01 거래일 달력 → 반기별 공표일·PBR 기준일·시가총액 20거래일 구간.

지침(김앤장 해설, 2026.9.14 — docs/01-재현사양.md §1):
  공표일      = 매년 5월·11월의 최초 매매거래일
  PBR 기준일  = 공표일의 7영업일 전  (영업일 = 매매거래일로 본다. 2026.11 회차 10.22 로 검증)
  시가총액    = PBR 기준일을 포함한 최근 20매매거래일 일평균
  순자산      = PBR 기준일 현재 가장 최근 정기보고서(사업·반기)  → 5월 회차=직전 사업보고서, 11월 회차=당해 반기보고서

과거 회차도 같은 규칙으로 소급 계산한다(지침이 과거 반기 산정 방식을 따로 정하지 않음 — 재현 가정 A1).

입력: CHECK /stock/m002/hist_info (KOSPI 지수, jcode=1) 의 입회일 = 매매거래일
출력: data/interim/calendar.csv, data/interim/rounds.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ROOT, call, rows  # noqa: E402

OUT = ROOT / "data" / "interim"
N_ROUNDS = 13          # 2026.11 회차 포함 13회차(면제 불가 판정이 13개 기준일까지 본다)
LAST_PUB = (2026, 11)  # 최근 회차


def trading_days() -> list[str]:
    days = set()
    for y in range(2019, 2027):
        d = call("/stock/m002/hist_info", jcode="1", sdate=f"{y}0101", edate=f"{y}1231",
                 data_list="F12506")
        days |= {str(r["F12506"]) for r in rows(d) if r.get("F12506")}
    return sorted(d for d in days if d <= "20261110")


def rounds(days: list[str]) -> list[dict]:
    out = []
    y, m = LAST_PUB
    for i in range(N_ROUNDS):
        ym = f"{y}{m:02d}"
        pub = next(d for d in days if d.startswith(ym))
        k = days.index(pub)
        base = days[k - 7]
        win = days[days.index(base) - 19: days.index(base) + 1]
        assert len(win) == 20
        out.append({
            "round": f"{y}.{m:02d}",
            "seq": N_ROUNDS - i,                     # 1 = 가장 오래된 회차
            "pub_date": pub,
            "base_date": base,
            "win_start": win[0],
            "win_end": win[-1],
            "report_kind": "annual" if m == 5 else "semi",
            "period_end": f"{y-1}-12-31" if m == 5 else f"{y}-06-30",
        })
        y, m = (y, 5) if m == 11 else (y - 1, 11)
    return out[::-1]


def main():
    days = trading_days()
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "calendar.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date"])
        w.writerows([[d] for d in days])
    rs = rounds(days)
    with open(OUT / "rounds.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
    for r in rs:
        print(r)
    last = rs[-1]
    assert (last["pub_date"], last["base_date"], last["win_start"]) == ("20261102", "20261022", "20260921"), \
        "2026.11 회차가 보도자료(공표 11.2 · 기준 10.22 · 구간 9.21~10.22)와 다르다"
    print("검증 OK: 2026.11 회차 = 보도자료 일정과 일치")


if __name__ == "__main__":
    main()
