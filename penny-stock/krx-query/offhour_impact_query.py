# -*- coding: utf-8 -*-
"""
================================================================================
관리종목 지정(시총 미달·주가 미달) — 지정사유 발생일 시간외거래 조사
================================================================================

  Spyder 에서 이 파일을 열고 **F5** 만 누르면 됩니다.
  결과는 이 스크립트가 있는 폴더에 .txt 로 떨어집니다.

  ── 조사 내용 ────────────────────────────────────────────────────────────────
   [1] 지정사유 발생일(= 15:30 종가를 마지막으로 반영하는 날)의
       시간외거래 **15:40 ~ 공시 발표 시각**까지의
         · 거래대금 · 거래량 · 체결건수
         · 체결가격 목록 (체결 단위 전건 + 가격별 집계)
   [2] 같은 날 **하루 전체**의 거래대금 · 거래량 (보드별 분해 포함)
   [3] **지정 효력일(사유발생일의 다음 거래일) 이후 첫 거래일의 시가**,
       그리고 [1]의 체결가격 각각을 그 시가와 대비한 **수익률 목록**
       (수익률 = 첫 거래일 시가 / 체결가 - 1  → 시간외 매수자가 실제로 팔 수 있는
        첫 가격 기준 손익. 유가증권시장은 지정일 매매거래정지가 걸려 T+2 가 되기도 한다)

  ── 데이터 원천 (거래소 내부 Oracle) ─────────────────────────────────────────
   USSV.VWSV_SPOT_TRD3       현물 체결 통합뷰 (TRD_TM = HHMMSSXXX, BRD_ID = 보드)
   USMD.TBMD_BYDD_ISU_TRDPRC 일별 종목 거래·시세 (시가/종가/누적거래대금/시총)
   USMC.TBMC_BZ_DD           영업일 마스터 (CALND_ID='EXCH')

   보드ID: G1 정규장 · G3 장종료후종가(15:40~16:00) · G4 장종료후단일가(16:00~18:00)
           B3/K3/N3 장종료후 대량·바스켓·협의대량 (있으면 별도 표기)

  ── 대상 ────────────────────────────────────────────────────────────────────
   targets.py 의 TARGETS — KIND 공시 전수 76건 (2026-02-12 ~ 2026-08-13).
   목록을 다시 만들려면 build_targets.py 를 외부망에서 F5.
================================================================================
"""

import sys
import time
import traceback
import unicodedata
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from targets import TARGETS  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
#  ★ 설정 — 아래 값만 고치고 F5
# ═══════════════════════════════════════════════════════════════════════════════

# ── DB 접속 ───────────────────────────────────────────────────────────────────
#   (1) 같은 폴더에 credentials_local.py 를 만들어 세 줄만 넣는 방법(권장, git 제외)
#         DB_USER = "실제계정" / DB_PASSWORD = "실제비밀번호" / DB_DSN = "DBMMXP"
#   (2) 또는 아래 "CHANGE_ME" 를 직접 교체. ⚠ 교체 후 commit 금지.
DB_USER     = "CHANGE_ME"
DB_PASSWORD = "CHANGE_ME"
DB_DSN      = "DBMMXP"          # TNS alias 또는 host:port/service

# ── 조사 구간 ─────────────────────────────────────────────────────────────────
OFFHR_START_TM   = "154000000"  # 시간외 시작 15:40:00.000 (HHMMSSXXX)
INCLUDE_END_MIN  = False        # False(기본) 공시시각 '직전'까지 (18:35 → 18:34:59.999)
                                # True       공시 '분' 을 통째로 포함 (18:35:59.999 까지)
LOOKAHEAD_BZ_DAYS = 10          # 사유발생일 다음 영업일부터 몇 일을 훑어 '첫 거래일' 을 찾을지.
                                # 유가증권시장은 관리종목 신규지정일에 매매거래를 정지해
                                # 지정일 시가가 없다 → 재개 첫날 시가로 수익률을 낸다.

# ── 출력 ─────────────────────────────────────────────────────────────────────
MAX_TICK_LINES   = 0            # 리포트에 찍을 체결 최대 줄수. 0 = 제한 없음
WRITE_TICK_FILE  = True         # 체결 단위 전건을 별도 탭구분 .txt 로도 저장
OUT_ENCODING     = "utf-8-sig"  # 메모장·엑셀에서 한글 안 깨지게

# ── 대상 필터 (테스트용) ──────────────────────────────────────────────────────
ONLY_CODES       = None         # 예: ["005320", "001420"] / None 이면 전건
LIMIT            = None         # 예: 3 / None 이면 전건

# ── DB 객체 (환경 다르면 여기만 수정) ─────────────────────────────────────────
TBL_TRADE = "USSV.VWSV_SPOT_TRD3"
TBL_BYDD  = "USMD.TBMD_BYDD_ISU_TRDPRC"
TBL_BZ_DD = "USMC.TBMC_BZ_DD"
# ═══════════════════════════════════════════════════════════════════════════════


