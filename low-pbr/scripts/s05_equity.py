"""s05 순자산(자본총계)·업종 — CHECK IFRS 계정 이력 + 기업 기본정보.

원천 (CHECK, 금액 단위 천원)
  /etc/ifrs/comp_ifrs_hist  jcode, icode   → 분기별 전체 이력. TERM_TYP 1x=별도 · 3x=연결 (x1 누적, x2 분기 — 재무상태표는 같은 값)
     115000 자본총계 · 115020 자본총계(지배)
  /etc/comp/comp_basic      jcode          → WICS 업종 · 결산월(FYE_MN) · 최근결산 주재무제표(MASTER_CHK: C 연결/I 개별)

어느 기간의 값을 쓰는지는 s06 이 정한다 — "기준일 현재 가장 최근 정기보고서(사업·반기)"의 작성기준일을
DART pr_filing 에서 회사별로 찾는다(결산월이 12월이 아닌 회사 때문에, docs/03 KIND 결산월).

출력
  data/interim/equity_hist.csv   code, yymm, scope(sep|con), item(total|parent), value_k
  data/interim/comp_basic.csv    code, name, wics, wi26, ksc, fye_mn, master_chk, list_dt
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ROOT, GatewayError, NotCached, call, rows  # noqa: E402

INTER = ROOT / "data" / "interim"
ITEMS = {"115000": "total", "115020": "parent"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="115000,115020")
    ap.add_argument("--codes", default="", help="쉼표 구분. 비우면 모집단 전체")
    ap.add_argument("--shard", default="", help="i/n — 종목을 n 조각으로 나눠 i 번째만 (병렬 시험용)")
    ap.add_argument("--merge", action="store_true", help="조각 결과(equity_hist_part*.csv)를 합치기만 한다")
    ap.add_argument("--cache-only", action="store_true", help="네트워크 없이 캐시된 회사만 (수집 중간 판정·웹페이지용)")
    args = ap.parse_args()
    if args.merge:
        import glob
        import pandas as pd
        for stem in ("equity_hist", "comp_basic"):
            parts = sorted(glob.glob(str(INTER / f"{stem}_part*.csv")))
            df = pd.concat([pd.read_csv(f, dtype=str) for f in parts]).drop_duplicates()
            df.to_csv(INTER / f"{stem}.csv", index=False, encoding="utf-8")
            print(stem, len(parts), "조각 →", len(df), "행")
        return

    snap = list(csv.DictReader(open(INTER / "universe_snap.csv", encoding="utf-8")))
    codes = sorted({s["code"] for s in snap}) if not args.codes else args.codes.split(",")
    if args.shard:
        i, n = map(int, args.shard.split("/"))
        codes = codes[i::n]
    items = args.items.split(",")
    print(f"{len(codes)}사 × (기본정보 + 계정 {items})")

    eq, basic, fail, pending = [], [], [], []
    for i, code in enumerate(codes, 1):
        try:
            off = args.cache_only
            b = rows(call("/etc/comp/comp_basic", offline=off, jcode=code))
            if b:
                x = b[0]
                basic.append({"code": code, "name": x.get("CMP_NM_KOR"), "wics": x.get("WICS"),
                              "wi26": x.get("WI26_CD"), "ksc": x.get("KSC_CD"), "fye_mn": x.get("FYE_MN"),
                              "master_chk": x.get("MASTER_CHK"), "list_dt": x.get("LIST_DT"),
                              "delist_dt": x.get("DELIST_DT")})
            for ic in items:
                for r in rows(call("/etc/ifrs/comp_ifrs_hist", offline=off, jcode=code, icode=ic)):
                    t = int(r.get("TERM_TYP") or 0)
                    if t in (1, 31) and r.get("VAL") is not None:      # 누적행만 (재무상태표는 누적=분기)
                        eq.append({"code": code, "yymm": r["YYMM"], "scope": "con" if t >= 30 else "sep",
                                   "item": ITEMS.get(ic, ic), "value_k": r["VAL"]})
        except NotCached:
            pending.append(code)
            basic = [x for x in basic if x["code"] != code]
            eq = [x for x in eq if x["code"] != code] if eq and eq[-1]["code"] == code else eq
        except GatewayError as e:
            fail.append((code, str(e)[:120]))
        if i % 200 == 0:
            print(f"  {i}/{len(codes)}  행 {len(eq)}  실패 {len(fail)}", flush=True)

    suffix = "_sample" if args.codes else (f"_part{args.shard.split('/')[0]}" if args.shard else "")
    with open(INTER / f"equity_hist{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "yymm", "scope", "item", "value_k"])
        w.writeheader()
        w.writerows(eq)
    with open(INTER / f"comp_basic{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(basic[0]))
        w.writeheader()
        w.writerows(basic)
    print(f"완료: 계정행 {len(eq)} · 기본정보 {len(basic)} · 실패 {len(fail)} · 미수집(캐시 없음) {len(pending)}")
    for c, e in fail[:20]:
        print("  실패", c, e)


if __name__ == "__main__":
    main()
