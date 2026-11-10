"""s07 정기보고서 원문·목차·재무상태표 값 → MySQL dart_periodic

대상: 회차별 순자산 근거 보고서(_rules.choose_filing) — 기업 목록은 --targets CSV(stock_code 열) 또는 --set
  --set kind     KIND 저PBR 공표 151사 + PBR 개선계획 제출 62사
  --set scope    data/interim/capture_scope.csv (s06 이 만드는 하위 약 20%, ~400사)

한 보고서에 대해
  1) 원문    OpenDART document.xml → pr_filing_xml  (이미 있으면 건너뜀. ipo_db 이관분 포함)
             규약은 ipo_registration/commitment_followup/scripts/s04_fetch_xml.py — ZIP 전체 file_seq·gzip·014=missing
  2) 목차    DART main.do → pr_filing_toc  (NODE_RE 는 ipo_registration/step3b_fetch_html_body.py 와 같다)
  3) 값      재무상태표 노드 viewer.do 에서 '자본총계'·'지배기업 소유주지분'·'비지배지분' 행과 단위 → pr_fs_value
     노드 찾기: 연결은 '연결 재무상태표'(최신 서식 2-1) → 없으면 '연결재무제표'(2.) / 별도는 '재무상태표'(4-1) → '재무제표'(4.)
     같은 (회사·기준일·종류) 안에서 이 버전에 재무제표 노드가 없으면(첨부정정 등) 형제 버전으로 내려간다.

OpenDART·DART 웹은 IP 단위로 차단한다 — 다른 수집과 동시에 돌리지 말 것. 간격 1초.
"""
import argparse
import csv
import gzip
import html as H
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _db import dart_keys, get_conn  # noqa: E402
from _rules import DART_MAIN, DART_VIEWER, ROOT, choose_filing, load_rounds, periodic_filings  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0"}
DELAY = 1.0
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
NODE_RE = re.compile(
    r"node(?P<lvl>\d+)\['text'\]\s*=\s*\"(?P<text>.*?)\";"
    r".*?node(?P=lvl)\['id'\]\s*=\s*\"(?P<id>\d+)\";"
    r".*?node(?P=lvl)\['rcpNo'\]\s*=\s*\"(?P<rcp>\d+)\";"
    r".*?node(?P=lvl)\['dcmNo'\]\s*=\s*\"(?P<dcm>\d+)\";"
    r".*?node(?P=lvl)\['eleId'\]\s*=\s*\"(?P<ele>\d+)\";"
    r".*?node(?P=lvl)\['offset'\]\s*=\s*\"(?P<off>\d+)\";"
    r".*?node(?P=lvl)\['length'\]\s*=\s*\"(?P<len>\d+)\";"
    r".*?node(?P=lvl)\['dtd'\]\s*=\s*\"(?P<dtd>[^\"]+)\";"
    r".*?node(?P=lvl)\['tocNo'\]\s*=\s*\"(?P<toc>\d+)\";", re.S)
FORMULA_RE = re.compile(r"<FORMULA-VERSION[^>]*>([^<]+)</FORMULA-VERSION>")
TITLE_RE = re.compile(r"<TITLE[\s>]")
UNIT_RE = re.compile(r"단위\s*[:：]\s*(백만원|천원|원)")
MULT = {"원": 1, "천원": 1000, "백만원": 1_000_000}
def is_parent(label: str) -> bool:
    """지배기업 소유주지분 행. 표기가 회사마다 다르다(실측 2026-11-10: 지배기업소유지분·지배지분·지배기업 주주지분·
    지배기업의 소유주에게 귀속되는 지분·Ⅵ. 지배기업지분 …) — 목록 대신 규칙으로 잡고, 표 안 첫 행만 쓴다."""
    return (label.startswith("지배") and any(k in label for k in ("지분", "자본", "귀속"))
            and not any(k in label for k in ("비지배", "이익", "손익", "포괄", "손실")))


ROWS = {"equity_total": {"자본총계", "총자본", "자본총액"},
        "equity_parent": {"지배기업의소유주에게귀속되는자본", "지배기업소유주지분", "지배기업의소유지분",
                          "지배주주지분", "지배기업소유주에게귀속되는자본", "지배회사소유주지분"},
        "equity_nci": {"비지배지분", "비지배주주지분"}}
_last = [0.0]


def gap():
    d = DELAY - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    _last[0] = time.time()


