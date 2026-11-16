"""s04d 스캔 정관 → Claude Opus 5.5 가 직접 읽어 옮기기 (Message Batches API, 일괄)

왜: s04b 의 Windows 내장 OCR 은 선명한 장은 약 99% 맞지만 작은 스캔은 80~93% 로 틀린다
    (ㅊ→ㅈ, 'ㅐ'→'0H', 동그라미 숫자 빠짐 …). 사용자 지시(2026-11-16): Opus 로 전부 다시 읽는다.
    Windows OCR 결과(charter_ocr.txt)는 그대로 두고, Opus 결과를 따로 charter_llm.txt 로 남긴다.

대상 (쪽 하나 = 요청 하나)
  · 스캔 이미지 정관(content_type image·mixed)의 이미지 전부 — meta.json images[] 중 받은 것 (DART 미서비스 1장 제외)
  · PDF 정관에서 글자층이 없어 글자 인식한 쪽 — charter_pdf.txt 의 '[쪽 N · OCR]' (s04c 가 그린 PNG, 없으면 다시 그림)

요청
  · 모델 claude-opus-5-5, Message Batches API(값 50%), effort low(전사는 깊은 추론이 필요 없다), max_tokens 8000
  · 이미지: 회색조 → 긴 변 2,576px·3.6MP 이하로 줄임(Opus 가 줄이지 않고 그대로 읽는 최대 크기) → JPEG 품질 85
    (data/raw/llm_ocr/img/{custom_id}.jpg 에 보낸 그대로 저장)
  · 배치 하나 180MB 이하로 나눠 보낸다(한도 256MB)
  · 프롬프트는 PROMPT — 보이는 글자만 그대로, 고치지·요약하지 않음, 표는 ' | ', 못 읽으면 [?]

정리 (문서 폴더)
  charter_llm.txt  이미지 정관: charter.txt 틀 그대로, 이미지 자리 줄 아래에 그 쪽의 Opus 전사
                   PDF 정관: charter_pdf.txt 틀 그대로, '[쪽 N · OCR]' 쪽만 Opus 전사로 바꾸고 '[쪽 N · Opus]' 로 표시
  llm_ocr.json     모델·배치 ID·쪽별 {file, sha256, input/output 토큰, stop_reason, chars}·합계·실패

사용법
  python -X utf8 scripts/s04d_charter_llm_ocr.py pilot --n 3   # 동기 호출로 몇 장 시험, 토큰·예상 비용
  python -X utf8 scripts/s04d_charter_llm_ocr.py submit        # 결과 없는 쪽 전부 배치로 보냄
  python -X utf8 scripts/s04d_charter_llm_ocr.py status        # 배치 진행 상황
  python -X utf8 scripts/s04d_charter_llm_ocr.py collect       # 끝난 배치 결과 받기 → 문서별 정리
키: .env 의 ANTHROPIC_API_KEY (git 제외)
"""
import argparse
import base64
import hashlib
import io
import json
import math
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import CHARTER, INTERIM, RAW, ROOT, load_env, now_iso, read_json, write_json  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "low"
MAX_TOKENS = 8000
LONG_EDGE, MAX_PIX = 2576, 3_600_000          # Opus 고해상도 한도(2,576px · 3.75MP) 안쪽
JPEG_Q = 85
BATCH_BYTES = 180_000_000
PRICE_IN, PRICE_OUT = 4.0 / 1e6, 20.0 / 1e6   # 일반 호출 $/토큰. 배치는 절반
LLM = RAW / "llm_ocr"
PAGES_F = INTERIM / "s04d_pages.json"
BATCHES_F = INTERIM / "s04d_batches.json"
RESULTS_F = LLM / "results.jsonl"            # custom_id 별 마지막 결과 (덧붙여 쓰고 읽을 때 마지막 것을 씀)
INDEX_F = INTERIM / "s04d_llm.json"

SYSTEM = "너는 문서 전사기다. 이미지에 보이는 글자를 그대로 옮겨 적고, 그 밖의 말은 하지 않는다."
PROMPT = """이 이미지는 한국 상장회사 정관(Articles of Incorporation)의 한 쪽을 스캔한 것이다. 보이는 글자를 빠짐없이 그대로 옮겨 적어라.
- 원문의 순서와 줄바꿈을 따른다(위에서 아래, 왼쪽에서 오른쪽). 문단 안에서 자동으로 줄이 바뀐 곳은 이어 써도 된다.
- 고치거나 요약하거나 설명을 붙이지 않는다. 맞춤법·띄어쓰기·숫자도 원문 그대로 쓴다.
- ①②③ 같은 원문자, 「」, ·, ※, 괄호 등 기호도 그대로 쓴다.
- 표는 행마다 한 줄로, 칸 사이를 ' | ' 로 잇는다.
- 쪽 번호·머리말·꼬리말·도장 안의 글자도 보이는 대로 쓴다. 로고·그림은 건너뛴다.
- 읽을 수 없는 글자는 [?] 로 쓴다. 글자가 없는 쪽이면 [빈 쪽] 한 줄만 쓴다.
- 전사한 본문만 출력한다."""
_MARK = re.compile(r"^\[이미지 [^\n]*?\] → (img/\S+?)\s*$")
_PDF_HEAD = re.compile(r"^\[PDF (\d{3}): .*\] → (pdf/\S+)\s*$")
_PDF_PAGE = re.compile(r"^\[쪽 (\d+)( · OCR)?\]\s*$")


