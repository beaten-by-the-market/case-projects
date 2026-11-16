"""s09b 발췌(s09a)를 Claude Opus 5.5 로 읽혀 결산배당 기준일 태그 달기 (Message Batches API)

태그: 정관no(이사회가 정함) · 정관yes(정관상 결산일 고정) · 정관yesorno(결산일 원칙 + 이사회가 따로 정할 수 있음) · 확인필요
기준은 스킬 문서 .claude/skills/charter-dividend-record-date/references/tagging-guide.md 의
`PROMPT START`~`PROMPT END` 구간이고, 그 글을 그대로 시스템 프롬프트로 보낸다(해시를 결과에 남긴다).

요청
  · 모델 claude-opus-5-5, effort medium(조문 소속을 가리는 판단이 있다), max_tokens 8000
  · 출력은 output_config.format 의 JSON 스키마(SCHEMA)로 고정 — 인용(quotes)은 발췌 글자 그대로
  · 시스템 프롬프트에 cache_control — 배치 안에서 같은 프롬프트를 되읽는다
  · 본문이 없는 정관(s09a no_text)은 보내지 않고 `확인필요` 로 바로 적는다
  · `full` 명령은 발췌 대신 정관 전문을 보낸다(발췌로 `확인필요`가 나온 회사를 다시 볼 때)

저장
  data/interim/s09b_results.jsonl  custom_id 별 응답 원문(덧붙여 쓰고, 읽을 때 같은 id 의 마지막 것을 쓴다)
                                   {custom_id, stock_code, mode(excerpt|full), batch_id, model, prompt_sha256, input_sha256,
                                    stop_reason, usage, output(JSON), error, at}
  data/interim/s09b_batches.json   보낸 배치 목록

사용법
  python -X utf8 scripts/s09b_dividend_tag_llm.py pilot --codes 005930,010130   # 동기 호출로 시험, 토큰·비용 출력
  python -X utf8 scripts/s09b_dividend_tag_llm.py submit                        # 결과 없는 회사 전부 배치로
  python -X utf8 scripts/s09b_dividend_tag_llm.py status | collect
  python -X utf8 scripts/s09b_dividend_tag_llm.py full --codes 000000,...       # 전문으로 다시 (동기)
  --sfx kosdaq  다른 표 (s09a 와 같은 접미어 — 파일 경로는 s09a.paths)
키: .env 의 ANTHROPIC_API_KEY (git 제외)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, load_env, now_iso, read_json, write_json  # noqa: E402
from s09a_dividend_excerpt import paths  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 8000
PRICE_IN, PRICE_OUT = 4.0 / 1e6, 20.0 / 1e6        # 일반 호출 $/토큰. 배치는 절반, 캐시 읽기는 입력의 1/20
GUIDE = ROOT / ".claude/skills/charter-dividend-record-date/references/tagging-guide.md"
SFX = ""                                            # main() 의 --sfx

TAGS = ["정관no", "정관yes", "정관yesorno", "확인필요"]
ROUTES = ["배당조항", "배당조항→기준일조항 참조", "기준일조항(배당 명시)", "기준일조항(배당 명시 없음)", "없음"]
SUB = ["없음", "고정", "이사회결정", "혼합", "확인필요"]
SCHEMA = {
    "type": "object",
    "properties": {
        "tag": {"type": "string", "enum": TAGS},
        "route": {"type": "string", "enum": ROUTES},
        "basis_article": {"type": "string"},
        "quotes": {"type": "array", "items": {"type": "string"}},
        "fixed_point": {"type": "string"},
        "board_may_set": {"type": "boolean"},
        "amend_note": {"type": "string"},
        "interim": {"type": "string", "enum": SUB},
        "quarterly": {"type": "string", "enum": SUB},
        "confidence": {"type": "string", "enum": ["높음", "보통", "낮음"]},
        "note": {"type": "string"},
    },
    "required": ["tag", "route", "basis_article", "quotes", "fixed_point", "board_may_set", "amend_note",
                 "interim", "quarterly", "confidence", "note"],
    "additionalProperties": False,
}


def prompt() -> str:
    t = GUIDE.read_text(encoding="utf-8")
    m = re.search(r"<!-- PROMPT START -->\n(.*?)\n<!-- PROMPT END -->", t, re.S)
    if not m:
        raise SystemExit(f"{GUIDE} 에 PROMPT START/END 구간이 없습니다")
    return m.group(1).strip()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def client():
    import anthropic
    key = load_env().get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 가 .env 에 없습니다")
    return anthropic.Anthropic(api_key=key, max_retries=4)


def load_excerpts(path: Path) -> dict[str, dict]:
    return {e["stock_code"]: e for e in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def load_targets() -> dict[str, dict]:
    tf = paths(SFX)["targets"]
    return {r["stock_code"]: r for r in read_json(tf)} if tf.exists() else {}


def user_text(e: dict, t: dict, mode: str) -> str:
    kind = {"text": "텍스트", "image": "스캔 이미지 → 글자 인식", "pdf": "PDF(글자층 또는 글자 인식)",
            "mixed": "텍스트+스캔"}.get(t.get("charter_content_type") or "", t.get("charter_content_type") or "")
    head = (f"회사: {e['corp_name']} ({e['stock_code']}) · 시장 {t.get('market') or ''} {t.get('sec_group') or ''}".rstrip()
            + f" · 결산월 {t.get('settle_month') or '?'}\n"
            f"정관: {t.get('charter_att_date') or '?'} 사업보고서 첨부본 · 원문 {kind}\n")
    if mode == "full":
        body = (ROOT / e["src"]).read_text(encoding="utf-8")
        return head + f"아래는 정관 전문({len(body):,}자)이다.\n\n<정관>\n{body}\n</정관>"
    return (head + f"아래는 정관 전문 {e['full_chars']:,}자 가운데 배당·기준일 관련 키워드 주변 {e['n_windows']}곳"
            f"({e['excerpt_chars']:,}자)을 발췌한 것이다.\n\n<발췌>\n{e['excerpt']}\n</발췌>")


def params(e: dict, t: dict, mode: str, sysprompt: str) -> dict:  # mode: excerpt·pilot → 발췌, full → 전문
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": sysprompt, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user_text(e, t, mode)}],
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    }


def cid_of(code: str, mode: str) -> str:
    """d_ 발췌 본 실행 · f_ 전문 재판별 · p_ 시험(pilot, 본 결과에 쓰지 않음)"""
    return {"excerpt": "d", "full": "f", "pilot": "p"}[mode] + "_" + code


def read_results(path: Path) -> dict[str, dict]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["custom_id"]] = r
    return out


def append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_message(msg) -> tuple[dict | None, str | None]:
    if msg.stop_reason == "refusal":
        return None, "refusal"
    if msg.stop_reason == "max_tokens":
        return None, "max_tokens"
    text = next((b.text for b in msg.content if b.type == "text"), None)
    if text is None:
        return None, "no_text_block"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as ex:
        return None, f"json: {ex}"


def usage_of(msg) -> dict:
    u = msg.usage
    return {k: getattr(u, k, None) or 0 for k in
            ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}


def cost(u: dict, batch: bool) -> float:
    c = (u["input_tokens"] + 1.25 * u["cache_creation_input_tokens"] + 0.1 * u["cache_read_input_tokens"]) * PRICE_IN \
        + u["output_tokens"] * PRICE_OUT
    return c / 2 if batch else c


def record(e: dict, mode: str, sysprompt: str, utext: str, msg=None, batch_id=None, error=None) -> dict:
    out, err = (parse_message(msg) if msg is not None else (None, error))
    return {"custom_id": cid_of(e["stock_code"], mode), "stock_code": e["stock_code"], "corp_name": e["corp_name"],
            "mode": mode, "batch_id": batch_id, "model": MODEL, "effort": EFFORT, "prompt_sha256": sha(sysprompt),
            "input_sha256": sha(utext), "stop_reason": getattr(msg, "stop_reason", None),
            "usage": usage_of(msg) if msg is not None else None, "output": out, "error": err, "at": now_iso()}


def no_text_record(e: dict, sysprompt: str) -> dict:
    return {"custom_id": cid_of(e["stock_code"], "excerpt"), "stock_code": e["stock_code"], "corp_name": e["corp_name"],
            "mode": "skip", "batch_id": None, "model": None, "effort": None, "prompt_sha256": sha(sysprompt),
            "input_sha256": None, "stop_reason": None, "usage": None, "error": None, "at": now_iso(),
            "output": {"tag": "확인필요", "route": "없음", "basis_article": "", "quotes": [], "fixed_point": "",
                       "board_may_set": False, "amend_note": "", "interim": "확인필요", "quarterly": "확인필요",
                       "confidence": "높음",
                       "note": ("정관 본문이 없다(첨부 PDF 가 Azure Information Protection 으로 잠겨 안내문만 있음). "
                                if e.get("src") else
                                "정관 원문이 없다(첨부 정관을 받지 못했거나 PDF 를 읽지 못함 — charter_fulltext_txt 빈 값). ")
                               + "LLM 에 보내지 않았다."}}


def sync_run(codes: list[str], mode: str, a) -> None:
    ex, tg, sp = load_excerpts(a.excerpts), load_targets(), prompt()
    c = client()
    tot = 0.0
    for code in codes:
        e = ex[code]
        if e["no_text"]:
            append(a.results, no_text_record(e, sp))
            print(f"{code} {e['corp_name']}: 본문 없음 → 확인필요 (호출 안 함)")
            continue
        p = params(e, tg.get(code, {}), mode, sp)
        t0 = time.time()
        msg = c.messages.create(**p)
        rec = record(e, mode, sp, p["messages"][0]["content"], msg)
        append(a.results, rec)
        u = rec["usage"]
        tot += cost(u, batch=False)
        o = rec["output"] or {}
        print(f"{code} {e['corp_name']}: {o.get('tag')} · {o.get('route')} · {o.get('basis_article')} · "
              f"중간 {o.get('interim')} · 분기 {o.get('quarterly')} · {o.get('confidence')} "
              f"[{u['input_tokens']:,}+캐시{u['cache_read_input_tokens']:,}/{u['cache_creation_input_tokens']:,} in · "
              f"{u['output_tokens']:,} out · {time.time() - t0:.0f}s]{' ERR ' + rec['error'] if rec['error'] else ''}")
        print(f"    {o.get('note')}")
        for q in o.get("quotes") or []:
            print(f"    「{q[:200]}」")
    print(f"합계 ${tot:.2f} (동기 호출 값)")


def submit(a) -> None:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    ex, tg, sp = load_excerpts(a.excerpts), load_targets(), prompt()
    done = {cid for cid, r in read_results(a.results).items() if r["output"] is not None}
    batches = read_json(a.batches) if a.batches.exists() else []
    pending = {cid for b in batches if b.get("status") != "collected" for cid in b["cids"]}
    todo = []
    for code, e in ex.items():
        cid = cid_of(code, "excerpt")
        if cid in done or cid in pending:
            continue
        if e["no_text"]:
            append(a.results, no_text_record(e, sp))
            continue
        todo.append((cid, params(e, tg.get(code, {}), "excerpt", sp)))
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        print("보낼 것이 없습니다")
        return
    c = client()
    b = c.messages.batches.create(requests=[Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**p))
                                            for cid, p in todo])
    batches.append({"id": b.id, "created_at": now_iso(), "n": len(todo), "cids": [cid for cid, _ in todo],
                    "prompt_sha256": sha(sp), "status": "submitted"})
    write_json(a.batches, batches)
    print(f"배치 {b.id} 제출 — {len(todo)}건")


def status(a) -> None:
    batches = read_json(a.batches) if a.batches.exists() else []
    c = client()
    for b in batches:
        if b.get("status") == "collected":
            continue
        r = c.messages.batches.retrieve(b["id"])
        b["processing_status"] = r.processing_status
        print(b["id"], r.processing_status, r.request_counts)
    write_json(a.batches, batches)


def collect(a) -> None:
    ex, tg, sp = load_excerpts(a.excerpts), load_targets(), prompt()
    batches = read_json(a.batches) if a.batches.exists() else []
    c = client()
    tot, n = 0.0, 0
    for b in batches:
        if b.get("status") == "collected":
            continue
        if c.messages.batches.retrieve(b["id"]).processing_status != "ended":
            print(b["id"], "아직 진행 중")
            continue
        for res in c.messages.batches.results(b["id"]):
            code = res.custom_id.split("_", 1)[1]
            e = ex[code]
            utext = user_text(e, tg.get(code, {}), "excerpt")
            if res.result.type == "succeeded":
                rec = record(e, "excerpt", sp, utext, res.result.message, batch_id=b["id"])
                tot += cost(rec["usage"], batch=True)
            else:
                rec = record(e, "excerpt", sp, utext, None, batch_id=b["id"], error=res.result.type)
            append(a.results, rec)
            n += 1
        b["status"] = "collected"
        b["collected_at"] = now_iso()
        write_json(a.batches, batches)
    rs = read_results(a.results)
    bad = [r for r in rs.values() if r["output"] is None]
    print(f"받음 {n}건 · 배치 값 ${tot:.2f} · 결과 {len(rs)}건 중 실패 {len(bad)}건 {[r['custom_id'] for r in bad][:20]}")


# ── API 대신 Claude Code 서브에이전트가 판별할 때 (pack → 에이전트 → ingest) ─────────────────────────────────────
# pack   : 결과 없는 회사마다 API 에 보냈을 사용자 메시지(user_text)를 in/{code}.txt 로 쓰고, 글자 수로 묶음(packets.json)을 짠다.
#          긴 줄은 WRAP 자에서 줄을 바꾼다(Read 도구가 긴 줄을 자르지 않게) — 인용 대조는 공백을 무시하므로 영향이 없다.
#          발췌에 핵심 문구가 없는 정관(weak)은 처음부터 전문(full, f_)으로 싼다.
# 에이전트: tagging-guide 의 PROMPT 구간을 시스템 프롬프트 삼아 in/{code}.txt 를 읽고 SCHEMA 그대로의 JSON 을 out/{code}.json 에 쓴다.
# ingest : out/*.json 을 SCHEMA 로 검사해 s09b_results 에 덧붙인다 (model 은 같은 Opus 5.5, runner 로 구분, usage 없음).
WRAP = 1000


def agent_dir() -> Path:
    return paths(SFX)["results"].parent / f"s09b_agent{'_' + SFX if SFX else ''}"


def wrap_long(s: str, width: int = WRAP) -> str:
    out = []
    for line in s.split("\n"):
        while len(line) > width:
            cut = line.rfind(" ", width // 2, width)
            cut = cut if cut > 0 else width
            out.append(line[:cut])
            line = line[cut:].lstrip(" ")
        out.append(line)
    return "\n".join(out)


def pack(a) -> None:
    ex, tg, sp = load_excerpts(a.excerpts), load_targets(), prompt()
    done = {r["stock_code"] for r in read_results(a.results).values() if r["output"] is not None
            and r["custom_id"][0] in "df"}
    d = agent_dir()
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    items = []
    for code, e in ex.items():
        if code in done:
            continue
        if e["no_text"]:
            append(a.results, no_text_record(e, sp))
            continue
        if a.exclude_ocr and str(e.get("src") or "").endswith("charter_ocr.txt"):
            continue                                   # Windows OCR 글 — 전사본(charter_llm.txt)이 나온 뒤 다시 pack
        mode = "full" if e["weak"] else "excerpt"
        u = user_text(e, tg.get(code, {}), mode)
        (d / "in" / f"{code}.txt").write_text(wrap_long(u), encoding="utf-8")
        items.append({"code": code, "name": e["corp_name"], "mode": mode, "chars": len(u)})
    packets, cur, n = [], [], 0
    for it in items:
        if cur and n + it["chars"] > a.chars:
            packets.append(cur)
            cur, n = [], 0
        cur.append(it)
        n += it["chars"]
    if cur:
        packets.append(cur)
    man = {"built_at": now_iso(), "prompt_sha256": sha(sp), "chars_per_packet": a.chars,
           "packets": {f"p{i:03d}": pk for i, pk in enumerate(packets, 1)}}
    write_json(d / "packets.json", man)
    print(f"{len(items)}사 → {len(packets)}묶음 ({a.chars:,}자 이하) · {d.relative_to(ROOT)}")


def _check(o, schema: dict | None = None) -> str | None:
    schema = schema or SCHEMA
    if not isinstance(o, dict):
        return "객체 아님"
    props = schema["properties"]
    miss = [k for k in schema["required"] if k not in o]
    extra = [k for k in o if k not in props]
    if miss or extra:
        return f"키 누락 {miss} · 여분 {extra}"
    for k, sc in props.items():
        v = o[k]
        if sc["type"] == "string" and not isinstance(v, str):
            return f"{k} 가 문자열 아님"
        if sc["type"] == "boolean" and not isinstance(v, bool):
            return f"{k} 가 참거짓 아님"
        if sc["type"] == "array" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            return f"{k} 가 문자열 목록 아님"
        if "enum" in sc and v not in sc["enum"]:
            return f"{k}={v!r} 허용값 아님"
    return None


def ingest(a) -> None:
    ex, tg, sp = load_excerpts(a.excerpts), load_targets(), prompt()
    d = agent_dir()
    man = read_json(d / "packets.json")
    if man["prompt_sha256"] != sha(sp):
        print("주의: pack 뒤 tagging-guide 프롬프트가 바뀌었습니다")
    have = read_results(a.results)
    n, bad, missing = 0, [], []
    for pid, pk in man["packets"].items():
        for it in pk:
            code, mode = it["code"], it["mode"]
            cid = cid_of(code, mode)
            if cid in have and have[cid]["output"] is not None and not a.force:
                continue
            f = d / "out" / f"{code}.json"
            if not f.exists():
                missing.append(f"{pid}:{code}")
                continue
            try:
                o = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as er:
                bad.append(f"{pid}:{code} json {er}")
                continue
            err = _check(o)
            if err:
                bad.append(f"{pid}:{code} {err}")
                continue
            e = ex[code]
            append(a.results, {
                "custom_id": cid, "stock_code": code, "corp_name": e["corp_name"], "mode": mode,
                "batch_id": f"agent:{pid}", "model": MODEL, "effort": None, "runner": "claude-code-subagent",
                "prompt_sha256": sha(sp), "input_sha256": sha(user_text(e, tg.get(code, {}), mode)),
                "stop_reason": None, "usage": None, "output": o, "error": None, "at": now_iso()})
            n += 1
    # 발췌로 판별한 뒤 전문으로 다시 본 회사(out/{code}.full.json → f_) — 발췌에 결산배당 조가 없던 경우
    for f in sorted((d / "out").glob("*.full.json")):
        code = f.name.split(".")[0]
        cid = cid_of(code, "full")
        if code not in ex or (cid in have and have[cid]["output"] is not None and not a.force):
            continue
        o = json.loads(f.read_text(encoding="utf-8"))
        err = _check(o)
        if err:
            bad.append(f"full:{code} {err}")
            continue
        e = ex[code]
        append(a.results, {
            "custom_id": cid, "stock_code": code, "corp_name": e["corp_name"], "mode": "full",
            "batch_id": "agent:full", "model": MODEL, "effort": None, "runner": "claude-code-subagent",
            "prompt_sha256": sha(sp), "input_sha256": sha(user_text(e, tg.get(code, {}), "full")),
            "stop_reason": None, "usage": None, "output": o, "error": None, "at": now_iso()})
        n += 1
    print(f"넣음 {n}건 · 형식 오류 {len(bad)}건 · 아직 없음 {len(missing)}건")
    for b in bad[:30]:
        print("  ", b)
    if missing:
        by = {}
        for m in missing:
            by.setdefault(m.split(":")[0], []).append(m.split(":")[1])
        print("  아직 없음:", {k: len(v) for k, v in by.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pilot", "submit", "status", "collect", "full", "pack", "ingest"])
    ap.add_argument("--codes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chars", type=int, default=100_000, help="pack: 묶음 하나의 입력 글자 수 상한")
    ap.add_argument("--force", action="store_true", help="ingest: 이미 결과가 있어도 다시 넣음")
    ap.add_argument("--exclude-ocr", action="store_true", help="pack: 정관 전문이 Windows OCR 글(charter_ocr.txt)인 회사는 건너뜀")
    ap.add_argument("--sfx", default="", help="다른 표일 때 파일 이름 접미어 (s09a 와 같게)")
    a = ap.parse_args()
    global SFX
    SFX = a.sfx
    p = paths(a.sfx)
    a.excerpts, a.results, a.batches = p["excerpts"], p["results"], p["batches"]
    codes = [x.strip() for x in a.codes.split(",") if x.strip()]
    if a.cmd in ("pilot", "full"):
        if not codes:
            raise SystemExit("--codes 를 주세요")
        sync_run(codes, a.cmd, a)
    else:
        {"submit": submit, "status": status, "collect": collect, "pack": pack, "ingest": ingest}[a.cmd](a)


if __name__ == "__main__":
    main()
