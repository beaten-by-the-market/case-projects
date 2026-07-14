"""거래정지를 **유발한** 공시유형을 실측으로 추린다.

두 개의 독립된 소스를 쓴다.

1. **정지 공시 제목의 괄호 안 사유**. `주권매매거래정지(무상증자)` 처럼 사유가 붙는다.
   실측 결과 **910건 전부(100%)** 에 사유가 있다. 이것이 1차 소스다.
2. **같은 분(±1분)에 나간 동반 공시**. 실무상 거래소는 정지 사유 공시와 정지 공시를
   같은 분(또는 1분 차이)에 내보낸다. 이걸로 **"그 사유를 어떤 공시가 실어 날랐는가"** 를 본다.

⚠ 모수는 **코스닥 시장(mtvcd=320) 전종목·전기간**이다. 본 연구의 1,683종목 분석 유니버스로
거르지 않는다. 유니버스는 정지일을 이미 제외하므로, 정지 자체를 보려면 유니버스 밖으로 나가야 한다.
(실제로 정지 종목 577개 중 171개가 유니버스 밖이다: 상폐·스팩·우선주·장기정지.)

정지 공시 정의(규칙 B와 동일): `주권매매거래정지` − `기간변경` − `해제` − `(정정)`
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
KOSDAQ, WINDOW = "320", 1          # WINDOW = 분. "같은 분(0) 또는 1분 차이(1)"
LEGAL = ("주식회사", "(주)", "㈜", "(유)", "유한회사")

# ── 축 1. 관리부담 ────────────────────────────────────────────────────────────
# **집행형** = 이미 공표된 절차를 예정대로 집행하느라 멈추는 것. 날짜가 미리 잡혀 있으므로
#   거래소가 새로 판단할 게 없다 → **관리부담이 낮다.**
#   실측으로 이 둘뿐이고, **동반 공시가 없다**(313건 중 302건이 여기다). 그게 곧 판별자다.
# **뉴스형** = 사건이 터진 그 시각에 **즉시 정지를 걸어야** 하는 것. 절차 개시를 알리는
#   결정 공시(무상증자·감자 등)도 그 시점에 30분 정지가 걸리므로 여기 들어간다 → **관리부담이 있다.**
EXECUTION_ONLY = ("주식의 병합", "전자등록", "SPAC 소멸합병")

# ── 축 2. 사유의 성격 ─────────────────────────────────────────────────────────
# **위에서부터 먼저 맞는 것**을 쓴다(순서 의미 있음).
# ⚠ 원문 표기가 흔들린다: `투자자 보호`/`투자자보호`, `상장폐지`/`상장페지`(오타),
#   `회생절차개시신청`/`회생절차 개시신청`. 공백 제거 + 오타를 함께 잡는다.
KIND_OF_HALT = [
    ("부실·위험", "상장폐지", "상장페지", "실질심사", "관리종목", "불성실공시", "영업정지",
                 "회계처리", "풍문", "보도", "횡령", "배임", "부도", "회생", "파산",
                 "감사의견", "투자자보호", "사업보고서미제출", "조회공시신고시한"),
    ("대형계약",  "단일판매", "공급계약"),
    ("자본·조직변동", "주식의병합", "무상증자", "자본감소", "감자", "이익소각", "주식교환", "분할",
                 "액면", "전자등록", "합병", "SPAC", "영업양수도", "우회상장", "주식배당"),
]


def _burden(reason: str) -> str:
    return "집행형(부담 낮음)" if any(k in reason for k in EXECUTION_ONLY) else "뉴스형(즉시조치)"


def _mins(t: str) -> int:
    t = t.zfill(6)
    return int(t[:2]) * 60 + int(t[2:4])


def _strip_company(title: str, names: set[str]) -> str:
    """제목 앞머리의 회사명을 뗀다. ⚠ 법인격 표기가 이름 앞뒤 어디에나 붙는다."""
    t = title.strip()
    for w in LEGAL:
        t = t.replace(w, " ", 2)
    t = " ".join(t.split())
    for n in sorted((n for n in names if t.startswith(n)), key=len, reverse=True):
        return t[len(n):].strip()
    return t.split(" ", 1)[1].strip() if " " in t else t


def _kind(title: str) -> str:
    return title.split("(")[0].strip() or title.strip()


def _nature(reason: str) -> str:
    r = reason.replace(" ", "")          # ⚠ 공백 표기가 흔들린다 → 지우고 맞춘다
    for nature, *kws in KIND_OF_HALT:
        if any(k in r for k in kws):
            return nature
    return "기타"


def main() -> None:
    g = pd.read_csv(DATA / "gongsi.csv", dtype=str).dropna(subset=["title"])
    g = g[g.mtvcd == KOSDAQ].copy()
    g["min"] = g.time.map(_mins)
    names = set(pd.read_csv(DATA / "master.csv", dtype=str).name.dropna())

    is_halt = g.title.str.contains("주권매매거래정지", na=False)
    halt = g[is_halt & ~g.title.str.contains(r"기간변경|해제|\(정정\)", na=False)].copy()
    halt["reason"] = halt.title.str.extract(r"주권매매거래정지[^(]*\((.*?)\)")[0].fillna("(표기 없음)")
    halt["nature"] = halt.reason.map(_nature)
    halt["burden"] = halt.reason.map(_burden)
    halt["t"] = halt.time.str.zfill(6).astype(int)
    halt["after"] = halt.t.between(154000, 200000)
    print(f"코스닥 최초 매매거래정지 {len(halt):,}건 · 종목 {halt.code.nunique():,}개  "
          f"(사유 표기 {(halt.reason != '(표기 없음)').mean() * 100:.0f}%)")

    # ── 같은 분(±1분) 동반 공시 ──
    other = g[~is_halt]
    j = halt[["code", "date", "min", "reason", "nature", "title"]].merge(
        other[["code", "date", "min", "title"]], on=["code", "date"], suffixes=("_halt", "_co"))
    j["gap"] = (j.min_co - j.min_halt).abs()
    co = j[j.gap <= WINDOW].copy()
    co["kind"] = co.title_co.map(lambda t: _kind(_strip_company(t, names)))
    matched = co.groupby(["code", "date", "min_halt"]).ngroups
    print(f"같은 분(±{WINDOW}분) 동반 공시가 붙은 정지: {matched:,}건 ({matched / len(halt) * 100:.1f}%) "
          f"· 동반 공시 {len(co):,}건")

    def _tab(by):
        x = (halt.groupby(by).agg(정지=("code", "size"), 종목=("code", "nunique"),
                                  애프터=("after", "sum")).sort_values("정지", ascending=False))
        x["비중_pct"] = (x.정지 / len(halt) * 100).round(1)
        x["애프터_pct"] = (x.애프터 / x.정지 * 100).round(1)
        return x

    # ── 창 넓이 민감도. ±1분이 자의적 선택이 아님을 보인다 ──
    # 뉴스형에는 좁은 창에서도 거의 다 붙고, 집행형에는 창을 30배로 넓혀도 안 붙는다.
    # → "동반 공시가 없다"는 것은 창이 좁아서가 아니라 **애초에 유발한 뉴스가 없어서**다.
    def _cover(w: int, burden: str) -> float:
        sub = halt[halt.burden == burden]
        hit = j[(j.gap <= w) & j.code.isin(sub.code)].merge(
            sub[["code", "date", "min"]].rename(columns={"min": "min_halt"}),
            on=["code", "date", "min_halt"])
        return hit.groupby(["code", "date", "min_halt"]).ngroups / len(sub) * 100

    WINDOWS = [0, 1, 5, 30]
    sens = pd.DataFrame(
        {"뉴스형_커버_pct": [round(_cover(w, "뉴스형(즉시조치)"), 1) for w in WINDOWS],
         "집행형_커버_pct": [round(_cover(w, "집행형(부담 낮음)"), 1) for w in WINDOWS]},
        index=pd.Index([f"±{w}분" for w in WINDOWS], name="창"))

    bur, nat, cross = _tab("burden"), _tab("nature"), _tab(["burden", "nature"])
    rsn = (halt.groupby(["burden", "nature", "reason"])
               .agg(정지=("code", "size"), 종목=("code", "nunique"), 애프터=("after", "sum"))
               .sort_values(["burden", "nature", "정지"], ascending=[True, True, False]))
    trg = (co.groupby(["nature", "kind"]).agg(동반=("code", "size"), 종목=("code", "nunique"))
             .sort_values(["nature", "동반"], ascending=[True, False]))

    # ── 뉴스형(즉시조치)만: 유니버스 decile별 부담 ──
    news = halt[halt.burden.str.startswith("뉴스형")]
    liq = pd.read_csv(OUT / "h1_stock_liquidity.csv", dtype={"code": str}).set_index("code")
    hu = news[news.code.isin(liq.index)].copy()
    hu["decile"] = liq.loc[hu.code].decile.values
    D = [f"D{i}" for i in range(1, 11)]
    amt = liq.reset_index().groupby("decile").amt_sum.sum().reindex(D)   # 원 단위. 반올림 전
    dec = pd.DataFrame({
        "정지": hu.groupby("decile").size().reindex(D).fillna(0).astype(int),
        "애프터": hu.groupby("decile").after.sum().reindex(D).fillna(0).astype(int),
        "거래대금_조": (amt / 1e12).round(1),
    })
    dec["정지_pct"] = (dec.정지 / dec.정지.sum() * 100).round(1)
    dec["거래대금_pct"] = (amt / amt.sum() * 100).round(1)
    per100 = dec.정지 / (amt / 1e10)          # ⚠ 반올림 전 값으로 나눈다
    dec["정지_per_100억"] = per100.round(4)
    # ⚠ 100억 단위는 D1 값이 0.0001 로 뭉개져 표에서 배수가 재현되지 않는다.
    #    보고서 표는 **1조원 단위**를 쓴다. 유효숫자 3자리면 161배가 그대로 나온다.
    dec["정지_per_1조"] = (dec.정지 / (amt / 1e12)).round(4)
    ratio = per100["D10"] / per100["D1"]

    OUT.mkdir(exist_ok=True)

    # ── 사람이 읽는 목록으로 저장한다 (종목명·decile·동반공시를 붙인다) ──
    nm = pd.read_csv(DATA / "master.csv", dtype=str).set_index("code").name
    dmap = liq.decile
    first_co = (co.sort_values("gap").groupby(["code", "date", "min_halt"]).title_co.first())

    out = halt.copy()
    out["종목명"] = out.code.map(nm).fillna("(상장폐지)")
    out["decile"] = out.code.map(dmap).fillna("(유니버스 밖)")
    out["동반공시"] = [first_co.get((c, d, m), "") for c, d, m in zip(out.code, out.date, out["min"])]
    out["시각"] = out.time.str.zfill(6).str.replace(r"(\d\d)(\d\d)(\d\d)", r"\1:\2:\3", regex=True)
    out["애프터"] = out.after.map({True: "Y", False: ""})
    cols = ["date", "시각", "애프터", "code", "종목명", "decile", "burden", "nature", "reason",
            "동반공시", "title"]
    (out[cols].rename(columns={"date": "공시일", "code": "종목코드", "burden": "관리부담",
                               "nature": "사유성격", "reason": "정지사유", "title": "정지공시_원문"})
        .sort_values(["공시일", "시각"])
        .to_csv(OUT / "halt_events.csv", index=False, encoding="utf-8-sig"))

    pairs = co.copy()
    pairs["종목명"] = pairs.code.map(nm).fillna("(상장폐지)")
    (pairs[["date", "code", "종목명", "nature", "reason", "gap", "title_co", "kind", "title_halt"]]
        .rename(columns={"date": "공시일", "code": "종목코드", "nature": "사유성격",
                         "reason": "정지사유", "gap": "시차_분", "title_co": "동반공시_원문",
                         "kind": "동반공시_유형", "title_halt": "정지공시_원문"})
        .sort_values(["공시일", "종목코드"])
        .to_csv(OUT / "halt_trigger_pairs.csv", index=False, encoding="utf-8-sig"))

    rsn.to_csv(OUT / "halt_triggers.csv", encoding="utf-8-sig")
    dec.to_csv(OUT / "halt_decile.csv", encoding="utf-8-sig")

    with (OUT / "halt_triggers.txt").open("w", encoding="utf-8") as f:
        f.write(f"코스닥(mtvcd=320) 최초 매매거래정지 {len(halt):,}건 · 종목 {halt.code.nunique():,}개\n")
        f.write("※ 분석 유니버스(1,683종목)로 거르지 않은 코스닥 전수.\n\n")
        f.write(f"같은 분(±1분) 동반 공시 있음: {matched:,}건 ({matched / len(halt) * 100:.1f}%)\n")
        f.write(f"동반 공시 없음:              {len(halt) - matched:,}건\n")
        f.write("시차(분) 분포. 0 = 같은 분\n" + co.gap.value_counts().sort_index().to_string() + "\n\n")
        f.write("=== 창 넓이 민감도 (±1분 채택의 근거) ===\n" + sens.to_string() + "\n")
        f.write("※ 창을 30배로 넓혀도 집행형에는 거의 안 붙는다 → 동반 공시가 없는 것은\n"
                "   창이 좁아서가 아니라 애초에 유발한 뉴스가 없어서다.\n\n")
        f.write("=== 축1. 관리부담 ===\n" + bur.to_string() + "\n\n")
        f.write("=== 축2. 사유의 성격 ===\n" + nat.to_string() + "\n\n")
        f.write("=== 교차 ===\n" + cross.to_string() + "\n\n")
        f.write("=== 정지 사유 상세 (정지 공시 제목의 괄호) ===\n" + rsn.to_string() + "\n\n")
        f.write("=== 그 사유를 실어 나른 동반 공시 유형 ===\n" + trg.to_string() + "\n\n")
        f.write(f"=== 뉴스형 정지 {len(news):,}건 중 유니버스 {len(hu):,}건의 decile 분포 ===\n")
        f.write(dec.to_string() + "\n")

    print("\n=== 축1. 관리부담 ===");  print(bur.to_string())
    print("\n=== 교차 (관리부담 × 사유) ===");  print(cross.to_string())
    print(f"\n=== 뉴스형(즉시조치) {len(news):,}건. 유니버스 {len(hu):,}건의 decile 분포 ===")
    print(dec.to_string())
    lo = dec.loc[["D6", "D7", "D8", "D9", "D10"]]
    print(f"\n하위 절반(841종목): 거래대금 {lo.거래대금_pct.sum():.1f}% · 뉴스형 정지 {lo.정지_pct.sum():.1f}%")
    print(f"거래대금 100억원당 뉴스형 정지: D1 {per100['D1']:.5f} vs D10 {per100['D10']:.5f} "
          f"= **{ratio:.0f}배**")
    print(f"\n저장: {OUT}/halt_events.csv · halt_triggers.csv · halt_trigger_pairs.csv · "
          f"halt_decile.csv · halt_triggers.txt")


if __name__ == "__main__":
    main()
