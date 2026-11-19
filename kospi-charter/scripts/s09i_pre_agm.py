"""s09i 사업보고서보다 먼저 접수된 주주총회 소집공고의 '정관의 변경' — 첨부 정관(주총 전 판) 뒤에 바뀐 결산배당 기준일

왜: 사용자 지시(2026-11-17, "진행. 코스닥도 포함.") — 상장협 2026.4.14 집계(유가 501사)와 맞춰 보니 코스피 정관no+yesorno 가
    59사 모자랐다. s05·s06(→ s09d)은 사업보고서 원본 최초 접수일 **뒤** 소집공고만 모은다. 정기주총 소집공고(주총 2주 전)는 대개
    사업보고서(주총 1주 전)보다 먼저 나오므로, 그 주총에서 기준일 조항을 바꾼 회사는 첨부 정관(주총 전 판) 태그에 머물러 있었다.

대상  근거가 첨부 정관 · 소집공고(basis_kind=사업보고서 · 주총소집공고)인 회사 전부 (처음엔 정관yes·정관yesorno 만 — 2026-11-17 넓힘).
      소집공고는 OpenDART 목록 캐시(data/raw/opendart_list/E006_Y_*.json — s05·s05k 가 받아 둔 시장 전체 목록, 호출 없음)에서
      원본 접수일 전 WINDOW 일 안에 접수된 것(정정은 최종본만 — 캐시가 last_reprt_at=Y).
단계
  targets  위 목록 → data/interim/s09i_targets{_sfx}.json
  fetch    OpenDART document.xml(순차, 요청 사이 GAP초 — 분당 80건 이하) → s06 의 parse·find_sections·section_text 로
           '정관의 변경' 절 → data/agm_pre{_sfx}/{종목}_{회사}/{접수일}_{접수번호}/정관의변경.txt  (s06 폴더와 섞지 않는다)
           원문 zip 캐시 data/raw/opendart_doc_pre/{접수번호}.zip
  pack     s09c.DIVAMEND(기준일 판별 문구)가 걸린 회사만, s09d 와 같은 입력(첨부 정관 발췌 + 첨부 정관 태그 + 안건 발췌)을
           서브에이전트용 in/{code}.txt 로 (API 를 쓰지 않는다 — 사용자 지시 2026-11-16)
  ingest   out/{code}.json(s09d 스키마) → data/interim/s09i_pre_agm{_sfx}.jsonl  {custom_id: b_{code}, rcept_nos, base_tag, output}
그다음  s09e(KIND 가결) → s09c(tag_current: 첨부 정관 → 이 안건 → 제출 뒤 안건) → s09g → s10

    python -X utf8 scripts/s09i_pre_agm.py targets [--sfx kosdaq]
    python -X utf8 scripts/s09i_pre_agm.py fetch   [--sfx kosdaq]     # 네트워크 — 다른 세션의 OpenDART 수집과 겹치지 않게
    python -X utf8 scripts/s09i_pre_agm.py pack    [--sfx kosdaq]
    python -X utf8 scripts/s09i_pre_agm.py ingest  [--sfx kosdaq]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, RAW, ROOT, Http, dart_keys, now_iso, read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402

WINDOW = 90
GAP = 0.8
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
CACHE = RAW / "opendart_doc_pre"


def notice_list() -> dict[str, list[dict]]:
    by: dict[str, dict] = {}
    for f in sorted((RAW / "opendart_list").glob("E006_Y_*.json")):
        for n in read_json(f).get("list") or []:
            if n.get("stock_code"):
                by.setdefault(n["stock_code"], {})[n["rcept_no"]] = n
    return {k: sorted(v.values(), key=lambda n: n["rcept_no"]) for k, v in by.items()}


def agm_root(sfx: str) -> Path:
    return ROOT / "data" / (f"agm_{sfx}_pre" if sfx else "agm_pre")


def targets(sfx: str) -> list[dict]:
    rows = read_json(X.paths(sfx)["out_json"])
    charter = {r["stock_code"]: r for r in read_json(FINAL / f"{'kosdaq' if sfx else 'kospi'}_charter.json")}
    nl = notice_list()
    out = []
    for r in rows:
        code = r["stock_code"]
        # 모든 태그 (사용자 지시 2026-11-17 "사업보고서보다 먼저 제출된 소집공고도, 뒤에 제출된 소집공고도 모두 봐야 지금 정관을 안다").
        # 처음(상장협 대조)엔 정관yes·정관yesorno 만 봐서 첨부 정관이 정관no 인 회사의 앞 공고(no → yesorno·yes)를 놓칠 수 있었다.
        # 근거가 첨부 정관 · 소집공고인 회사 — 전년도 정관 · 사업보고서 본문(확인필요 대체)은 s09f 가 본다.
        if r["basis_kind"] not in ("사업보고서", "주총소집공고"):
            continue
        c = charter.get(code) or {}
        orig = c.get("orig_rcept_dt") or r["rcept_no"][:8]
        lo = (datetime.strptime(orig, "%Y%m%d") - timedelta(days=WINDOW)).strftime("%Y%m%d")
        ns = [n for n in nl.get(code, []) if lo <= n["rcept_dt"] < orig]
        if ns:
            out.append({"stock_code": code, "corp_name": r["corp_name"], "tag": r["tag"], "tag_current": r["tag_current"],
                        "settle_month": r["settle_month"], "sec_group": r["sec_group"], "orig_rcept_dt": orig,
                        "notices": [{"rcept_no": n["rcept_no"], "rcept_dt": n["rcept_dt"], "report_nm": n["report_nm"],
                                     "corp_name": n["corp_name"]} for n in ns]})
    write_json(X.interim_of(sfx, "s09i_targets.json"), out)
    nn = sum(len(t["notices"]) for t in out)
    print(f"{len(out)}사 · 소집공고 {nn}건 (원본 접수일 전 {WINDOW}일) → {X.interim_of(sfx, 's09i_targets.json').name}")
    return out


def fetch(sfx: str, reparse: bool = False) -> None:
    import s06_agm_xml as A
    A.AGM = agm_root(sfx)
    tf = X.interim_of(sfx, "s09i_targets.json")
    ts = read_json(tf)
    key = dart_keys()[0]
    od = Http(delay=GAP)
    CACHE.mkdir(parents=True, exist_ok=True)
    n_req = n_sec = 0
    for t in ts:
        for n in t["notices"]:
            d = A.notice_dir(n, t["stock_code"])
            txt_f = d / "정관의변경.txt"
            raw_f = CACHE / f"{n['rcept_no']}.zip"
            if not raw_f.exists():
                raw_f.write_bytes(od.get(DOC_URL, params=dict(crtfc_key=key, rcept_no=n["rcept_no"])).content)
                n_req += 1
            if not txt_f.exists() and (reparse or not n.get("no_section")):   # reparse: 절 찾기 규칙을 고친 뒤 다시 읽기(원문은 캐시)
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
        if n_req and n_req % 50 == 0:
            write_json(tf, ts)
    write_json(tf, ts)
    print(f"{now_iso()} document.xml 요청 {n_req}건 · '정관의 변경' 절 {n_sec}건 → {agm_root(sfx).relative_to(ROOT)}")


def hit_targets(sfx: str) -> list[dict]:
    from s09c_dividend_build import DIVAMEND
    tg = {t["stock_code"]: t for t in read_json(X.paths(sfx)["targets"])}
    out = []
    for t in read_json(X.interim_of(sfx, "s09i_targets.json")):
        hits = [n["txt"] for n in t["notices"] if n.get("txt")
                and DIVAMEND.search((ROOT / n["txt"]).read_text(encoding="utf-8"))]
        if hits:
            out.append({**tg[t["stock_code"]], "amend_hits": hits})
    return out


def agent_dir(sfx: str) -> Path:
    return X.interim_of(sfx, "s09i_agent.json").with_suffix("")


def pack(sfx: str, chars: int) -> None:
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    L.SFX = sfx
    P = X.paths(sfx)
    ex, res = L.load_excerpts(P["excerpts"]), L.read_results(P["results"])
    review = read_json(P["review"]) if P["review"].exists() else {}
    out_f = X.interim_of(sfx, "s09i_pre_agm.jsonl")
    done = L.read_results(out_f)
    d = agent_dir(sfx)
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    items = []
    for t in hit_targets(sfx):
        code = t["stock_code"]
        rcs = [Path(p).parent.name.split("_", 1)[-1] for p in t["amend_hits"]]
        dj = done.get(f"b_{code}") or {}
        if dj.get("output") and sorted(dj.get("rcept_nos") or []) == sorted(rcs):
            continue                                     # 걸린 공고가 달라졌으면(절 찾기 규칙 보완 등) 다시 판별
        base = dict(D.base_of(res, code))
        if code in review:                               # 서식 판정·사람 검토로 바꾼 태그를 첨부 정관 태그로 보인다
            base["tag"] = review[code]["tag"]
        u = D.user_text(t, ex[code], base).replace("<정관의 변경 안건 · 소집공고", "<정관의 변경 안건 (사업보고서보다 먼저 접수) · 소집공고")
        fi, w = d / "in" / f"{code}.txt", L.wrap_long(u)
        if fi.exists() and fi.read_text(encoding="utf-8") != w:
            (d / "out" / f"{code}.json").unlink(missing_ok=True)       # 입력이 바뀌었다 — 다시 판별
        fi.write_text(w, encoding="utf-8")
        items.append({"code": code, "name": t["corp_name"], "chars": len(u), "base_tag": base.get("tag"),
                      "rcept_nos": [Path(p).parent.name.split("_", 1)[-1] for p in t["amend_hits"]]})
    packets, cur, n = [], [], 0
    for it in items:
        if cur and n + it["chars"] > chars:
            packets.append(cur)
            cur, n = [], 0
        cur.append(it)
        n += it["chars"]
    if cur:
        packets.append(cur)
    write_json(d / "packets.json", {"built_at": now_iso(), "prompt_sha256": L.sha(D.after_prompt()),
                                    "packets": {f"r{i:03d}": pk for i, pk in enumerate(packets, 1)}})
    print(f"{len(items)}사 → {len(packets)}묶음 · {d.relative_to(ROOT)}")


def ingest(sfx: str) -> None:
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    d = agent_dir(sfx)
    man = read_json(d / "packets.json")
    out_f = X.interim_of(sfx, "s09i_pre_agm.jsonl")
    done = L.read_results(out_f)
    sp = D.after_prompt()
    n, bad, missing = 0, [], []
    for pid, pk in man["packets"].items():
        for it in pk:
            code = it["code"]
            dj = done.get(f"b_{code}") or {}
            if dj.get("output") and sorted(dj.get("rcept_nos") or []) == sorted(it["rcept_nos"]):
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
            err = L._check(o, D.SCHEMA)
            if err:
                bad.append(f"{code} {err}")
                continue
            L.append(out_f, {"custom_id": f"b_{code}", "stock_code": code, "corp_name": it["name"], "rcept_nos": it["rcept_nos"],
                             "base_tag": it["base_tag"], "model": L.MODEL, "effort": None, "runner": "claude-code-subagent",
                             "batch_id": f"agent:{pid}", "prompt_sha256": L.sha(sp), "stop_reason": None, "usage": None,
                             "output": o, "error": None, "at": now_iso()})
            n += 1
    print(f"넣음 {n}건 · 형식 오류 {len(bad)}건 {bad[:10]} · 아직 없음 {len(missing)}건 {missing[:20]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["targets", "fetch", "pack", "ingest"])
    ap.add_argument("--sfx", default="")
    ap.add_argument("--chars", type=int, default=100_000)
    ap.add_argument("--reparse", action="store_true", help="fetch: '정관의 변경' 절 없음으로 표시한 공고도 캐시 원문으로 다시 읽기")
    a = ap.parse_args()
    if a.cmd == "targets":
        targets(a.sfx)
    elif a.cmd == "fetch":
        fetch(a.sfx, a.reparse)
    elif a.cmd == "pack":
        pack(a.sfx, a.chars)
    else:
        ingest(a.sfx)