# credentials_local.py 가 있으면 위 접속정보를 덮어씀
try:
    from credentials_local import (  # type: ignore # noqa: E402
        DB_USER as _CL_USER,
        DB_PASSWORD as _CL_PASSWORD,
        DB_DSN as _CL_DSN,
    )
    DB_USER, DB_PASSWORD, DB_DSN = _CL_USER, _CL_PASSWORD, _CL_DSN
except ImportError:
    pass


BOARD_NM = {
    "G1": "정규장",
    "G2": "장개시전종가",
    "G3": "장종료후종가",
    "G4": "장종료후단일가",
    "B1": "장중대량", "B2": "장개시전대량", "B3": "장종료후대량",
    "K1": "장중대량바스켓", "K2": "장개시전대량바스켓", "K3": "장종료후대량바스켓",
    "N1": "장중협의대량", "N2": "장개시전협의대량", "N3": "장종료후협의대량",
    "I1": "장중경쟁대량", "I2": "장개시전경쟁대량",
    "G5": "장개시전경매매", "G6": "경매매",
}
OFFHR_MAIN_BOARDS  = ("G3", "G4")        # 시간외 일반매매 (핵심 집계)
OFFHR_BLOCK_BOARDS = ("B3", "K3", "N3")  # 장종료후 대량·바스켓·협의


# ═══════════════════════════════════════════════════════════════════════════════
#  SQL
# ═══════════════════════════════════════════════════════════════════════════════

# [1] 시간외 체결 — 15:40 ~ 공시 발표 시각
SQL_OFFHR_TICKS = f"""
SELECT TRD_TM, TRD_NO, BRD_ID, SESS_ID, TRD_TP_CD, REGUL_OFFHR_TP_CD,
       TRD_PRC, TRDVOL
  FROM {TBL_TRADE}
 WHERE TRD_DD  = :dd
   AND ISU_CD  = :isu
   AND TRD_TM >= :tm_from
   AND TRD_TM <  :tm_to
 ORDER BY TRD_TM, TRD_NO
"""

# [2] 당일 전체 — 보드별 집계 (정규장/시간외 분해)
SQL_DAY_BY_BOARD = f"""
SELECT BRD_ID,
       COUNT(*)              AS TRD_CNT,
       SUM(TRDVOL)           AS TRDVOL,
       SUM(TRD_PRC * TRDVOL) AS TRDVAL,
       MIN(TRD_TM)           AS FST_TM,
       MAX(TRD_TM)           AS LST_TM
  FROM {TBL_TRADE}
 WHERE TRD_DD = :dd
   AND ISU_CD = :isu
 GROUP BY BRD_ID
 ORDER BY BRD_ID
"""

# [2]/[3] 일별 시세 — 당일(전체 거래대금·거래량) / 익일(시가)
SQL_BYDD = f"""
SELECT TRD_DD, AGG_BAS_TP_CD, MKT_ID,
       TDD_OPNPRC, TDD_HGPRC, TDD_LWPRC, TDD_CLSPRC, PREVDD_CLSPRC,
       ACC_TRDCNT, ACC_TRDVOL, ACC_TRDVAL, MKTCAP, LST_AGG_TM
  FROM {TBL_BYDD}
 WHERE ISU_CD = :isu
   AND TRD_DD = :dd
 ORDER BY DECODE(AGG_BAS_TP_CD, '0', 1, '9', 2, 3)
"""

# [3] 사유발생일 다음 영업일부터 N일 (첫날 = 관리종목 지정 효력일)
#     유가증권시장은 관리종목 신규지정일에 매매거래를 정지하므로 그날 시가가 없다.
#     → 실제로 거래가 이뤄진 첫 날까지 훑어야 시간외 매수자의 청산가격이 나온다.
SQL_NEXT_BZ_DDS = f"""
SELECT BZ_DD
  FROM (SELECT BZ_DD
          FROM {TBL_BZ_DD}
         WHERE CALND_ID = 'EXCH'
           AND BZ_DD    > :dd
         ORDER BY BZ_DD)
 WHERE ROWNUM <= :n
"""

# [3] 사유발생일 이후 구간의 일별 시세 (거래정지 여부 판별 + 첫 거래일 시가)
SQL_BYDD_RANGE = f"""
SELECT TRD_DD, AGG_BAS_TP_CD, MKT_ID,
       TDD_OPNPRC, TDD_HGPRC, TDD_LWPRC, TDD_CLSPRC, PREVDD_CLSPRC,
       ACC_TRDCNT, ACC_TRDVOL, ACC_TRDVAL, MKTCAP, LST_AGG_TM
  FROM {TBL_BYDD}
 WHERE ISU_CD  = :isu
   AND TRD_DD  > :dd
   AND TRD_DD <= :dd_end
 ORDER BY TRD_DD, DECODE(AGG_BAS_TP_CD, '0', 1, '9', 2, 3)
"""

