"""s09a 정관에서 배당기준일 관련 대목만 넉넉하게 발췌 (LLM 판별 s09b 의 입력)

왜: 정관 전문은 1~6만 자라 825사 전체를 LLM 에 넣으면 비싸고, 판별에 필요한 곳은 몇 조뿐이다.
    사용자 지시(2026-11-16): "최대한 관대한 범위의 키워드로 해당 조항 앞뒤를 잘 추린 다음 LLM 에 돌린다."

방법 — 형식을 타지 않는 '앵커 + 앞뒤 창'
  · 정관 서식이 제각각이다: `제42조(이익배당)`, `제42조 | (이익배당)`, `제43조 이익배당`(괄호 없음), 머리 없이
    `제36조 이익배당금은…`, 한자 정관(`第39條 (配當)`), 싱가포르·케이맨 회사의 번호식(`16.11 회사는…`),
    줄바꿈이 없는 한 줄 원문. 그래서 조문을 나누지 않고 키워드 위치에서 앞뒤 창을 잘라 겹치면 합친다.
  · 앵커는 한글·한자를 함께 잡는다 (ANCHORS). 지급 대상 문구(배당을 받을·질권자·결산기말 현재…)는 앞 500·뒤 700자,
    조문 머리의 '배당'은 뒤로 1,100자, 흔한 '기준일'은 앞 300·뒤 500자.
  · 창의 시작은 앞쪽 300자 안의 가장 가까운 조문 머리(`제N조`·`第N條`)까지 당겨 조 제목이 들어가게 한다.
  · 지급 대상 문구 앞뒤 200자 안의 '제N조' 참조(예: "제13조 제1항에서 정한 날 현재의 주주")는 그 조의 머리를 찾아
    창을 하나 더 연다.
  · 발췌에 결산배당 지급 대상 문구(CORE)가 하나도 없으면 `weak=True` — s09b 가 정관 전문으로 다시 본다.

입력  data/interim/s09_targets.json  (없으면 data/final/kospi_charter.json 에서 만든다: 옆 세션이 s07 로 다시 쓸 수 있어
                                       시작할 때 한 번 떠 둔다)
      각 행의 charter_fulltext_txt (텍스트·Opus 전사·PDF 글자 중 그 정관의 전문)
출력  data/interim/s09a_excerpts.jsonl  행마다 {stock_code, corp_name, src, full_chars, excerpt_chars, n_windows,
                                         windows:[{start,end,anchors}], core_hits, weak, no_text, excerpt}

사용법
  python -X utf8 scripts/s09a_dividend_excerpt.py                # 전부 (코스피)
  python -X utf8 scripts/s09a_dividend_excerpt.py --show 005930  # 한 회사 발췌를 화면에
  python -X utf8 scripts/s09a_dividend_excerpt.py --sfx kosdaq --src data/final/kosdaq_charter.json
      다른 표: stock_code·corp_name·charter_fulltext_txt 열만 있으면 된다. --sfx 를 주면 s09a/b/c 의 모든 파일 이름 끝에
      `_{sfx}` 가 붙는다 (s09_targets_kosdaq.json, s09a_excerpts_kosdaq.jsonl … charter_dividend_record_date_kosdaq.json).
      s09b·s09c 에도 같은 --sfx 를 준다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, INTERIM, ROOT, now_iso, read_json, write_json  # noqa: E402

def paths(sfx: str = "") -> dict[str, Path]:
    """s09a/b/c 가 함께 쓰는 파일 경로. sfx 가 있으면 이름 끝에 _{sfx} (코스닥 등 다른 표)."""
    x = f"_{sfx}" if sfx else ""
    return {
        "targets": INTERIM / f"s09_targets{x}.json",
        "excerpts": INTERIM / f"s09a_excerpts{x}.jsonl",
        "results": INTERIM / f"s09b_results{x}.jsonl",
        "batches": INTERIM / f"s09b_batches{x}.json",
        "review": INTERIM / f"s09_review{x}.json",
        "summary": INTERIM / f"s09c_summary{x}.json",
        "out_json": FINAL / f"charter_dividend_record_date{x}.json",
        "out_csv": FINAL / f"charter_dividend_record_date{x}.csv",
    }


def interim_of(sfx: str, name: str) -> Path:
    """s09d~s10 의 중간 파일도 같은 접미어 규칙 — interim_of("kosdaq", "s09e_agm_results.json") → s09e_agm_results_kosdaq.json"""
    stem, ext = name.rsplit(".", 1)
    return INTERIM / (f"{stem}_{sfx}.{ext}" if sfx else name)

# ── 낱말 (한글 | 한자) ───────────────────────────────────────────────────────
배당 = r"(?:배\s*당|配\s*當)"
기준일 = r"(?:기\s*준\s*일|基\s*準\s*日)"
질권 = r"(?:질\s*권|質\s*權)"
주주명부 = r"(?:주\s*주\s*명\s*부|株\s*主\s*名\s*簿)"
결산기 = r"(?:결\s*산\s*기|決\s*算\s*期|결\s*산\s*일|決\s*算\s*日)"
사업연도 = r"(?:사\s*업\s*[연년]\s*도|事\s*業\s*年\s*度|영\s*업\s*[연년]\s*도|營\s*業\s*年\s*度|회\s*계\s*[연년]\s*도)"
말 = r"(?:말\s*일|末\s*日|말|末|종\s*료\s*일|終\s*了\s*日|최\s*종\s*일|最\s*終\s*日)"
이사회 = r"(?:이\s*사\s*회|理\s*事\s*會)"

받을 = r"(?:을|를)?\s*(?:받\s*(?:을|는)|수\s*령|受\s*領)"
현재 = r"(?:현\s*재|現\s*在)"
# 조문 머리 바로 뒤(괄호 제목 또는 본문 첫머리) 10자 안에 '배당'이 오는 곳: 제42조(이익배당) · 제42조 | (이익배당) ·
# 제43조 이익배당 ① · 제36조 이익배당금은 · 第 39 條 (配當) · 제39조 (이익배당 및 분기배당)
배당조머리 = (r"(?:제\s*\d{1,3}\s*조|第\s*\d{1,3}\s*條)(?:\s*의\s*\d{1,2})?[\s|(（【\[〔<]{0,4}"
          r"[^\n①②)）】\]〕>]{0,10}?" + 배당)

# (이름, 정규식, 앞, 뒤)
ANCHORS: list[tuple[str, str, int, int]] = [
    ("배당받을", 배당 + r"\s*" + 받을, 500, 700),
    ("배당기준일", 배당 + r"\s*" + 기준일, 500, 700),
    ("질권자", 질권 + r"\s*(?:자|者)", 500, 700),
    ("결산기말현재", r"(?:" + 결산기 + r"|" + 사업연도 + r")\s*" + 말 + r"[^\n]{0,12}?" + 현재, 500, 700),
    ("배당조문", 배당조머리, 100, 1100),
    ("최종주주명부", r"(?:최\s*종|最\s*終)\s*(?:의\s*)?" + 주주명부, 400, 600),
    ("기준일", 기준일, 300, 500),
    ("주주명부폐쇄", 주주명부 + r"\s*(?:의|를)?\s*(?:폐\s*쇄|閉\s*鎖|기\s*재\s*(?:변\s*경|변\s*동)|記\s*載\s*變\s*更)", 300, 600),
    ("중간분기배당", r"(?:중\s*간|中\s*間|분\s*기|分\s*期)\s*" + 배당, 300, 600),
]
# 결산배당을 받을 주주를 정하는 문구 — 이 가운데 하나도 없으면 발췌가 약하다
CORE = re.compile("|".join([
    배당 + r"\s*" + 받을,
    질권 + r"\s*(?:자|者)",
    r"(?:" + 결산기 + r"|" + 사업연도 + r")\s*" + 말 + r"\s*(?:현\s*재|現\s*在)",
    배당 + r"\s*" + 기준일,
    이사회 + r"[^\n]{0,40}?" + 기준일,
    r"권\s*리\s*를\s*행\s*사\s*할\s*주\s*주|權\s*利\s*를\s*行\s*使\s*할\s*株\s*主",
]))
HEAD = re.compile(r"(?:제\s*\d{1,3}\s*조|第\s*\d{1,3}\s*條)(?:\s*의\s*\d{1,2})?")
REF = re.compile(r"제\s*(\d{1,3})\s*조(?:\s*의\s*(\d{1,2}))?")
BACK_TO_HEAD = 300
MERGE_GAP = 150
MAX_EXCERPT = 16_000            # 이보다 길면 '기준일'만 걸린 창부터 뺀다
REF_NEAR = 200


def load_targets(src: Path | None, sfx: str = "") -> list[dict]:
    """대상 표를 한 번 떠 둔 것(s09_targets*.json)을 쓴다. --src 를 주면 그 표에서 다시 뜬다."""
    tf = paths(sfx)["targets"]
    if src is None and tf.exists():
        return read_json(tf)
    if src is None and sfx:
        raise SystemExit(f"--sfx {sfx} 는 처음 한 번 --src 로 대상 표를 주어야 합니다")
    rows = read_json(src or (FINAL / "kospi_charter.json"))
    keep = ["corp_code", "corp_name", "stock_code", "market", "sec_group", "settle_month", "fiscal_year",
            "rcept_no", "rcept_no_new", "charter_att_date", "charter_url", "charter_content_type",
            "charter_fulltext_txt", "agm_charter_amend_txt"]
    # 사업보고서가 없어 다른 문서(증권신고서·분할공시·KIND·홈페이지)에서 정관을 찾은 표(absent_charter.json)는 그 출처 열도 남기고,
    # 사업보고서 접수번호 자리에 정관 출처 문서의 접수번호를 둔다(사용자 지시 2026-11-17 — 근거문서로 구분해 본다)
    extra = ["charter_source_doc", "charter_source_rcept_no", "charter_source_nm", "charter_source_dt", "charter_source_url",
             "charter_viewer_url", "reason", "reason_code"]
    out = []
    for r in rows:      # 정관 전문이 없는 행(코스닥: PDF 를 하나도 못 읽은 4사 등)도 남긴다 — 발췌는 no_text, s09b 가 확인필요로 적는다
        t = {k: r.get(k) for k in keep}
        t.update({k: r.get(k) for k in extra if k in r})
        if not t.get("rcept_no") and "charter_source_doc" in r:
            t["rcept_no"] = r.get("charter_source_rcept_no") or r.get("charter_rcpNo") or ""
        out.append(t)
    write_json(tf, out)
    return out


def snap_start(t: str, s: int, hit: int) -> int:
    """창 시작을 앞쪽 BACK_TO_HEAD 자 안의 가장 가까운 조문 머리로 당긴다. 없으면 줄 머리로."""
    lo = max(0, hit - BACK_TO_HEAD)
    heads = [m.start() for m in HEAD.finditer(t, lo, hit)]
    if heads:
        return min(s, heads[-1])
    nl = t.rfind("\n", max(0, s - 200), s)
    return nl + 1 if nl >= 0 else s


def snap_end(t: str, e: int) -> int:
    nl = t.find("\n", e, min(len(t), e + 200))
    return nl if nl >= 0 else min(len(t), e)


def head_pos(t: str, no: str, sub: str | None) -> int | None:
    """'제N조(의M)' 머리 위치 — 본문 참조가 아니라 조문 머리로 보이는 것(뒤에 괄호·제목이 오는 것)의 첫 위치."""
    pat = r"제\s*" + no + r"\s*조" + (r"\s*의\s*" + sub if sub else r"(?!\s*의\s*\d)")
    for m in re.finditer(pat, t):
        nxt = t[m.end():m.end() + 6]
        if re.match(r"\s*(?:제\s*\d+\s*항|에|의\s*규정|에서|및|,|와|과|또는)", nxt):
            continue                            # 본문 속 참조
        return m.start()
    return None


def windows_for(t: str) -> list[dict]:
    wins = []
    for name, pat, before, after in ANCHORS:
        for m in re.finditer(pat, t):
            s = snap_start(t, max(0, m.start() - before), m.start())
            wins.append({"start": s, "end": snap_end(t, m.end() + after), "anchors": {name},
                         "strong": name != "기준일"})
    wins = merge(wins)
    # 지급 대상 문구 바로 옆(앞뒤 REF_NEAR 자)의 '제N조' 참조만 따라가 그 조의 머리에서 창을 하나 더 연다 (한 번만)
    # 예: "제1항의 배당은 제13조 제1항에서 정한 날 현재의 주주명부에 기재된 주주" → 제13조(기준일)
    extra = []
    covered = lambda p: any(w["start"] <= p < w["end"] for w in wins)  # noqa: E731
    for w in wins:
        for c in CORE.finditer(t, w["start"], w["end"]):
            for m in REF.finditer(t, max(w["start"], c.start() - REF_NEAR), min(w["end"], c.end() + REF_NEAR)):
                p = head_pos(t, m.group(1), m.group(2))
                if p is not None and not covered(p):
                    extra.append({"start": snap_start(t, p, p), "end": snap_end(t, p + 900), "anchors": {"참조조문"},
                                  "strong": True})
    wins = merge(wins + extra)
    total = sum(w["end"] - w["start"] for w in wins)
    if total > MAX_EXCERPT:                     # '기준일'만 걸린 창을 긴 것부터 뺀다
        for w in sorted([w for w in wins if not w["strong"]], key=lambda w: -(w["end"] - w["start"])):
            if total <= MAX_EXCERPT:
                break
            wins.remove(w)
            total -= w["end"] - w["start"]
    return wins


def merge(wins: list[dict]) -> list[dict]:
    out: list[dict] = []
    for w in sorted(wins, key=lambda w: w["start"]):
        if out and w["start"] <= out[-1]["end"] + MERGE_GAP:
            o = out[-1]
            o["end"] = max(o["end"], w["end"])
            o["anchors"] |= w["anchors"]
            o["strong"] = o["strong"] or w["strong"]
        else:
            out.append(dict(w, anchors=set(w["anchors"])))
    return out


def excerpt_of(row: dict) -> dict:
    p = ROOT / row["charter_fulltext_txt"] if row.get("charter_fulltext_txt") else None
    t = p.read_text(encoding="utf-8") if p and p.exists() else ""
    # 본문이 사실상 없는 정관 (예: Azure Information Protection 보호 PDF — 'Microsoft Azure' 안내문만 있다)
    body = re.sub(r"\[(?:PDF|쪽|이미지)[^\]]*\][^\n]*", "", t)
    no_text = len(re.sub(r"\s", "", body)) < 1500
    wins = [] if no_text else windows_for(t)
    parts = []
    for i, w in enumerate(wins, 1):
        # 머리말에 앵커 이름을 넣지 않는다 — LLM 에 쓸데없는 힌트가 되고 규칙 판별 정규식에도 걸린다 (앵커는 windows 에 남긴다)
        parts.append(f"[발췌 {i} · {w['start']:,}–{w['end']:,}자]\n" + t[w["start"]:w["end"]].strip())
    ex = "\n\n".join(parts)
    core = sorted({m.group(0) for m in CORE.finditer(ex)})
    return {
        "stock_code": row["stock_code"], "corp_name": row["corp_name"], "src": row["charter_fulltext_txt"],
        "full_chars": len(t), "excerpt_chars": len(ex), "n_windows": len(wins),
        "windows": [{"start": w["start"], "end": w["end"], "anchors": sorted(w["anchors"])} for w in wins],
        "core_hits": core[:20], "weak": (not no_text) and not core, "no_text": no_text, "excerpt": ex,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, help="대상 표 (기본: s09_targets.json ← kospi_charter.json)")
    ap.add_argument("--sfx", default="", help="다른 표일 때 파일 이름 접미어 (예: kosdaq)")
    ap.add_argument("--show", help="종목코드 하나의 발췌를 출력")
    a = ap.parse_args()
    a.out = paths(a.sfx)["excerpts"]
    rows = load_targets(a.src, a.sfx)
    if a.show:
        r = next(r for r in rows if r["stock_code"] == a.show)
        e = excerpt_of(r)
        print(json.dumps({k: v for k, v in e.items() if k != "excerpt"}, ensure_ascii=False, indent=1))
        print(e["excerpt"])
        return
    out = [excerpt_of(r) for r in rows]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for e in out:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    ex = sorted(e["excerpt_chars"] for e in out)
    full = sum(e["full_chars"] for e in out)
    print(f"{now_iso()} 발췌 {len(out)}사 → {a.out.relative_to(ROOT)}")
    print(f"  발췌 글자 합 {sum(ex):,} / 전문 {full:,} ({sum(ex) / max(full, 1):.0%}) · 중앙값 {ex[len(ex) // 2]:,} · "
          f"최대 {ex[-1]:,}")
    print(f"  본문 없음 {sum(e['no_text'] for e in out)} · 핵심 문구 없음(weak) {sum(e['weak'] for e in out)}")
    for e in out:
        if e["no_text"] or e["weak"]:
            print(f"    {e['stock_code']} {e['corp_name']} no_text={e['no_text']} weak={e['weak']} "
                  f"full={e['full_chars']:,}")


if __name__ == "__main__":
    main()