class Net:
    """DART 호출 공용 세션. 시간초과·연결오류는 세션을 새로 열고 5·20·60초 쉬었다 다시 (s04_fetch_xml 규약)."""
    sess = requests.Session()

    @classmethod
    def get(cls, url, **kw):
        kw.setdefault("headers", UA)
        for i, wait in enumerate((5, 20, 60, None)):
            gap()
            try:
                r = cls.sess.get(url, **kw)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
                if wait is None:
                    raise
                cls.sess.close()
                cls.sess = requests.Session()
                time.sleep(wait)


def norm(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = H.unescape(s)
    s = re.sub(r"^[\s\dⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ.()\-\[ㆍ·]+", "", s)
    return re.sub(r"[\s·ㆍ\.\-()（）\[\]]", "", s)


# ---------- 1) 원문 ----------
def fetch_xml(conn, rcp: str, key: str, sess) -> str:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pr_filing_xml WHERE rcept_no=%s", (rcp,))
    if cur.fetchone()[0]:
        return "ok"
    r = Net.get(DOC_URL, params={"crtfc_key": key, "rcept_no": rcp}, timeout=180)
    if r.content[:2] != b"PK":
        st = re.search(r"<status>(\d+)</status>", r.text[:600])
        st = st.group(1) if st else "?"
        if st == "020":
            raise SystemExit("OpenDART 한도 초과(020)")
        status = "missing" if st == "014" else "error"
        cur.execute("UPDATE pr_filing SET xml_status=%s WHERE rcept_no=%s", (status, rcp))
        conn.commit()
        return status
    files = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in sorted(zf.namelist()):
            raw = zf.read(name)
            for enc in ("utf-8", "cp949"):
                try:
                    files.append((name, raw.decode(enc), enc))
                    break
                except UnicodeDecodeError:
                    continue
            else:
                files.append((name, raw.decode("utf-8", errors="replace"), "utf-8/replace"))
    prepared = []
    for seq, (name, text, enc) in enumerate(files):
        body = text.encode("utf-8")
        fv = FORMULA_RE.search(text[:4000])
        prepared.append([rcp, seq, name[:300], "xml", 0, enc, fv.group(1).strip() if fv else None,
                         len(TITLE_RE.findall(text)), len(body), gzip.compress(body, 6)])
    best = max(prepared, key=lambda p: (p[7], p[2] == f"{rcp}.xml", -p[1]))
    best[4] = 1
    cur.executemany("INSERT INTO pr_filing_xml (rcept_no,file_seq,file_name,source,is_main,encoding_used,"
                    "formula_version,title_cnt,raw_bytes,body_gz) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE body_gz=VALUES(body_gz)", [tuple(p) for p in prepared])
    cur.execute("UPDATE pr_filing SET xml_status='ok' WHERE rcept_no=%s", (rcp,))
    conn.commit()
    return "ok"


# ---------- 2) 목차 ----------
def fetch_toc(conn, rcp: str, sess) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT toc_no, level, title, dcm_no, ele_id, offset, length, dtd FROM pr_filing_toc "
                "WHERE rcept_no=%s ORDER BY toc_no", (rcp,))
    got = cur.fetchall()
    if got:
        return [dict(zip(["toc_no", "level", "title", "dcm_no", "ele_id", "offset", "length", "dtd"], g)) for g in got]
    t = Net.get(DART_MAIN.format(rcp), timeout=60).text
    nodes, stack = [], []
    for m in NODE_RE.finditer(t):
        lvl, toc = int(m["lvl"]), int(m["toc"])
        stack = stack[: lvl - 1]
        parent = stack[-1] if stack else None
        stack.append(toc)
        nodes.append({"toc_no": toc, "level": lvl, "parent_toc_no": parent, "title": H.unescape(m["text"]).strip()[:300],
                      "dcm_no": m["dcm"], "ele_id": int(m["ele"]), "offset": int(m["off"]),
                      "length": int(m["len"]), "dtd": m["dtd"]})
    if not nodes:
        cur.execute("UPDATE pr_filing SET toc_status='no_viewer' WHERE rcept_no=%s", (rcp,))
        conn.commit()
        return []
    cur.executemany("INSERT IGNORE INTO pr_filing_toc (rcept_no,toc_no,level,parent_toc_no,title,dcm_no,ele_id,"
                    "offset,length,dtd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(rcp, n["toc_no"], n["level"], n["parent_toc_no"], n["title"], n["dcm_no"], n["ele_id"],
                      n["offset"], n["length"], n["dtd"]) for n in nodes])
    cur.execute("UPDATE pr_filing SET toc_status='ok' WHERE rcept_no=%s", (rcp,))
    conn.commit()
    return nodes