# [3] 시가 폴백 — 일별 테이블에 시가가 없으면 정규장 첫 체결가
SQL_FIRST_REGUL_TRD = f"""
SELECT TRD_PRC, TRD_TM
  FROM (SELECT TRD_PRC, TRD_TM
          FROM {TBL_TRADE}
         WHERE TRD_DD = :dd
           AND ISU_CD = :isu
           AND BRD_ID = 'G1'
         ORDER BY TRD_TM, TRD_NO)
 WHERE ROWNUM = 1
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  유틸
# ═══════════════════════════════════════════════════════════════════════════════

def connect():
    """cx_Oracle 우선, 없으면 oracledb 로 접속."""
    try:
        import cx_Oracle as co
        return co.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN,
                          encoding="UTF-8"), "cx_Oracle"
    except ImportError:
        import oracledb as od
        try:
            od.init_oracle_client()      # thick 모드 (Oracle Client 있으면)
        except Exception:
            pass
        return od.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN), "oracledb"


def q(cur, sql, **params):
    """SELECT 실행 → [dict, ...]"""
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def num(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def dwidth(s):
    """한글(전각) 을 2칸으로 세는 표시폭."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def L(s, n):
    """표시폭 기준 좌측정렬. 긴 값은 잘라내되 칸 사이 공백 1칸은 항상 남긴다."""
    s = str(s)
    lim = max(1, n - 1)
    while dwidth(s) > lim and s:
        s = s[:-1]
    return s + " " * max(0, n - dwidth(s))


def R(s, n):
    """표시폭 기준 우측정렬."""
    s = str(s)
    return " " * max(0, n - dwidth(s)) + s


def fmt_tm(tm):
    """'183512345' → '18:35:12.345'"""
    if not tm:
        return "-"
    tm = str(tm).ljust(9, "0")
    return f"{tm[0:2]}:{tm[2:4]}:{tm[4:6]}.{tm[6:9]}"


def fmt_dd(dd):
    return f"{dd[0:4]}-{dd[4:6]}-{dd[6:8]}" if dd and len(str(dd)) == 8 else str(dd or "-")


def i(v):
    """정수 콤마 포맷"""
    return "-" if v is None else f"{int(round(float(v))):,}"


def p(v):
    """가격 포맷 (소수 있으면 살림)"""
    if v is None:
        return "-"
    f = float(v)
    return f"{int(f):,}" if abs(f - int(f)) < 1e-9 else f"{f:,.3f}"


def pct(v, nd=2):
    return "-" if v is None else f"{v:+.{nd}f}%"


def bnm(brd):
    return f"{brd} {BOARD_NM.get(brd, '')}".strip()


def end_bound(tm4):
    """공시시각 'HHMM' → 조사구간 상한(HHMMSSXXX, 미만 비교용)."""
    tm4 = str(tm4).ljust(4, "0")
    # 배타(기본): 18:35 → '183500000' 미만 = 18:34:59.999 까지
    # 포함        : 18:35 → '183560000' 미만 = 18:35:59.999 까지
    return tm4 + ("60000" if INCLUDE_END_MIN else "00000")


# ═══════════════════════════════════════════════════════════════════════════════
#  종목 1건 조사
# ═══════════════════════════════════════════════════════════════════════════════

