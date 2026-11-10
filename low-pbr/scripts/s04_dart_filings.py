"""s04 정기보고서 목록 → MySQL dart_periodic.pr_filing  (+ 기존 수집분 이관)

규약은 ipo_registration/commitment_followup/scripts/s03_collect_filings.py 와 같다 (docs/02-데이터저장.md).
  · list.json 직접 호출, pblntf_ty='A'(정기공시), last_reprt_at='N'(정정본·원본 모두)
  · doc_class 는 접두어를 뗀 보고서명에 앵커 정규식 (부분 일치 금지)
  · is_body_version 은 (회사, 종류, 기준일) 안 최신 접수로 잠정 — s07 이 원문 절 제목 수로 확정

단계
  1) corpCode.xml → pr_corp
  2) ipo_db.cf_filing / cf_filing_xml → pr_filing / pr_filing_xml  (origin='ipo_db.cf_filing', 다시 받지 않음)
  3) 모집단 회사마다 list.json (2020-01-01 ~ 2026-10-22 접수)

종목코드 → corp_code: corpCode.xml 은 상장폐지 회사의 stock_code 가 비어 있다.
그런 회사는 회사명(공백·(주) 제거)으로 맞추고, 못 맞춘 것은 logs/s04_unmatched.csv 로 남긴다.

사용법
    python scripts/s04_dart_filings.py            # 전체 (재실행 시 수집 끝난 회사는 건너뜀)
    python scripts/s04_dart_filings.py --limit 5  # 파일럿
"""
import argparse
import calendar
import csv
import io
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _db import dart_keys, get_conn  # noqa: E402
from _gw import ROOT  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
CORP_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
BGN, END = "20200101", "20261022"
DELAY = 0.35

DOC_CLASS = [(re.compile(r"^사업보고서\s*(\(|$)"), "annual"),
             (re.compile(r"^반기보고서\s*(\(|$)"), "semi"),
             (re.compile(r"^분기보고서\s*(\(|$)"), "quarter")]
REV_KIND = {"기재정정": "content", "첨부추가": "attach", "첨부정정": "attach"}
_PREFIX = re.compile(r"^(?:\[[^\]]*\])+")
_TAGS = re.compile(r"\[([^\]]*)\]")
_PERIOD = re.compile(r"\((\d{4})[.\-](\d{1,2})(?:[.\-]\d{1,2})?\)")


def classify(nm: str):
    nm = (nm or "").strip()
    body = _PREFIX.sub("", nm)
    cls = next((c for rx, c in DOC_CLASS if rx.search(body)), "other")
    pe = None
    m = _PERIOD.search(nm)
    if m and 1 <= int(m[2]) <= 12:
        y, mo = int(m[1]), int(m[2])
        pe = date(y, mo, calendar.monthrange(y, mo)[1])
    rev = "original"
    pm = _PREFIX.match(nm)
    tags = _TAGS.findall(pm.group(0)) if pm else []
    for t in tags:
        if t.strip() in REV_KIND:
            rev = REV_KIND[t.strip()]
            break
    else:
        if tags:
            rev = "other"
    return cls, pe, rev


class Keys:
    def __init__(self):
        self.keys, self.i = dart_keys(), 0

    @property
    def cur(self):
        return self.keys[self.i]

    def rotate(self):
        self.i += 1
        if self.i >= len(self.keys):
            raise SystemExit("OpenDART 키 전부 한도 초과(020) — 내일 이어서 실행")


def norm_name(s: str) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").upper()


def load_corp(conn, keys: Keys, sess):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pr_corp")
    if cur.fetchone()[0] > 50000:
        return
    r = sess.get(CORP_URL, params={"crtfc_key": keys.cur}, timeout=120)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(zf.read(zf.namelist()[0]))
    rows = [(e.findtext("corp_code"), e.findtext("corp_name"), (e.findtext("stock_code") or "").strip(),
             e.findtext("modify_date")) for e in root.iter("list")]
    cur.executemany("INSERT INTO pr_corp (corp_code, corp_name, stock_code, modify_date) VALUES (%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE corp_name=VALUES(corp_name), stock_code=VALUES(stock_code), "
                    "modify_date=VALUES(modify_date)", rows)
    conn.commit()
    print(f"pr_corp {len(rows)}건")


def import_existing(conn):
    """ipo_db 기존 수집분 이관. 이미 있는 rcept_no 는 건드리지 않는다."""
    cur = conn.cursor()
    n1 = cur.execute("""
        INSERT IGNORE INTO pr_filing (rcept_no, corp_code, corp_name, report_nm, rcept_dt, flr_nm, rm,
               doc_class, period_end, rev_kind, is_body_version, xml_status, html_status, origin)
        SELECT f.rcept_no, f.corp_code, f.corp_name, f.report_nm, f.rcept_dt, f.flr_nm, f.rm,
               IF(f.doc_class='major','other',f.doc_class), f.period_end, f.rev_kind, f.is_body_version,
               f.xml_status, f.html_status, 'ipo_db.cf_filing'
        FROM ipo_db.cf_filing f""")
    n2 = cur.execute("""
        INSERT IGNORE INTO pr_filing_xml (rcept_no, file_seq, file_name, source, is_main, encoding_used,
               formula_version, title_cnt, raw_bytes, body_gz, origin)
        SELECT rcept_no, file_seq, file_name, source, is_main, encoding_used, formula_version, title_cnt,
               raw_bytes, body_gz, 'ipo_db.cf_filing' FROM ipo_db.cf_filing_xml""")
    cur.execute("UPDATE pr_filing f JOIN pr_corp c ON c.corp_code=f.corp_code "
                "SET f.stock_code=c.stock_code WHERE f.stock_code IS NULL AND c.stock_code<>''")
    conn.commit()
    print(f"기존 수집분 이관: pr_filing +{n1} · pr_filing_xml +{n2}")