def bs_node(nodes: list[dict], scope: str) -> dict | None:
    """재무상태표가 실린 가장 좁은 목차 노드."""
    titles = [(norm(n["title"]), n) for n in nodes]
    if scope == "consolidated":
        prefs = [lambda t: t.startswith("연결재무상태표"), lambda t: t == "연결재무제표"]
    else:
        prefs = [lambda t: t.startswith("재무상태표") and not t.startswith("연결"),
                 lambda t: t == "재무제표"]
    for p in prefs:
        for t, n in titles:
            if p(t):
                return n
    return None


# ---------- 3) 값 ----------
def parse_bs(page: str) -> dict:
    um = UNIT_RE.search(page)
    unit = um.group(1) if um else None
    out = {"unit": unit}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
        if len(cells) < 2:
            continue
        label = norm(cells[0])
        for item, names in ROWS.items():
            hit = is_parent(label) if item == "equity_parent" else label in names
            if hit and item not in out:
                # 값 칸 = 라벨 뒤 첫 '금액' 칸. 주석 번호(짧은 숫자, 콤마 없음)는 건너뛴다.
                # 실측: 보험사 재무상태표는 [과목, 주석, 당기 세부, 당기 합계, ...] 라 두 번째 칸이 주석이다.
                for c in cells[1:]:
                    txt = H.unescape(re.sub(r"<[^>]+>", "", c)).strip().replace(" ", "").replace("\xa0", "")
                    digits = re.sub(r"[^\d]", "", txt)
                    if not digits or not ("," in txt or "(" in txt or len(digits) >= 4):
                        continue
                    neg = txt.startswith("(") or txt.startswith("-") or txt.startswith("△")
                    out[item] = (-int(digits) if neg else int(digits),
                                 H.unescape(re.sub(r"<[^>]+>", " ", tr)).strip()[:300])
                    break
    return out