def probe_one(cur, t):
    """한 (종목, 지정사유 발생일) 조사 → 결과 dict"""
    dd, isu, tm = t["dd"], t["isu"], t["tm"]
    tm_to = end_bound(tm)

    out = dict(t)
    out["window"] = (OFFHR_START_TM, tm_to)

    # ── [1] 시간외 체결 (15:40 ~ 공시시각) ────────────────────────────────────
    ticks = q(cur, SQL_OFFHR_TICKS, dd=dd, isu=isu,
              tm_from=OFFHR_START_TM, tm_to=tm_to)
    for x in ticks:
        x["PRC"] = num(x["TRD_PRC"], 0.0)
        x["VOL"] = num(x["TRDVOL"], 0.0)
        x["VAL"] = x["PRC"] * x["VOL"]
    out["ticks"] = ticks

    def agg(rows):
        return dict(cnt=len(rows),
                    vol=sum(x["VOL"] for x in rows),
                    val=sum(x["VAL"] for x in rows))

    out["offhr_all"]   = agg(ticks)
    out["offhr_main"]  = agg([x for x in ticks if x["BRD_ID"] in OFFHR_MAIN_BOARDS])
    out["offhr_block"] = agg([x for x in ticks if x["BRD_ID"] in OFFHR_BLOCK_BOARDS])

    by_board = OrderedDict()
    for x in ticks:
        b = by_board.setdefault(x["BRD_ID"], dict(cnt=0, vol=0.0, val=0.0))
        b["cnt"] += 1
        b["vol"] += x["VOL"]
        b["val"] += x["VAL"]
    out["offhr_by_board"] = OrderedDict(sorted(by_board.items()))

    by_prc = OrderedDict()
    for x in sorted(ticks, key=lambda z: z["PRC"]):
        b = by_prc.setdefault(x["PRC"], dict(cnt=0, vol=0.0, val=0.0))
        b["cnt"] += 1
        b["vol"] += x["VOL"]
        b["val"] += x["VAL"]
    out["offhr_by_prc"] = by_prc

    # ── [2] 당일 전체 ────────────────────────────────────────────────────────
    out["day_board"] = q(cur, SQL_DAY_BY_BOARD, dd=dd, isu=isu)
    bydd = q(cur, SQL_BYDD, dd=dd, isu=isu)
    out["bydd"] = bydd[0] if bydd else None

    # ── [3] 지정 효력일 이후 — 첫 '거래된' 날의 시가 ─────────────────────────
    #     유가증권시장은 관리종목 신규지정일 하루를 매매거래정지한다. 그 경우
    #     지정일에는 시가가 없고, 시간외 매수자가 실제로 팔 수 있는 첫 가격은
    #     거래재개일 시가다. 코스닥은 정지하지 않아 대개 지정일 = 첫 거래일.
    cur.execute(SQL_NEXT_BZ_DDS, dict(dd=dd, n=LOOKAHEAD_BZ_DAYS))
    bzds = [r0[0] for r0 in cur.fetchall()]
    out["next_bz_days"] = bzds
    out["next_dd"] = bzds[0] if bzds else None          # 지정 효력일

    rows = q(cur, SQL_BYDD_RANGE, isu=isu, dd=dd, dd_end=bzds[-1]) if bzds else []
    bydd_by_dd = OrderedDict()
    for r0 in rows:                                     # DECODE 정렬로 '0' 이 먼저
        bydd_by_dd.setdefault(r0["TRD_DD"], r0)
    out["after_days"] = [
        dict(dd=d,
             row=bydd_by_dd.get(d),
             vol=num((bydd_by_dd.get(d) or {}).get("ACC_TRDVOL"), 0.0) or 0.0,
             opn=num((bydd_by_dd.get(d) or {}).get("TDD_OPNPRC")))
        for d in bzds
    ]
    out["next_bydd"] = out["after_days"][0]["row"] if out["after_days"] else None

    out["open_dd"] = out["open_price"] = out["open_src"] = None
    out["halt_days"] = 0                                # 지정 효력일부터 거래 없던 영업일 수
    for k, d0 in enumerate(out["after_days"]):
        if d0["vol"] <= 0:
            continue
        op0, src0 = d0["opn"], "TBMD_BYDD_ISU_TRDPRC.TDD_OPNPRC (당일시가)"
        if not op0:                                     # 시가 결측이면 정규장 첫 체결로 폴백
            ft = q(cur, SQL_FIRST_REGUL_TRD, dd=d0["dd"], isu=isu)
            if ft:
                op0, src0 = num(ft[0]["TRD_PRC"]), f"정규장 첫 체결 {fmt_tm(ft[0]['TRD_TM'])}"
        if op0:
            out["open_dd"], out["open_price"], out["open_src"] = d0["dd"], op0, src0
            out["halt_days"] = k
            break

    # ── 수익률 ───────────────────────────────────────────────────────────────
    op = out["open_price"]
    for x in ticks:
        x["RET"] = (op / x["PRC"] - 1.0) * 100.0 if (op and x["PRC"]) else None
    for k, b in by_prc.items():
        b["ret"] = (op / k - 1.0) * 100.0 if (op and k) else None

    a, m = out["offhr_all"], out["offhr_main"]
    out["offhr_vwap"] = (a["val"] / a["vol"]) if a["vol"] else None
    out["offhr_main_vwap"] = (m["val"] / m["vol"]) if m["vol"] else None
    out["offhr_vwap_ret"] = ((op / out["offhr_vwap"] - 1) * 100
                             if (op and out["offhr_vwap"]) else None)
    out["offhr_main_vwap_ret"] = ((op / out["offhr_main_vwap"] - 1) * 100
                                  if (op and out["offhr_main_vwap"]) else None)
    out["offhr_pnl"] = (sum(x["VOL"] * (op - x["PRC"]) for x in ticks) if op else None)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  리포트 렌더링
# ═══════════════════════════════════════════════════════════════════════════════