def client():
    import anthropic
    key = load_env().get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 가 .env 에 없습니다")
    return anthropic.Anthropic(api_key=key, max_retries=4)


# ── 대상 쪽 목록 ─────────────────────────────────────────────────────────────
def pdf_ocr_pages(d: Path) -> list[tuple[str, int]]:
    f = d / "charter_pdf.txt"
    if not f.exists():
        return []
    cur, out = None, []
    for line in f.read_text(encoding="utf-8").splitlines():
        m = _PDF_HEAD.match(line)
        if m:
            cur = m.group(2)
            continue
        m = _PDF_PAGE.match(line)
        if m and m.group(2) and cur:
            out.append((cur, int(m.group(1))))
    return out


def build_pages() -> dict:
    """custom_id → 쪽. 정관 폴더·파일 순서로 번호를 매긴다(다시 만들어도 같은 번호)."""
    items = []
    for mf in sorted(CHARTER.glob("*/*/meta.json")):
        d, m = mf.parent, read_json(mf)
        folder = d.relative_to(ROOT).as_posix()
        if m.get("content_type") in ("image", "mixed"):
            for im in m.get("images", []):
                if "error" not in im and (d / im["file"]).exists():
                    items.append({"folder": folder, "kind": "img", "file": im["file"], "sha256": im.get("sha256")})
        for pdf, n in pdf_ocr_pages(d):
            items.append({"folder": folder, "kind": "pdf", "file": pdf, "page": n})
    return {f"p{i:05d}": it for i, it in enumerate(items, 1)}


def source_image(it: dict):
    from PIL import Image
    d = ROOT / it["folder"]
    if it["kind"] == "img":
        return Image.open(d / it["file"])
    png = RAW / "pdf_pages" / Path(it["folder"]).name / f"{Path(it['file']).stem}_p{it['page']:03d}.png"
    if not png.exists():
        import fitz
        with fitz.open(d / it["file"]) as doc:
            page = doc[it["page"] - 1]
            z = 3000 / max(page.rect.width, page.rect.height)
            png.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csGRAY).save(png)
    return Image.open(png)


def prepared_jpeg(cid: str, it: dict) -> bytes:
    """보낼 JPEG (회색조, 긴 변 2,576·3.6MP 이하). 한 번 만들면 data/raw/llm_ocr/img 에서 읽는다."""
    f = LLM / "img" / f"{cid}.jpg"
    if f.exists():
        return f.read_bytes()
    from PIL import Image, ImageOps
    with source_image(it) as im:
        g = ImageOps.grayscale(im)
    s = min(1.0, LONG_EDGE / max(g.size), math.sqrt(MAX_PIX / (g.width * g.height)))
    if s < 0.999:
        g = g.resize((max(1, int(g.width * s)), max(1, int(g.height * s))), Image.LANCZOS)
    buf = io.BytesIO()
    g.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(buf.getvalue())
    return buf.getvalue()


def params(cid: str, it: dict) -> dict:
    b64 = base64.standard_b64encode(prepared_jpeg(cid, it)).decode("ascii")
    return {"model": MODEL, "max_tokens": MAX_TOKENS, "system": SYSTEM,
            "output_config": {"effort": EFFORT},
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": PROMPT}]}]}


# ── 결과 저장 ───────────────────────────────────────────────────────────────
def load_results() -> dict:
    out = {}
    if RESULTS_F.exists():
        for line in RESULTS_F.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["custom_id"]] = r
    return out