def targets(conn) -> list[tuple[str, str, str]]:
    snap = list(csv.DictReader(open(ROOT / "data/interim/universe_snap.csv", encoding="utf-8")))
    latest = {}
    for s in snap:
        latest[s["code"]] = s["corp_name"]
    cur = conn.cursor()
    cur.execute("SELECT corp_code, corp_name, stock_code FROM pr_corp")
    by_code, by_name = {}, {}
    for cc, nm, sc in cur.fetchall():
        if sc:
            by_code[sc] = cc
        by_name.setdefault(norm_name(nm), []).append(cc)
    out, miss = [], []
    for code, nm in sorted(latest.items()):
        cc = by_code.get(code)
        if not cc:
            c = by_name.get(norm_name(nm), [])
            cc = c[0] if len(c) == 1 else None
        (out if cc else miss).append((code, nm, cc))
    (ROOT / "logs").mkdir(exist_ok=True)
    with open(ROOT / "logs/s04_unmatched.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("code", "name")] + [(c, n) for c, n, _ in miss])
    print(f"모집단 {len(latest)}사 → corp_code 매칭 {len(out)} · 미매칭 {len(miss)} (logs/s04_unmatched.csv)")
    return out


def dart_list(keys: Keys, sess, corp_code: str) -> list[dict]:
    rows, page, total = [], 1, 1
    while page <= total:
        time.sleep(DELAY)
        r = sess.get(LIST_URL, params={"crtfc_key": keys.cur, "corp_code": corp_code, "bgn_de": BGN, "end_de": END,
                                       "pblntf_ty": "A", "last_reprt_at": "N", "page_no": page,
                                       "page_count": 100}, timeout=30)
        jo = r.json()
        st = jo.get("status")
        if st == "013":
            return []
        if st == "020":
            keys.rotate()
            continue
        if st != "000":
            raise RuntimeError(f"{corp_code} status={st} {jo.get('message')}")
        rows += jo.get("list", [])
        total = int(jo.get("total_page") or 1)
        page += 1
    return rows


def save(conn, stock_code: str, recs: list[dict]):
    cur = conn.cursor()
    vals = []
    for x in recs:
        cls, pe, rev = classify(x["report_nm"])
        vals.append((x["rcept_no"], x["corp_code"], x["corp_name"], stock_code, x["report_nm"].strip(),
                     x["rcept_dt"], x.get("flr_nm"), x.get("rm"), cls, pe, rev))
    cur.executemany("""INSERT INTO pr_filing (rcept_no, corp_code, corp_name, stock_code, report_nm, rcept_dt,
                         flr_nm, rm, doc_class, period_end, rev_kind) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE stock_code=COALESCE(pr_filing.stock_code, VALUES(stock_code)),
                         report_nm=VALUES(report_nm), rm=VALUES(rm)""", vals)
    # 잠정 본문 버전: (회사, 종류, 기준일) 안 최신 접수. 원문 확정(s07)이 끝난 그룹은 건드리지 않는다.
    corp = recs[0]["corp_code"]
    cur.execute("""UPDATE pr_filing f JOIN (
                     SELECT doc_class, period_end, MAX(rcept_no) r FROM pr_filing
                     WHERE corp_code=%s AND doc_class<>'other' AND period_end IS NOT NULL
                     GROUP BY doc_class, period_end) p
                   ON f.corp_code=%s AND f.doc_class=p.doc_class AND f.period_end=p.period_end
                   SET f.is_body_version = (f.rcept_no = p.r)
                   WHERE f.xml_status IS NULL""", (corp, corp))
    cur.execute("INSERT INTO pr_corp_collect (corp_code, bgn_de, end_de, n_rows) VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE n_rows=VALUES(n_rows), collected_at=NOW()", (corp, BGN, END, len(recs)))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    keys, sess = Keys(), requests.Session()
    conn = get_conn()
    load_corp(conn, keys, sess)
    import_existing(conn)
    tg = targets(conn)
    cur = conn.cursor()
    cur.execute("SELECT corp_code FROM pr_corp_collect WHERE bgn_de=%s AND end_de=%s", (BGN, END))
    done = {r[0] for r in cur.fetchall()}
    todo = [t for t in tg if t[2] not in done][: args.limit or None]
    print(f"목록 수집 대상 {len(todo)}사 (이미 수집 {len(done)})")
    n = 0
    for i, (code, nm, cc) in enumerate(todo, 1):
        recs = dart_list(keys, sess, cc)
        if recs:
            save(conn, code, recs)
            n += len(recs)
        else:
            cur.execute("INSERT IGNORE INTO pr_corp_collect (corp_code,bgn_de,end_de,n_rows) VALUES (%s,%s,%s,0)",
                        (cc, BGN, END))
            conn.commit()
        if i % 200 == 0:
            print(f"  {i}/{len(todo)} 누적 {n}건", flush=True)
    cur.execute("SELECT doc_class, COUNT(*), SUM(is_body_version) FROM pr_filing GROUP BY doc_class")
    print("pr_filing:", cur.fetchall())


if __name__ == "__main__":
    main()