def render_one(o, idx, total):
    out = []
    add = out.append
    add("=" * 104)
    add(f"[{idx}/{total}] {o['nm']} ({o['srt']} / {o['isu']})   {o['mkt']}")
    add(f"         사유  {o['rsn']} · {o['typ']}")
    add(f"         지정사유 발생일(종가 확정일) {fmt_dd(o['dd'])}"
        f"   ·   공시 발표 {o['tm'][:2]}:{o['tm'][2:]}"
        f"   ·   지정 효력일 {fmt_dd(o['next_dd'])}")
    add("=" * 104)

    # ── [1] ─────────────────────────────────────────────────────────────────
    st, en = o["window"]
    a, m, bk = o["offhr_all"], o["offhr_main"], o["offhr_block"]
    add("")
    add(f"[1] 시간외거래  {fmt_tm(st)} ~ {fmt_tm(en)} 미만"
        f"   (15:30 종가 확정 이후 ~ 공시 발표 {'분 포함' if INCLUDE_END_MIN else '직전'})")
    add(f"    ┌ 시간외 일반매매 (G3 장종료후종가 15:40~16:00 + G4 장종료후단일가 16:00~18:00)")
    add(f"    │    거래량        {R(i(m['vol']), 20)} 주")
    add(f"    │    거래대금      {R(i(m['val']), 20)} 원")
    add(f"    │    체결건수      {R(i(m['cnt']), 20)} 건")
    add(f"    │    평균단가VWAP  {R(p(o['offhr_main_vwap']), 20)} 원")
    if bk["cnt"]:
        add(f"    ├ 장종료후 대량·바스켓·협의   거래량 {i(bk['vol'])} 주"
            f" / 거래대금 {i(bk['val'])} 원 / {i(bk['cnt'])} 건")
    add(f"    └ 구간 합계(전 보드)  거래량 {i(a['vol'])} 주 / 거래대금 {i(a['val'])} 원"
        f" / {i(a['cnt'])} 건 / VWAP {p(o['offhr_vwap'])} 원")

    if o["offhr_by_board"]:
        add("")
        add("    · 보드별 분해")
        add("      " + L("보드", 24) + R("체결건수", 12) + R("거래량", 18) + R("거래대금", 22))
        for b, v in o["offhr_by_board"].items():
            add("      " + L(bnm(b), 24) + R(i(v["cnt"]), 12) + R(i(v["vol"]), 18) + R(i(v["val"]), 22))

    add("")
    add(f"    · 체결가격 목록 — 체결 단위 전건 ({i(a['cnt'])} 건)")
    if not o["ticks"]:
        add("      (해당 구간 체결 없음)")
    else:
        add("      " + L("체결시각", 16) + L("보드", 8) + R("체결가", 14)
            + R("체결수량", 16) + R("체결대금", 20))
        rows = o["ticks"] if not MAX_TICK_LINES else o["ticks"][:MAX_TICK_LINES]
        for x in rows:
            add("      " + L(fmt_tm(x["TRD_TM"]), 16) + L(x["BRD_ID"], 8)
                + R(p(x["PRC"]), 14) + R(i(x["VOL"]), 16) + R(i(x["VAL"]), 20))
        if len(rows) < len(o["ticks"]):
            add(f"      ... 이하 {len(o['ticks']) - len(rows)}건 생략 (MAX_TICK_LINES 조정)")

    # ── [2] ─────────────────────────────────────────────────────────────────
    add("")
    add(f"[2] {fmt_dd(o['dd'])} 하루 전체 거래")
    b = o["bydd"]
    if b:
        add(f"    · 일별 집계 (TBMD_BYDD_ISU_TRDPRC, AGG_BAS_TP_CD={b.get('AGG_BAS_TP_CD')})")
        add(f"        시가 {p(b.get('TDD_OPNPRC'))} / 고가 {p(b.get('TDD_HGPRC'))}"
            f" / 저가 {p(b.get('TDD_LWPRC'))} / 종가 {p(b.get('TDD_CLSPRC'))}"
            f"   (전일종가 {p(b.get('PREVDD_CLSPRC'))})")
        add(f"        거래량        {R(i(b.get('ACC_TRDVOL')), 20)} 주")
        add(f"        거래대금      {R(i(b.get('ACC_TRDVAL')), 20)} 원")
        add(f"        체결건수      {R(i(b.get('ACC_TRDCNT')), 20)} 건")
        add(f"        시가총액      {R(i(b.get('MKTCAP')), 20)} 원"
            + (f"   (최종집계 {fmt_tm(b.get('LST_AGG_TM'))})"
               if str(b.get("LST_AGG_TM") or "").isdigit() else ""))
    else:
        add("    · 일별 집계 테이블에 행 없음")

    tot_vol = tot_val = 0.0
    if o["day_board"]:
        add("")
        add("    · 체결 원장 보드별 분해 (VWSV_SPOT_TRD3)")
        add("      " + L("보드", 24) + R("체결건수", 12) + R("거래량", 18)
            + R("거래대금", 22) + "   " + L("최초", 15) + L("최종", 15))
        for row in o["day_board"]:
            v, val = num(row["TRDVOL"], 0.0), num(row["TRDVAL"], 0.0)
            tot_vol += v
            tot_val += val
            add("      " + L(bnm(row["BRD_ID"]), 24) + R(i(row["TRD_CNT"]), 12)
                + R(i(v), 18) + R(i(val), 22) + "   "
                + L(fmt_tm(row["FST_TM"]), 15) + L(fmt_tm(row["LST_TM"]), 15))
        add("      " + L("합계", 24) + R("", 12) + R(i(tot_vol), 18) + R(i(tot_val), 22))

    if tot_val:
        add("")
        add(f"    · 시간외(15:40~공시) 비중 —  거래량 {a['vol'] / tot_vol * 100:.2f}%"
            f" / 거래대금 {a['val'] / tot_val * 100:.2f}%   (당일 전체 대비)")

    # ── [3] ─────────────────────────────────────────────────────────────────
    add("")
    add(f"[3] 지정 효력일 {fmt_dd(o['next_dd'])} 이후 첫 거래일 시가 대비 수익률")
    if o["after_days"]:
        add("    · 지정 효력일 이후 거래 상황")
        add("      " + L("영업일", 13) + L("구분", 30) + R("시가", 12) + R("종가", 12)
            + R("거래량", 16) + R("거래대금", 20))
        show = max(5, o["halt_days"] + 2)
        for k, d0 in enumerate(o["after_days"][:show]):
            row0 = d0["row"] or {}
            tag = []
            if k == 0:
                tag.append("지정 효력일")
            if d0["row"] is None:
                tag.append("자료없음")
            elif d0["vol"] <= 0:
                tag.append("매매거래정지")
            if d0["dd"] == o["open_dd"]:
                tag.append("★첫 거래일")
            add("      " + L(fmt_dd(d0["dd"]), 13) + L(" · ".join(tag), 30)
                + R(p(row0.get("TDD_OPNPRC")), 12) + R(p(row0.get("TDD_CLSPRC")), 12)
                + R(i(row0.get("ACC_TRDVOL")), 16) + R(i(row0.get("ACC_TRDVAL")), 20))
    if o["open_price"] is None:
        add(f"    · 이후 {len(o['after_days'])}영업일 안에 거래된 날이 없어 시가를 찾지 못함"
            f" (장기 거래정지 등 — LOOKAHEAD_BZ_DAYS 를 늘려 볼 것)")
    else:
        nb = (o["after_days"][o["halt_days"]]["row"] if o["after_days"] else None) or {}
        if o["halt_days"]:
            add(f"    · ⚠ 지정 효력일 {fmt_dd(o['next_dd'])} 은 거래 없음(매매거래정지)."
                f" {o['halt_days']}영업일 뒤 {fmt_dd(o['open_dd'])} 이 첫 거래일"
                f"  →  수익률 기준일은 T+{o['halt_days'] + 1}")
        add(f"    · 기준 시가 {p(o['open_price'])} 원  ({fmt_dd(o['open_dd'])})"
            f"   [{o['open_src']}]")
        if nb:
            add(f"      (그날 고가 {p(nb.get('TDD_HGPRC'))} / 저가 {p(nb.get('TDD_LWPRC'))}"
                f" / 종가 {p(nb.get('TDD_CLSPRC'))} / 거래량 {i(nb.get('ACC_TRDVOL'))})")
        cls = num((o["bydd"] or {}).get("TDD_CLSPRC"))
        if cls:
            add(f"      사유발생일 종가 {p(cls)} → 기준 시가 {p(o['open_price'])} :"
                f" {pct((o['open_price'] / cls - 1) * 100)}")
        add(f"    · 시간외 평균단가 대비   일반매매 VWAP {p(o['offhr_main_vwap'])}"
            f" → {pct(o['offhr_main_vwap_ret'])}"
            f"   /   전 보드 VWAP {p(o['offhr_vwap'])} → {pct(o['offhr_vwap_ret'])}")

        if o["offhr_by_prc"]:
            add("")
            add("    · 체결가격별 수익률 목록   (수익률 = 첫 거래일 시가 / 체결가 - 1)")
            add("      " + R("체결가", 14) + R("체결건수", 12) + R("체결수량", 16)
                + R("체결대금", 20) + R("수익률", 14))
            for k, v in o["offhr_by_prc"].items():
                add("      " + R(p(k), 14) + R(i(v["cnt"]), 12) + R(i(v["vol"]), 16)
                    + R(i(v["val"]), 20) + R(pct(v["ret"]), 14))
            loss_val = sum(v["val"] for v in o["offhr_by_prc"].values() if (v["ret"] or 0) < 0)
            add(f"      → 시간외 매수 전량을 첫 거래일 시가에 청산 시 평가손익 {i(o['offhr_pnl'])} 원"
                f"   (손실 구간 체결대금 {i(loss_val)} 원)")

        if o["ticks"]:
            add("")
            add(f"    · 체결 단위 수익률 목록 ({i(len(o['ticks']))} 건)")
            add("      " + L("체결시각", 16) + L("보드", 8) + R("체결가", 14)
                + R("체결수량", 16) + R("수익률", 14))
            rows = o["ticks"] if not MAX_TICK_LINES else o["ticks"][:MAX_TICK_LINES]
            for x in rows:
                add("      " + L(fmt_tm(x["TRD_TM"]), 16) + L(x["BRD_ID"], 8)
                    + R(p(x["PRC"]), 14) + R(i(x["VOL"]), 16) + R(pct(x["RET"]), 14))
            if len(rows) < len(o["ticks"]):
                add(f"      ... 이하 {len(o['ticks']) - len(rows)}건 생략")
    add("")
    return "\n".join(out)