def append_result(rec: dict):
    RESULTS_F.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_F, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def message_record(cid: str, msg, source: str) -> dict:
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    u = msg.usage
    return {"custom_id": cid, "ok": msg.stop_reason in ("end_turn", "stop_sequence") and bool(text),
            "text": text, "stop_reason": msg.stop_reason, "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens, "source": source, "at": now_iso()}


# ── 명령 ────────────────────────────────────────────────────────────────────
def cmd_pilot(n: int, ids: list[str]):
    pages = build_pages()
    write_json(PAGES_F, pages)
    if not ids:                                   # 작은 스캔·큰 스캔·PDF 쪽을 골고루
        def h(cid):
            it = pages[cid]
            return 0 if it["kind"] == "pdf" else 1
        pool = sorted(pages, key=lambda c: (h(c), c))
        step = max(1, len(pool) // n)
        ids = pool[::step][:n]
    c = client()
    tin = tout = 0
    for cid in ids:
        t = time.time()
        msg = c.messages.create(**params(cid, pages[cid]))
        rec = message_record(cid, msg, "pilot")
        append_result(rec)
        tin += rec["input_tokens"]
        tout += rec["output_tokens"]
        it = pages[cid]
        print(f"== {cid} {it['folder']} {it['file']}{' p' + str(it['page']) if it['kind'] == 'pdf' else ''} "
              f"· in {rec['input_tokens']} · out {rec['output_tokens']} · {rec['stop_reason']} · {time.time() - t:.1f}s")
        print(rec["text"][:600] + ("\n…" if len(rec["text"]) > 600 else ""))
    k = len(ids)
    est = len(pages) * (tin / k * PRICE_IN + tout / k * PRICE_OUT) * 0.5
    print(f"\n시험 {k}장 · 장당 입력 {tin / k:,.0f} · 출력 {tout / k:,.0f} 토큰"
          f"\n전체 {len(pages):,}장 배치 예상 비용 약 ${est:,.0f} (일반 호출이면 약 ${est * 2:,.0f})")


def cmd_submit():
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    pages = build_pages()
    write_json(PAGES_F, pages)
    done = {k for k, r in load_results().items() if r.get("ok")}
    batches = read_json(BATCHES_F) if BATCHES_F.exists() else []
    pending = {cid for b in batches if b.get("status") != "collected" for cid in b["cids"]}
    todo = [cid for cid in pages if cid not in done and cid not in pending]
    print(f"쪽 {len(pages):,} · 끝남 {len(done):,} · 진행 중 배치 {len(pending):,} · 보낼 것 {len(todo):,}", flush=True)
    c = client()
    chunk, size = [], 0

    def send(chunk):
        reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**p)) for cid, p in chunk]
        b = c.messages.batches.create(requests=reqs)
        batches.append({"id": b.id, "created_at": now_iso(), "n": len(chunk), "cids": [cid for cid, _ in chunk],
                        "status": b.processing_status})
        write_json(BATCHES_F, batches)
        print(f"  배치 {b.id} · {len(chunk)}건 · {size / 1e6:.0f}MB", flush=True)

    for i, cid in enumerate(todo, 1):
        p = params(cid, pages[cid])
        sz = len(p["messages"][0]["content"][0]["source"]["data"]) + 4000
        if chunk and size + sz > BATCH_BYTES:
            send(chunk)
            chunk, size = [], 0
        chunk.append((cid, p))
        size += sz
        if i % 500 == 0:
            print(f"  준비 {i}/{len(todo)}", flush=True)
    if chunk:
        send(chunk)
    print(f"배치 {sum(1 for b in batches if b.get('status') != 'collected')}개 진행 중")


def cmd_status():
    batches = read_json(BATCHES_F) if BATCHES_F.exists() else []
    c = client()
    for b in batches:
        if b.get("status") == "collected":
            continue
        r = c.messages.batches.retrieve(b["id"])
        rc = r.request_counts
        b["status"] = r.processing_status if b.get("status") != "collected" else b["status"]
        print(f"{b['id']} · {r.processing_status} · 처리 중 {rc.processing} · 성공 {rc.succeeded} · 오류 {rc.errored} · "
              f"만료 {rc.expired} · 취소 {rc.canceled}")
    write_json(BATCHES_F, batches)


def cmd_collect():
    batches = read_json(BATCHES_F) if BATCHES_F.exists() else []
    c = client()
    got = 0
    for b in batches:
        if b.get("status") == "collected":
            continue
        r = c.messages.batches.retrieve(b["id"])
        if r.processing_status != "ended":
            print(f"{b['id']} 아직 {r.processing_status}")
            continue
        for res in c.messages.batches.results(b["id"]):
            t = res.result.type
            if t == "succeeded":
                rec = message_record(res.custom_id, res.result.message, b["id"])
            else:
                err = getattr(res.result, "error", None)
                rec = {"custom_id": res.custom_id, "ok": False, "text": "", "stop_reason": t,
                       "error": str(getattr(err, "error", err))[:300] if err else t, "source": b["id"], "at": now_iso()}
            append_result(rec)
            got += 1
        b["status"] = "collected"
        b["collected_at"] = now_iso()
        write_json(BATCHES_F, batches)
        print(f"{b['id']} 결과 받음", flush=True)
    print(f"이번에 받은 결과 {got:,}건")
    organize()


