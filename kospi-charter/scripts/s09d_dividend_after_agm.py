"""s09d 사업보고서 제출 뒤 주총 '정관의 변경' 안건이 결산배당 기준일을 바꾸는지 — 바뀐 뒤 태그 (동기 호출)

왜: s09b 태그는 사업보고서 첨부 정관 기준이다. 12월 결산 회사는 대개 3월 정기주총 직전 정관이라, 그 주총에서 배당기준일
    조항을 고친 회사는 태그가 이미 옛것이다. s06 이 모은 소집공고(원본 제출일 이후 접수)의 '정관의 변경' 절에 기준일 판별에
    닿는 문구(s09c.DIVAMEND)가 있는 회사만 골라, 안건이 원안대로 가결되면 태그가 무엇이 되는지 본다.
    가결 여부는 확인하지 않는다(주총 결과 공시를 따로 보지 않았다) — 열 이름에 'agm_' 을 붙여 '안건 기준'임을 드러낸다.

입력  s09_targets.json(agm_charter_amend_txt) · s09a_excerpts.jsonl · s09b_results.jsonl(d_/f_ 결과)
      안건 텍스트는 s09a 의 앵커 창(windows_for)으로 잘라 보낸다 — 정관의변경.txt 에 재무제표 표 등이 섞여 있다
프롬프트  tagging-guide.md 의 PROMPT 구간 + AFTER-AGM 구간
출력  data/interim/s09d_after_agm.jsonl  {custom_id: a_{code}, stock_code, rcept_nos, output, usage, prompt_sha256, …}

사용법
  python -X utf8 scripts/s09d_dividend_after_agm.py            # 대상 전부 (이미 받은 회사는 건너뜀)
  python -X utf8 scripts/s09d_dividend_after_agm.py --list     # 대상만 보기
  python -X utf8 scripts/s09d_dividend_after_agm.py --sfx kosdaq --pack     # API 대신 서브에이전트: 입력 쓰기
  python -X utf8 scripts/s09d_dividend_after_agm.py --sfx kosdaq --ingest   #   결과(out/*.json) 검사해 넣기
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, read_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402
import s09b_dividend_tag_llm as L  # noqa: E402
from s09c_dividend_build import DIVAMEND  # noqa: E402

SUB = L.SUB
SCHEMA = {
    "type": "object",
    "properties": {
        "changes_record_date": {"type": "boolean"},
        "tag_after": {"type": "string", "enum": L.TAGS},
        "quotes_after": {"type": "array", "items": {"type": "string"}},
        "interim_after": {"type": "string", "enum": SUB},
        "quarterly_after": {"type": "string", "enum": SUB},
        "confidence": {"type": "string", "enum": ["높음", "보통", "낮음"]},
        "note": {"type": "string"},
    },
    "required": ["changes_record_date", "tag_after", "quotes_after", "interim_after", "quarterly_after",
                 "confidence", "note"],
    "additionalProperties": False,
}


def after_prompt() -> str:
    t = L.GUIDE.read_text(encoding="utf-8")
    m = re.search(r"<!-- AFTER-AGM START -->\n(.*?)\n<!-- AFTER-AGM END -->", t, re.S)
    if not m:
        raise SystemExit("tagging-guide.md 에 AFTER-AGM 구간이 없습니다")
    return L.prompt() + "\n\n" + m.group(1).strip()


def amend_excerpt(p: str) -> str:
    t = (ROOT / p).read_text(encoding="utf-8")
    wins = X.windows_for(t)
    return "\n\n".join(f"[안건 발췌 {i} · {w['start']:,}–{w['end']:,}자]\n" + t[w["start"]:w["end"]].strip()
                       for i, w in enumerate(wins, 1))


def targets(sfx: str) -> list[dict]:
    out = []
    for t in read_json(X.paths(sfx)["targets"]):
        hits = [p for p in t.get("agm_charter_amend_txt") or []
                if (ROOT / p).exists() and DIVAMEND.search((ROOT / p).read_text(encoding="utf-8"))]
        if hits:
            out.append({**t, "amend_hits": hits})
    return out


def user_text(t: dict, e: dict, base: dict) -> str:
    parts = [f"회사: {t['corp_name']} ({t['stock_code']}) · 결산월 {t.get('settle_month')}",
             f"사업보고서 첨부 정관({t.get('charter_att_date')})으로 단 태그: {base.get('tag')} · 근거 {base.get('basis_article')}"
             f" · 중간배당 {base.get('interim')} · 분기배당 {base.get('quarterly')}",
             "", "<첨부 정관 발췌>", e["excerpt"], "</첨부 정관 발췌>"]
    for p in t["amend_hits"]:
        rc = Path(p).parent.name                       # {접수일}_{rcept_no}
        parts += ["", f"<정관의 변경 안건 · 소집공고 {rc}>", amend_excerpt(p), "</정관의 변경 안건>"]
    return "\n".join(parts)


def base_of(res: dict, code: str) -> dict:
    r = res.get(f"f_{code}") if res.get(f"f_{code}", {}).get("output") else res.get(f"d_{code}")
    return (r or {}).get("output") or {}


def agent_pack(a, P, ts, out_f) -> None:
    """API 대신 서브에이전트 — 회사마다 user_text 를 in/{code}.txt 로 (s09b pack 과 같은 규칙)."""
    ex, res, done = L.load_excerpts(P["excerpts"]), L.read_results(P["results"]), L.read_results(out_f)
    d = X.interim_of(a.sfx, "s09d_agent.json").with_suffix("")
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    items = []
    for t in ts:
        code = t["stock_code"]
        if done.get(f"a_{code}", {}).get("output"):
            continue
        base = base_of(res, code)
        if not base:
            print(f"  {code} {t['corp_name']}: s09b 태그가 아직 없다 — 건너뜀")
            continue
        u = user_text(t, ex[code], base)
        (d / "in" / f"{code}.txt").write_text(L.wrap_long(u), encoding="utf-8")
        items.append({"code": code, "name": t["corp_name"], "chars": len(u),
                      "rcept_nos": [Path(p).parent.name.split("_", 1)[-1] for p in t["amend_hits"]], "base_tag": base.get("tag")})
    packets, cur, n = [], [], 0
    for it in items:
        if cur and n + it["chars"] > a.chars:
            packets.append(cur)
            cur, n = [], 0
        cur.append(it)
        n += it["chars"]
    if cur:
        packets.append(cur)
    L.write_json(d / "packets.json", {"built_at": L.now_iso(), "prompt_sha256": L.sha(after_prompt()),
                                      "packets": {f"q{i:03d}": pk for i, pk in enumerate(packets, 1)}})
    print(f"{len(items)}사 → {len(packets)}묶음 · {d.relative_to(ROOT)}")


def agent_ingest(a, P, ts, out_f) -> None:
    d = X.interim_of(a.sfx, "s09d_agent.json").with_suffix("")
    man = read_json(d / "packets.json")
    sp = after_prompt()
    ex, res, done = L.load_excerpts(P["excerpts"]), L.read_results(P["results"]), L.read_results(out_f)
    tmap = {t["stock_code"]: t for t in ts}
    n, bad, missing = 0, [], []
    for pid, pk in man["packets"].items():
        for it in pk:
            code = it["code"]
            if done.get(f"a_{code}", {}).get("output"):
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
            err = L._check(o, SCHEMA)
            if err:
                bad.append(f"{code} {err}")
                continue
            t = tmap[code]
            base = base_of(res, code)
            L.append(out_f, {"custom_id": f"a_{code}", "stock_code": code, "corp_name": t["corp_name"],
                             "rcept_nos": it["rcept_nos"], "base_tag": base.get("tag"), "model": L.MODEL, "effort": None,
                             "runner": "claude-code-subagent", "batch_id": f"agent:{pid}",
                             "prompt_sha256": L.sha(sp), "input_sha256": L.sha(user_text(t, ex[code], base)),
                             "stop_reason": None, "usage": None, "output": o, "error": None, "at": L.now_iso()})
            n += 1
    print(f"넣음 {n}건 · 형식 오류 {len(bad)}건 {bad[:10]} · 아직 없음 {len(missing)}건 {missing[:20]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--pack", action="store_true", help="API 대신 서브에이전트용 입력을 쓴다")
    ap.add_argument("--ingest", action="store_true", help="서브에이전트 결과(out/*.json)를 검사해 넣는다")
    ap.add_argument("--chars", type=int, default=100_000)
    a = ap.parse_args()
    P = X.paths(a.sfx)
    out_f = P["results"].with_name(P["results"].name.replace("s09b_results", "s09d_after_agm"))
    ts = targets(a.sfx)
    if a.list:
        for t in ts:
            print(t["stock_code"], t["corp_name"], [Path(p).parent.name for p in t["amend_hits"]])
        print(len(ts), "사")
        return
    if a.pack:
        return agent_pack(a, P, ts, out_f)
    if a.ingest:
        return agent_ingest(a, P, ts, out_f)
    ex = L.load_excerpts(P["excerpts"])
    res = L.read_results(P["results"])
    done = L.read_results(out_f)
    sp = after_prompt()
    c = L.client()
    tot = 0.0
    for t in ts:
        code = t["stock_code"]
        cid = f"a_{code}"
        if done.get(cid, {}).get("output"):
            continue
        r = res.get(f"f_{code}") if res.get(f"f_{code}", {}).get("output") else res.get(f"d_{code}")
        base = (r or {}).get("output") or {}
        ut = user_text(t, ex[code], base)
        msg = c.messages.create(model=L.MODEL, max_tokens=L.MAX_TOKENS,
                                system=[{"type": "text", "text": sp, "cache_control": {"type": "ephemeral"}}],
                                messages=[{"role": "user", "content": ut}],
                                output_config={"effort": L.EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}})
        o, err = L.parse_message(msg)
        u = L.usage_of(msg)
        tot += L.cost(u, batch=False)
        L.append(out_f, {"custom_id": cid, "stock_code": code, "corp_name": t["corp_name"],
                         "rcept_nos": [Path(p).parent.name.split("_", 1)[-1] for p in t["amend_hits"]],
                         "base_tag": base.get("tag"), "model": L.MODEL, "effort": L.EFFORT,
                         "prompt_sha256": L.sha(sp), "input_sha256": L.sha(ut), "stop_reason": msg.stop_reason,
                         "usage": u, "output": o, "error": err, "at": L.now_iso()})
        o = o or {}
        print(f"{code} {t['corp_name']}: {base.get('tag')} → {o.get('tag_after')} "
              f"(바뀜 {o.get('changes_record_date')}, {o.get('confidence')}) {o.get('note', '')[:120]}"
              f"{' ERR ' + err if err else ''}")
        time.sleep(0.2)
    print(f"합계 ${tot:.2f} (동기 호출 값) → {out_f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