def render_summary(results):
    out = []
    add = out.append
    add("=" * 104)
    add("전체 요약")
    add("=" * 104)
    add("")
    add(L("사유발생일", 13) + L("공시", 7) + L("시장", 10) + L("종목명", 18) + L("단축", 8)
        + L("사유", 19) + R("시간외거래대금", 18) + R("시간외거래량", 15)
        + R("당일거래대금", 20) + R("비중%", 9) + R("기준일", 8) + R("기준시가", 11)
        + R("VWAP수익률", 13))
    tot_off_val = tot_off_vol = tot_day_val = tot_pnl = 0.0
    for o in results:
        a = o["offhr_all"]
        day_val = num((o["bydd"] or {}).get("ACC_TRDVAL"), 0.0) or \
            sum(num(x["TRDVAL"], 0.0) for x in o["day_board"])
        share = (a["val"] / day_val * 100) if day_val else None
        tot_off_val += a["val"]
        tot_off_vol += a["vol"]
        tot_day_val += day_val
        tot_pnl += (o["offhr_pnl"] or 0.0)
        add(L(fmt_dd(o["dd"]), 13) + L(f"{o['tm'][:2]}:{o['tm'][2:]}", 7) + L(o["mkt"], 10)
            + L(o["nm"], 18) + L(o["srt"], 8) + L(o["rsn"], 19)
            + R(i(a["val"]), 18) + R(i(a["vol"]), 15) + R(i(day_val), 20)
            + R(f"{share:.2f}" if share is not None else "-", 9)
            + R(f"T+{o['halt_days'] + 1}" if o["open_price"] else "-", 8)
            + R(p(o["open_price"]), 11) + R(pct(o["offhr_vwap_ret"]), 13))
    add("")
    add(f"  대상 {len(results)}건 (공시 건수 기준)")
    add(f"  시간외(15:40~공시) 총 거래대금 {i(tot_off_val)} 원 · 총 거래량 {i(tot_off_vol)} 주")
    add(f"  당일 총 거래대금 {i(tot_day_val)} 원 · 시간외 비중"
        f" {(tot_off_val / tot_day_val * 100) if tot_day_val else 0:.2f}%")
    add(f"  첫 거래일 시가 청산 가정 총 평가손익 {i(tot_pnl)} 원")

    # 같은 (종목, 사유발생일) 에 공시가 2건 이상이면(사유추가 등) 위 합계에 같은 체결이
    # 두 번 들어간다. 공시시각이 가장 늦은 = 구간이 가장 넓은 한 건만 남겨 중복을 뺀다.
    uniq = OrderedDict()
    for o in results:
        k = (o["dd"], o["srt"])
        if k not in uniq or o["tm"] > uniq[k]["tm"]:
            uniq[k] = o
    if len(uniq) != len(results):
        u_val = sum(o["offhr_all"]["val"] for o in uniq.values())
        u_vol = sum(o["offhr_all"]["vol"] for o in uniq.values())
        u_pnl = sum(o["offhr_pnl"] or 0.0 for o in uniq.values())
        add("")
        add(f"  ※ 공시 {len(results)}건 중 같은 (종목, 사유발생일) 재공시가 있어 위 합계엔"
            f" 중복이 섞여 있다. 고유 {len(uniq)}건 기준:")
        add(f"     시간외 총 거래대금 {i(u_val)} 원 · 총 거래량 {i(u_vol)} 주"
            f" · 총 평가손익 {i(u_pnl)} 원")

    for key, label in (("mkt", "시장별"), ("rsn", "사유별")):
        add("")
        add(f"  [{label}]")
        g = OrderedDict()
        for o in results:
            b = g.setdefault(o[key], dict(n=0, vol=0.0, val=0.0, pnl=0.0, pnl_n=0))
            b["n"] += 1
            b["vol"] += o["offhr_all"]["vol"]
            b["val"] += o["offhr_all"]["val"]
            if o["offhr_pnl"] is not None:
                b["pnl"] += o["offhr_pnl"]
                b["pnl_n"] += 1
        for k, v in sorted(g.items()):
            add("    " + L(k, 20) + R(f"{v['n']}건", 8)
                + "   거래량 " + R(i(v["vol"]), 15) + " 주"
                + "   거래대금 " + R(i(v["val"]), 18) + " 원"
                + "   첫거래일시가 청산 평가손익 " + R(i(v["pnl"]), 18) + f" 원 ({v['pnl_n']}건 산출)")
    add("")
    return "\n".join(out)