def extract_values(conn, rcp: str, nodes: list[dict], sess, force: bool = False) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pr_fs_value WHERE rcept_no=%s", (rcp,))
    if cur.fetchone()[0] and not force:
        return -1
    n_saved = 0
    for scope in ("consolidated", "separate"):
        n = bs_node(nodes, scope)
        if not n:
            continue
        page = Net.get(DART_VIEWER.format(rcp=rcp, dcm=n["dcm_no"], ele=n["ele_id"], off=n["offset"],
                                          len=n["length"], dtd=n["dtd"]), timeout=90).text
        vals = parse_bs(page)
        mult = MULT.get(vals["unit"] or "", None)
        for item in ROWS:
            if item in vals:
                v, raw = vals[item]
                cur.execute("REPLACE INTO pr_fs_value (rcept_no,fs_scope,item,value_won,unit_text,raw_text,toc_no) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (rcp, scope, item, v * mult if mult else None, vals["unit"], raw, n["toc_no"]))
                n_saved += 1
    conn.commit()
    return n_saved


def target_codes(which: str) -> list[str]:
    import pandas as pd
    if which == "kind":
        snap = pd.read_csv(ROOT / "data/interim/universe_snap.csv", dtype=str)
        snap = snap[snap["round"] == "2026.11"]
        k = pd.read_csv(ROOT / "data/final/kind_lowpbr_20261102.csv", dtype=str)
        v = pd.read_csv(ROOT / "data/final/kind_valueup_discl.csv", dtype=str)
        v = v[v.title.str.contains("PBR") & (v.disc_dt <= "2026-10-22 23:59")]
        c5 = set(k.corp5) | set(v.corp5)
        return sorted(snap[snap.code.str[:5].isin(c5) & snap.code.str.endswith("0")].code.unique())
    if which == "scope":
        return [r["code"] for r in csv.DictReader(open(ROOT / "data/interim/capture_scope.csv", encoding="utf-8"))]
    return [r["stock_code"] for r in csv.DictReader(open(which, encoding="utf-8"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="kind", help="kind | scope | <csv 경로>")
    ap.add_argument("--rounds", default="", help="쉼표 구분 회차(예 2026.11). 비우면 13회차 전부")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-xml", action="store_true", help="원문 ZIP 은 받지 않고 목차·값만")
    ap.add_argument("--reparse-parent", action="store_true",
                    help="연결 자본총계는 있는데 지배지분이 빠진 보고서만 재무상태표를 다시 읽는다")
    args = ap.parse_args()
    if args.reparse_parent:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""SELECT DISTINCT v.rcept_no FROM pr_fs_value v WHERE v.fs_scope='consolidated' AND v.item='equity_total'
                         AND NOT EXISTS (SELECT 1 FROM pr_fs_value p WHERE p.rcept_no=v.rcept_no
                                         AND p.fs_scope='consolidated' AND p.item='equity_parent')""")
        todo = [r[0] for r in cur.fetchall()]
        n = 0
        for i, rcp in enumerate(todo, 1):
            try:
                extract_values(conn, rcp, fetch_toc(conn, rcp, None), None, force=True)
            except requests.RequestException:
                continue
            cur.execute("SELECT 1 FROM pr_fs_value WHERE rcept_no=%s AND fs_scope='consolidated' AND item='equity_parent'", (rcp,))
            n += bool(cur.fetchone())
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} 지배지분 확보 {n}", flush=True)
        print(f"지배지분 재추출: 대상 {len(todo)} · 확보 {n}")
        return

    codes = target_codes(args.set)
    rounds = [r for r in load_rounds() if not args.rounds or r["round"] in args.rounds.split(",")]
    conn = get_conn()
    fil = periodic_filings(conn, codes)
    jobs = []
    for code in codes:
        for r in rounds:
            f = choose_filing(fil.get(code, []), r["base_date"])
            if f:
                jobs.append((code, r["round"], f[0]))
    rcps = list(dict.fromkeys(j[2] for j in jobs))[: args.limit or None]
    print(f"{len(codes)}사 × {len(rounds)}회차 → 근거 보고서 {len(rcps)}건 (중복 제거)")

    key = dart_keys()[0]
    sess = requests.Session()
    stat = {"xml": {}, "toc0": 0, "val": 0, "noval": []}
    consec, errs = 0, []
    for i, rcp in enumerate(rcps, 1):
        try:
            if not args.no_xml:
                s = fetch_xml(conn, rcp, key, sess)
                stat["xml"][s] = stat["xml"].get(s, 0) + 1
            nodes = fetch_toc(conn, rcp, sess)
            if not nodes:
                stat["toc0"] += 1
                continue
            k = extract_values(conn, rcp, nodes, sess)
            consec = 0
        except requests.RequestException as e:
            # 재시도까지 실패한 문서는 건너뛰고 기록한다. 연속 5건이면 차단으로 보고 10분 쉰다.
            errs.append((rcp, type(e).__name__))
            consec += 1
            if consec % 5 == 0:
                print(f"  연속 실패 {consec}건 — 차단으로 보고 600초 쉰다", flush=True)
                time.sleep(600)
            continue
        if k == 0:
            stat["noval"].append(rcp)
        elif k > 0:
            stat["val"] += 1
        if i % 50 == 0:
            print(f"  {i}/{len(rcps)} {stat['xml']} 목차없음 {stat['toc0']} 값추출 {stat['val']} 값없음 {len(stat['noval'])}",
                  flush=True)
    print("완료", {k: (v if not isinstance(v, list) else len(v)) for k, v in stat.items()}, "네트워크 실패", len(errs))
    if errs:
        with open(ROOT / "logs/s07_neterr.csv", "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(errs)
    # 형제 버전 대체: 고른 버전에 재무상태표 값이 없으면(예: [첨부정정] — 첨부만 갈아 끼움)
    # 같은 (회사, 종류, 작성기준일)의 다른 버전에서 근거를 찾는다. 접수번호 내림차순.
    cur = conn.cursor()
    has_val = lambda r: cur.execute("SELECT 1 FROM pr_fs_value WHERE rcept_no=%s AND item='equity_total' LIMIT 1", (r,)) > 0
    evidence, n_sib = {}, 0
    for rcp in dict.fromkeys(j[2] for j in jobs):
        if has_val(rcp):
            evidence[rcp] = rcp
            continue
        cur.execute("""SELECT s.rcept_no FROM pr_filing f JOIN pr_filing s
                         ON s.corp_code=f.corp_code AND s.doc_class=f.doc_class AND s.period_end=f.period_end
                       WHERE f.rcept_no=%s AND s.rcept_no<>f.rcept_no ORDER BY s.rcept_no DESC""", (rcp,))
        for (sib,) in cur.fetchall():
            try:
                nodes = fetch_toc(conn, sib, None)
                if nodes:
                    extract_values(conn, sib, nodes, None)
            except requests.RequestException:
                continue
            if has_val(sib):
                evidence[rcp] = sib
                n_sib += 1
                break
    print(f"형제 버전으로 근거 대체 {n_sib}건 · 근거 없음 {sum(1 for j in jobs if j[2] not in evidence)}회차행")
    tag = args.set if args.set in ("kind", "scope") else "custom"
    with open(ROOT / f"data/interim/equity_source_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("code", "round", "rcept_no", "evidence_rcept_no")] +
                                [(c, r, x, evidence.get(x, "")) for c, r, x in jobs])


if __name__ == "__main__":
    main()