def organize():
    """결과 → 문서별 charter_llm.txt · llm_ocr.json · 색인."""
    pages = read_json(PAGES_F) if PAGES_F.exists() else build_pages()
    res = load_results()
    by_doc = {}
    for cid, it in pages.items():
        by_doc.setdefault(it["folder"], []).append((cid, it))
    index = {}
    for folder, items in sorted(by_doc.items()):
        d = ROOT / folder
        recs = {cid: res.get(cid) for cid, _ in items}
        if not any(r and r.get("ok") for r in recs.values()):
            continue
        img_text = {it["file"]: (cid, recs[cid]) for cid, it in items if it["kind"] == "img"}
        pdf_text = {(it["file"], it["page"]): (cid, recs[cid]) for cid, it in items if it["kind"] == "pdf"}

        def body(rec):
            if rec and rec.get("ok"):
                return rec["text"].splitlines()
            return [f"[Opus 실패: {rec.get('error') or rec.get('stop_reason') if rec else '아직 결과 없음'}]"]

        out, used = [], set()
        if pdf_text:                                   # PDF 정관
            cur, skip = None, False
            for line in (d / "charter_pdf.txt").read_text(encoding="utf-8").splitlines():
                m = _PDF_HEAD.match(line)
                if m:
                    cur, skip = m.group(2), False
                    out.append(line)
                    continue
                m = _PDF_PAGE.match(line)
                if m:
                    key = (cur, int(m.group(1)))
                    if m.group(2) and key in pdf_text:
                        out.append(f"[쪽 {m.group(1)} · Opus]")
                        out += body(pdf_text[key][1])
                        used.add(key)
                        skip = True
                    else:
                        out.append(line)
                        skip = False
                    continue
                if not skip:
                    out.append(line)
        else:                                          # 이미지 정관
            for line in (d / "charter.txt").read_text(encoding="utf-8").splitlines():
                out.append(line)
                m = _MARK.match(line)
                if m and m.group(1) in img_text and m.group(1) not in used:
                    out += body(img_text[m.group(1)][1])
                    used.add(m.group(1))
            for f, (cid, rec) in img_text.items():
                if f not in used:
                    out.append(f"[이미지 {Path(f).stem}: charter.txt 에 표시 줄 없음] → {f}")
                    out += body(rec)
        text = "\n".join(out).rstrip() + "\n"
        (d / "charter_llm.txt").write_text(text, encoding="utf-8")
        page_recs = []
        for cid, it in items:
            r = recs[cid] or {}
            page_recs.append({"custom_id": cid, "file": it["file"], "page": it.get("page"), "sha256": it.get("sha256"),
                              "ok": bool(r.get("ok")), "stop_reason": r.get("stop_reason"),
                              "input_tokens": r.get("input_tokens"), "output_tokens": r.get("output_tokens"),
                              "chars": len(re.sub(r"\s", "", r.get("text") or "")), "batch": r.get("source")})
        chars = sum(p["chars"] for p in page_recs)
        errors = [p for p in page_recs if not p["ok"]]
        write_json(d / "llm_ocr.json", {"model": MODEL, "effort": EFFORT, "prompt_sha256": hashlib.sha256(
            (SYSTEM + PROMPT).encode()).hexdigest()[:16], "image": {"long_edge": LONG_EDGE, "max_pixels": MAX_PIX,
            "gray": True, "jpeg_quality": JPEG_Q}, "pages": page_recs, "total_chars": chars,
            "n_errors": len(errors), "created_at": now_iso()})
        index[folder] = {"llm_txt": f"{folder}/charter_llm.txt", "pages": len(items), "total_chars": chars,
                         "errors": len(errors)}
    write_json(INDEX_F, index)
    tin = sum((r or {}).get("input_tokens") or 0 for r in res.values())
    tout = sum((r or {}).get("output_tokens") or 0 for r in res.values())
    print(f"정리: 문서 {len(index)}개 · 쪽 {sum(v['pages'] for v in index.values()):,} · "
          f"글자 {sum(v['total_chars'] for v in index.values()):,} · 실패 쪽 {sum(v['errors'] for v in index.values())}"
          f" · 누적 토큰 입력 {tin:,} · 출력 {tout:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pilot", "submit", "status", "collect", "organize"])
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--ids", nargs="*", default=[])
    a = ap.parse_args()
    {"pilot": lambda: cmd_pilot(a.n, a.ids), "submit": cmd_submit, "status": cmd_status,
     "collect": cmd_collect, "organize": organize}[a.cmd]()