def render_tickfile(results):
    out = ["\t".join([
        "사유발생일", "공시시각", "시장", "단축코드", "표준코드", "종목명", "사유", "유형",
        "체결시각", "보드ID", "보드명", "세션ID", "체결유형코드", "정규시간외구분코드",
        "체결가", "체결수량", "체결대금", "지정효력일", "정지영업일수", "기준거래일", "기준시가", "수익률(%)",
    ])]
    for o in results:
        for x in o["ticks"]:
            out.append("\t".join([
                o["dd"], o["tm"], o["mkt"], o["srt"], o["isu"], o["nm"], o["rsn"], o["typ"],
                str(x["TRD_TM"]), str(x["BRD_ID"]), BOARD_NM.get(x["BRD_ID"], ""),
                str(x.get("SESS_ID") or ""), str(x.get("TRD_TP_CD") or ""),
                str(x.get("REGUL_OFFHR_TP_CD") or ""),
                f"{x['PRC']:g}", f"{x['VOL']:.0f}", f"{x['VAL']:.0f}",
                str(o["next_dd"] or ""), str(o["halt_days"]),
                str(o["open_dd"] or ""),
                (f"{o['open_price']:g}" if o["open_price"] else ""),
                (f"{x['RET']:.4f}" if x["RET"] is not None else ""),
            ]))
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════════
#  실행 — F5
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    tgts = list(TARGETS)
    if ONLY_CODES:
        tgts = [t for t in tgts if t["srt"] in set(ONLY_CODES)]
    if LIMIT:
        tgts = tgts[:LIMIT]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = HERE / f"offhour_impact_{stamp}.txt"
    tick_path = HERE / f"offhour_impact_{stamp}_ticks.txt"

    print(f"대상 {len(tgts)}건 · DSN={DB_DSN}")
    print(f"출력 폴더 {HERE}")
    if DB_USER == "CHANGE_ME":
        print("\n⛔ DB 접속정보가 비어 있습니다.")
        print("   스크립트 상단 DB_USER/DB_PASSWORD/DB_DSN 을 채우거나,")
        print("   같은 폴더에 credentials_local.py (DB_USER/DB_PASSWORD/DB_DSN 세 줄) 를 만들어 주세요.")
        return None

    conn, drv = connect()
    print(f"✅ Connected to {DB_DSN} via {drv}")
    cur = conn.cursor()

    results, errors = [], []
    t0 = time.time()
    for n, t in enumerate(tgts, 1):
        try:
            o = probe_one(cur, t)
            results.append(o)
            print(f"  [{n}/{len(tgts)}] {t['dd']} {t['nm']:<12} "
                  f"시간외 {i(o['offhr_all']['val']):>14}원 / {o['offhr_all']['cnt']}건")
        except Exception as e:
            errors.append((t, traceback.format_exc()))
            print(f"  [{n}/{len(tgts)}] {t['dd']} {t['nm']:<12} ❌ {e}")
    cur.close()
    conn.close()

    head = [
        "=" * 104,
        "관리종목 지정(시가총액 미달 · 주가 미달(동전주)) — 지정사유 발생일 시간외거래 조사",
        "=" * 104,
        f"  실행시각    : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"  접속        : {DB_USER} @ {DB_DSN}  ({drv})",
        f"  대상        : {len(results)}건 (요청 {len(tgts)}건, 실패 {len(errors)}건)",
        f"  조사구간    : 각 종목 지정사유 발생일의 {fmt_tm(OFFHR_START_TM)} ~ 공시 발표 시각"
        f"{' (공시 분 포함)' if INCLUDE_END_MIN else ' (공시 분 직전까지)'}",
        f"  체결 원장   : {TBL_TRADE}",
        f"  일별 시세   : {TBL_BYDD}",
        f"  영업일 달력 : {TBL_BZ_DD}  (CALND_ID='EXCH')",
        "",
        "  ※ 정규장 종료(종가 확정) 15:30 → 시간외종가매매 15:40~16:00 (보드 G3) →",
        "     시간외단일가매매 16:00~18:00 (보드 G4). 공시가 그 뒤에 나가면, 그 사이의 체결은",
        "     '관리종목 지정 사실이 공표되지 않은 상태에서 이뤄진 거래' 다.",
        "  ※ 수익률 = 첫 거래일 시가 / 체결가 - 1   (시간외 매수 → 그 시가에 청산 가정).",
        "     유가증권시장은 관리종목 신규지정일 하루를 매매거래정지하므로 지정일 시가가 없다.",
        "     그 경우 거래재개 첫날 시가를 기준으로 삼고, 요약표 '기준일' 에 T+2 처럼 표시한다.",
        "  ※ 거래대금은 체결 원장에서 SUM(체결가 × 체결수량) 으로 산출.",
        "",
    ]

    body = [render_summary(results)] + [
        render_one(o, n, len(results)) for n, o in enumerate(results, 1)
    ]
    if errors:
        body += ["=" * 104, "실패 목록", "=" * 104]
        for t, tb in errors:
            body.append(f"- {t['nm']} {t['dd']}\n{tb}")

    text = "\n".join(head + body)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    out_path.write_text(text, encoding=OUT_ENCODING)
    print(f"\n✅ 리포트  : {out_path}")
    if WRITE_TICK_FILE:
        tick_path.write_text(render_tickfile(results), encoding=OUT_ENCODING)
        print(f"✅ 체결원자료: {tick_path}")
    print(f"소요 {time.time() - t0:.1f}초")
    return results


if __name__ == "__main__":
    RESULTS = main()
