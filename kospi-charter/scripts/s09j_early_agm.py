"""s09j 사업보고서보다 1년쯤 앞선 주주총회 소집공고의 '정관의 변경' — 첨부 정관이 그보다도 옛 판인 회사

왜: 사용자 지시(2026-11-17) — 한세엠케이 · 한국쉘석유 · 아주스틸은 2025년 3월 정기주총에서 결산배당 기준일을 Y → N 으로 바꿨는데,
    2026년에 낸 2025 사업보고서에 그 전 정관을 붙여 두었다. s09i 는 사업보고서 원본 접수일 전 90일 안 공고(그해 정기주총)만 보고,
    s05 · s06(→ s09d)은 제출 뒤 공고만 보므로 이런 회사는 첨부 정관 태그에 머문다. 2025-01-01 부터(사용자 지시로 2024-01-01 부터)의 소집공고를 더 받아 잡는다.

대상  근거가 첨부 정관 · 소집공고인 회사 전부(s09i 와 같음). 소집공고는 OpenDART 목록(E006, 최종본)에서
      접수일이 [EARLY_FROM, 원본 접수일 - 90일) 인 것 — s09i 창(원본 접수일 전 90일)과 겹치지 않게.
단계
  list     OpenDART list.json E006 을 2024-01-01 ~ 2025-11-04 (목록 캐시가 2025-11-05 부터라) 3개월 구간으로 받기
           → data/raw/opendart_list/E006_Y_*.json (s05 의 fetch 그대로, 캐시 있으면 다시 안 부름)
  targets  위 목록 → data/interim/s09j_targets{_sfx}.json
  fetch    OpenDART document.xml(요청 사이 0.8초 — 분당 75건) → '정관의 변경' 절 → data/agm_early{_sfx}/{종목}_{회사}/{접수일}_{접수번호}/정관의변경.txt
           원문 zip 캐시 data/raw/opendart_doc_early/{접수번호}.zip
  pack     기준일 판별 문구(s09c.DIVAMEND)가 걸린 회사만, 첨부 정관 발췌 + 첨부 정관 태그 + 걸린 안건 발췌(접수 순서)를
           서브에이전트용 data/interim/s09j_agent{_sfx}/in/{code}.txt 로. 지시는 tagging-guide.md PROMPT + AFTER-AGM + EARLY-AGM
           (첨부 정관이 그 개정을 이미 담았는지부터 가린다)
  ingest   out/{code}.json(s09d 스키마 + applied_rcept_no) → data/interim/s09j_early_agm{_sfx}.jsonl {custom_id: j_{code}, …}
  그다음  s09e(KIND 가결 — applied_rcept_no 공고) → s09c(첨부 정관 → 이 안건 → s09i 앞 공고 → s09d 뒤 공고) → s09g → s10

    python -X utf8 scripts/s09j_early_agm.py list
    python -X utf8 scripts/s09j_early_agm.py targets [--sfx kosdaq]
    python -X utf8 scripts/s09j_early_agm.py fetch   [--sfx kosdaq]     # 네트워크 — 다른 세션의 DART · OpenDART 수집과 겹치지 않게
    python -X utf8 scripts/s09j_early_agm.py pack    [--sfx kosdaq] [--codes 105630,…]
    python -X utf8 scripts/s09j_early_agm.py ingest  [--sfx kosdaq]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, RAW, ROOT, Http, dart_keys, now_iso, read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402
import s09i_pre_agm as I  # noqa: E402

EARLY_FROM = "20240101"          # 처음 2025-01-01 → 사용자 지시(2026-11-19)로 2024-01-01
LIST_WINDOWS = [(date(2024, 1, 1), date(2024, 3, 31)), (date(2024, 4, 1), date(2024, 6, 30)),
                (date(2024, 7, 1), date(2024, 9, 30)), (date(2024, 10, 1), date(2024, 12, 31)),
                (date(2025, 1, 1), date(2025, 3, 31)), (date(2025, 4, 1), date(2025, 6, 30)),
                (date(2025, 7, 1), date(2025, 9, 30)), (date(2025, 10, 1), date(2025, 11, 4))]
GAP = 0.8
CACHE = RAW / "opendart_doc_early"


def agm_root(sfx: str) -> Path:
    return ROOT / "data" / (f"agm_{sfx}_early" if sfx else "agm_early")


def tfile(sfx: str) -> Path:
    return X.interim_of(sfx, "s09j_targets.json")


def cmd_list() -> None:
    import s05_agm_list as L
    http, keys = Http(delay=0.35), dart_keys()
    n = 0
    for b, e in LIST_WINDOWS:
        n += len(L.fetch(http, keys, b, e))
    print(f"{now_iso()} E006 목록 {n}건 ({LIST_WINDOWS[0][0]} ~ {LIST_WINDOWS[-1][1]}) → data/raw/opendart_list/")


def targets(sfx: str) -> list[dict]:
    rows = read_json(X.paths(sfx)["out_json"])
    charter = {r["stock_code"]: r for r in read_json(FINAL / f"{'kosdaq' if sfx else 'kospi'}_charter.json")}
    nl = I.notice_list()
    out = []
    for r in rows:
        code = r["stock_code"]
        if r["basis_kind"] not in ("사업보고서", "주총소집공고"):
            continue
        c = charter.get(code) or {}
        orig = c.get("orig_rcept_dt") or r["rcept_no"][:8]
        hi = (datetime.strptime(orig, "%Y%m%d") - timedelta(days=I.WINDOW)).strftime("%Y%m%d")
        ns = [n for n in nl.get(code, []) if EARLY_FROM <= n["rcept_dt"] < hi]
        if ns:
            out.append({"stock_code": code, "corp_name": r["corp_name"], "tag": r["tag"], "tag_current": r["tag_current"],
                        "settle_month": r["settle_month"], "sec_group": r["sec_group"], "orig_rcept_dt": orig,
                        "notices": [{"rcept_no": n["rcept_no"], "rcept_dt": n["rcept_dt"], "report_nm": n["report_nm"],
                                     "corp_name": n["corp_name"]} for n in ns]})
    write_json(tfile(sfx), out)
    nn = sum(len(t["notices"]) for t in out)
    print(f"{len(out)}사 · 소집공고 {nn}건 ({EARLY_FROM} ~ 원본 접수일 전 {I.WINDOW}일 앞) → {tfile(sfx).name}")
    return out


def fetch(sfx: str) -> None:
    import s06_agm_xml as A
    A.AGM = agm_root(sfx)
    tf = tfile(sfx)
    ts = read_json(tf)
    key = dart_keys()[0]
    od = Http(delay=GAP)
    CACHE.mkdir(parents=True, exist_ok=True)
    n_req = n_sec = n_fail = last = 0
    for t in ts:
        for n in t["notices"]:
            d = A.notice_dir(n, t["stock_code"])
            txt_f = d / "정관의변경.txt"
            raw_f = CACHE / f"{n['rcept_no']}.zip"
            if not raw_f.exists():
                # 인터넷이 잠깐 끊겨도(2026-11-19 이름 풀이 실패로 코스피 2024 수집이 멈춤) 30초 간격 10번까지 다시, 그래도 안 되면 건너뜀.
                # zip 이 아닌 응답(OpenDART 오류 문구)은 캐시에 쓰지 않는다 — 다시 돌리면 그 공고만 다시 받는다
                body = None
                for k in range(10):
                    try:
                        body = od.get(I.DOC_URL, params=dict(crtfc_key=key, rcept_no=n["rcept_no"])).content
                        break
                    except RuntimeError as ex:
                        print(f"  {now_iso()} {n['rcept_no']} 받기 실패 {k + 1}/10: {type(ex).__name__}", flush=True)
                        time.sleep(30)
                n_req += 1
                if not body or not body.startswith(b"PK"):
                    n_fail += 1
                    n.pop("no_section", None)
                    continue
                raw_f.write_bytes(body)
            if not txt_f.exists() and not n.get("no_section"):
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_f.read_bytes())) as z:
                        name = sorted(z.namelist(), key=len)[0]
                        root, _ = A.parse(z.read(name))
                    secs, _ = A.find_sections(root)
                except (zipfile.BadZipFile, KeyError, ValueError) as ex:
                    n["error"] = f"{type(ex).__name__}: {ex}"[:200]
                    secs = []
                if secs:
                    d.mkdir(parents=True, exist_ok=True)
                    txt_f.write_text("\n\n".join(A.section_text(s) for s in secs), encoding="utf-8")
                else:
                    n["no_section"] = True
            if txt_f.exists():
                n["txt"] = txt_f.relative_to(ROOT).as_posix()
                n_sec += 1
            if n_req and n_req % 50 == 0 and n_req != last:
                last = n_req
                write_json(tf, ts)
                print(f"  {now_iso()} 요청 {n_req}건", flush=True)
    write_json(tf, ts)
    print(f"{now_iso()} document.xml 요청 {n_req}건(못 받음 {n_fail}) · '정관의 변경' 절 {n_sec}건 → {agm_root(sfx).relative_to(ROOT)}")


def schema() -> dict:
    """s09d 스키마 + applied_rcept_no (tag_after 의 근거가 된 안건의 소집공고 접수번호 — KIND 가결 · 주총일을 그 공고로 본다)."""
    import s09d_dividend_after_agm as D
    s = dict(D.SCHEMA)
    s["properties"] = {**D.SCHEMA["properties"], "applied_rcept_no": {"type": "string"}}
    s["required"] = D.SCHEMA["required"] + ["applied_rcept_no"]
    return s


def early_prompt() -> str:
    import re
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    t = L.GUIDE.read_text(encoding="utf-8")
    m = re.search(r"<!-- EARLY-AGM START -->\n(.*?)\n<!-- EARLY-AGM END -->", t, re.S)
    if not m:
        raise SystemExit("tagging-guide.md 에 EARLY-AGM 구간이 없습니다")
    return D.after_prompt() + "\n\n" + m.group(1).strip()


def hit_targets(sfx: str) -> list[dict]:
    """'정관의 변경' 절에 기준일 판별 문구(s09c.DIVAMEND)가 걸린 공고가 있는 회사 — 공고는 접수 순서로."""
    import s06_agm_xml as A
    from s09c_dividend_build import DIVAMEND
    A.AGM = agm_root(sfx)
    tg = {t["stock_code"]: t for t in read_json(X.paths(sfx)["targets"])}
    out = []
    for t in read_json(tfile(sfx)):
        # 대상 표의 'txt' 표시가 아니라 디스크의 정관의변경.txt 로 (수집이 끊겨 표시가 덜 붙은 채 저장될 수 있다)
        fs = [A.notice_dir(n, t["stock_code"]) / "정관의변경.txt" for n in sorted(t["notices"], key=lambda n: n["rcept_no"])]
        hits = [f for f in fs if f.exists() and DIVAMEND.search(f.read_text(encoding="utf-8"))]
        if hits:
            out.append({**tg[t["stock_code"]], "orig_rcept_dt": t["orig_rcept_dt"],
                        "amend_hits": [f.relative_to(ROOT).as_posix() for f in hits]})
    return out


def agent_dir(sfx: str) -> Path:
    return X.interim_of(sfx, "s09j_agent.json").with_suffix("")


def out_file(sfx: str) -> Path:
    return X.interim_of(sfx, "s09j_early_agm.jsonl")


# 규칙 거르기 (2026-11-19): 1~2년 앞선 안건은 대개 첨부 정관이 이미 반영한 판이다(코스피 표본 · 첫 80사 판별에서 87사 중 85사).
# 대비표('변경 전 | 변경 후 | 사유') 중 기준일 판별 문구가 걸린 줄에서 기준일 낱말이 든 조항 가운데 실제로 바뀐 것만 보고,
# '변경 후' 조항은 모두 첨부 정관에 있고(3글자 조각 95% 이상) '변경 전'에서 사라진 조항은 하나도 없으면(80% 미만) '이미 반영'으로
# 서브에이전트 없이 넣는다. 조금이라도 어긋나면 서브에이전트가 본다. 시험: 서브에이전트 판별 87사에 대해 규칙 '이미 반영' 53사가
# 모두 서브에이전트와 같았고, 옛 판 2사(한세엠케이 · 한국쉘석유)는 모두 서브에이전트로 넘어갔다.
R_KEY = re.compile(r"기\s*준\s*일|결\s*산\s*기|주\s*주\s*명\s*부|질\s*권\s*자|배\s*당\s*을\s*받\s*을|사\s*업\s*[연년]\s*도\s*말|12\s*월\s*31\s*일")
R_ANNOT = re.compile(r"[<(\[〈【]\s*(?:개정|신설|삭제|본조)[^>)\]〉】]{0,40}[>)\]〉】]")


def _rnorm(s: str) -> str:
    return re.sub(r"[\s\W_①-⑳]+|\d+\s*\.", "", R_ANNOT.sub("", s))


def _rclauses(cell: str) -> list[str]:
    out = []
    for p in re.split(r"\s/\s|(?=[①-⑳])|(?<=다\.)\s+(?=\d{1,2}\.\s)", cell):
        n = _rnorm(p)
        if len(n) >= 15 and R_KEY.search(p) and "좌동" not in n and "현행과같음" not in n:
            out.append(n)
    return out


def _g3(s: str) -> set[str]:
    return {s[i:i + 3] for i in range(len(s) - 2)}


def rule_reflected(t: dict, src: str | None) -> tuple[bool, str]:
    """(이미 반영인가, 까닭). False 면 서브에이전트가 본다."""
    from s09c_dividend_build import DIVAMEND
    if not src or not (ROOT / src).exists():
        return False, "첨부 정관 원문 없음"
    full = _rnorm((ROOT / src).read_text(encoding="utf-8"))
    fg = _g3(full)

    def cover(c: str) -> float:
        g = _g3(c)
        return 1.0 if c in full else (len(g & fg) / len(g) if g else 0)
    n_rows = 0
    for p in t["amend_hits"]:
        for ln in (ROOT / p).read_text(encoding="utf-8").splitlines():
            cells = ln.split(" | ")
            if not DIVAMEND.search(ln) or len(cells) < 2:
                continue
            b, a = _rclauses(cells[0]), _rclauses(cells[1])
            ch_a, rm_b = [c for c in a if c not in b], [c for c in b if c not in a]
            if not ch_a and not rm_b:
                continue
            n_rows += 1
            if any(cover(c) < 0.95 for c in ch_a):
                return False, "변경 후 문구가 첨부 정관에 없음"
            if any(cover(c) >= 0.8 for c in rm_b):
                return False, "변경 전 문구가 첨부 정관에 남음"
    if not n_rows:
        return False, "기준일 문구가 바뀐 줄 없음"
    return True, f"대비표 {n_rows}줄의 '변경 후' 기준일 문구가 첨부 정관에 있고 '변경 전' 문구는 없음"


def complete_codes(sfx: str) -> set[str]:
    """대상 공고 원문(zip)을 모두 받은 회사 — 수집 중에도 이 회사들은 걸린 공고가 더 늘지 않으니 먼저 판별해도 된다."""
    return {t["stock_code"] for t in read_json(tfile(sfx)) if all((CACHE / f"{n['rcept_no']}.zip").exists() for n in t["notices"])}


def pack(sfx: str, chars: int, only: set[str], complete: bool = False, use_rule: bool = True) -> None:
    """s09i pack 과 같은 입력(첨부 정관 발췌 + 첨부 정관 태그 + 안건 발췌) — 안건 머리에 '사업보고서보다 1~2년 앞섬', 원본 접수일 한 줄.
    complete=True 면 공고 원문을 다 받은 회사만. 입력 글이 예전과 달라진 회사(공고가 더 걸림)는 예전 out 을 지운다."""
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    L.SFX = sfx
    P = X.paths(sfx)
    ex, res = L.load_excerpts(P["excerpts"]), L.read_results(P["results"])
    review = read_json(P["review"]) if P["review"].exists() else {}
    done = L.read_results(out_file(sfx))
    d = agent_dir(sfx)
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    items, n_rule = [], 0
    ok = complete_codes(sfx) if complete else None
    for t in hit_targets(sfx):
        code = t["stock_code"]
        rcs = [Path(p).parent.name.split("_", 1)[-1] for p in t["amend_hits"]]
        dj = done.get(f"j_{code}") or {}
        if (only and code not in only) or (ok is not None and code not in ok) or (dj.get("output") and dj.get("rcept_nos") == rcs):
            continue                                     # 넣은 결과가 있어도 걸린 공고가 달라졌으면 다시
        base = dict(D.base_of(res, code))
        if code in review:                               # 서식 판정 · 재검토로 바꾼 태그를 첨부 정관 태그로 보인다
            base["tag"] = review[code]["tag"]
        if use_rule:
            ok_r, why_r = rule_reflected(t, ex[code].get("src"))
            if ok_r:                                     # 규칙으로 '이미 반영' — 서브에이전트 없이 넣는다
                L.append(out_file(sfx), {
                    "custom_id": f"j_{code}", "stock_code": code, "corp_name": t["corp_name"], "rcept_nos": rcs,
                    "base_tag": base.get("tag"), "model": None, "effort": None, "runner": "rule", "batch_id": "rule",
                    "prompt_sha256": None, "stop_reason": None, "usage": None, "error": None, "at": now_iso(),
                    "output": {"changes_record_date": False, "tag_after": base.get("tag"), "quotes_after": [],
                               "interim_after": base.get("interim") or "확인필요", "quarterly_after": base.get("quarterly") or "확인필요",
                               "confidence": "높음", "note": f"첨부 정관에 이미 반영 (규칙: {why_r})", "applied_rcept_no": ""}})
                n_rule += 1
                continue
        u = D.user_text(t, ex[code], base).replace("<정관의 변경 안건 · 소집공고",
                                                   "<정관의 변경 안건 (사업보고서보다 1~2년 앞섬) · 소집공고")
        o = t["orig_rcept_dt"]
        u = u.replace("\n\n<첨부 정관 발췌>", f"\n사업보고서 원본 접수일: {o[:4]}-{o[4:6]}-{o[6:]}\n\n<첨부 정관 발췌>", 1)
        fi, w = d / "in" / f"{code}.txt", L.wrap_long(u)
        if fi.exists() and fi.read_text(encoding="utf-8") != w:
            (d / "out" / f"{code}.json").unlink(missing_ok=True)       # 입력이 바뀌었다 — 다시 판별
        fi.write_text(w, encoding="utf-8")
        items.append({"code": code, "name": t["corp_name"], "chars": len(u), "base_tag": base.get("tag"), "rcept_nos": rcs})
    packets, cur, n = [], [], 0
    for it in items:
        if cur and n + it["chars"] > chars:
            packets.append(cur)
            cur, n = [], 0
        cur.append(it)
        n += it["chars"]
    if cur:
        packets.append(cur)
    old = read_json(d / "packets.json")["packets"] if (d / "packets.json").exists() else {}
    k0 = len(old)
    write_json(d / "packets.json", {"built_at": now_iso(), "prompt_sha256": L.sha(early_prompt()),
                                    "packets": {**old, **{f"r{k0 + i:03d}": pk for i, pk in enumerate(packets, 1)}}})
    print(f"규칙 '이미 반영' {n_rule}사 · 서브에이전트 {len(items)}사 → {len(packets)}묶음 (r{k0 + 1:03d}~) · {d.relative_to(ROOT)}")


def ingest(sfx: str) -> None:
    import json
    import s09b_dividend_tag_llm as L
    d = agent_dir(sfx)
    man = read_json(d / "packets.json")
    out_f = out_file(sfx)
    done = L.read_results(out_f)
    sp, sc = early_prompt(), schema()
    n, bad, missing = 0, [], []
    latest = {it["code"]: (pid, it) for pid, pk in man["packets"].items() for it in pk}   # 같은 회사가 여러 묶음이면 마지막 것
    for code, (pid, it) in latest.items():
        dj = done.get(f"j_{code}") or {}
        if dj.get("output") and dj.get("rcept_nos") == it["rcept_nos"]:
            continue
        f = d / "out" / f"{code}.json"
        if not f.exists():
            missing.append(code)
            continue
        try:
            o = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as er:
            bad.append(f"{code} json {er}")
            continue
        err = L._check(o, sc)
        if not err and o["changes_record_date"] and o["applied_rcept_no"] not in it["rcept_nos"]:
            err = f"applied_rcept_no {o['applied_rcept_no']!r} 가 걸린 공고({it['rcept_nos']})에 없음"
        if err:
            bad.append(f"{code} {err}")
            continue
        L.append(out_f, {"custom_id": f"j_{code}", "stock_code": code, "corp_name": it["name"], "rcept_nos": it["rcept_nos"],
                         "base_tag": it["base_tag"], "model": L.MODEL, "effort": None, "runner": "claude-code-subagent",
                         "batch_id": f"agent:{pid}", "prompt_sha256": L.sha(sp), "stop_reason": None, "usage": None,
                         "output": o, "error": None, "at": now_iso()})
        n += 1
    print(f"넣음 {n}건 · 형식 오류 {len(bad)}건 {bad[:10]} · 아직 없음 {len(missing)}건 {missing[:20]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "targets", "fetch", "pack", "ingest"])
    ap.add_argument("--sfx", default="")
    ap.add_argument("--chars", type=int, default=100_000)
    ap.add_argument("--codes", default="", help="pack 에서 이 회사만 (표본 시험)")
    ap.add_argument("--complete", action="store_true", help="pack 에서 공고 원문을 다 받은 회사만 (수집 중 먼저 판별)")
    ap.add_argument("--no-rule", action="store_true", help="pack 에서 규칙 거르기 없이 모두 서브에이전트로")
    a = ap.parse_args()
    only = {c.strip() for c in a.codes.split(",") if c.strip()}
    {"list": lambda: cmd_list(), "targets": lambda: targets(a.sfx), "fetch": lambda: fetch(a.sfx),
     "pack": lambda: pack(a.sfx, a.chars, only, a.complete, not a.no_rule), "ingest": lambda: ingest(a.sfx)}[a.cmd]()
