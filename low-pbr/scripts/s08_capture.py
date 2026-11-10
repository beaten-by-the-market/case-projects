"""s08 DART 재무상태표 '자본총계' 행 캡처 (Playwright, 프로젝트 .venv 에서 실행).

    .venv/Scripts/python scripts/s08_capture.py --set kind --rounds 2026.11
    .venv/Scripts/python scripts/s08_capture.py --set scope

대상: pr_fs_value 에 값이 있는 근거 보고서(s07) — 회차·기업 범위는 s07 과 같은 --set/--rounds.
한 장에 담는 것: 문서 상단의 단위 줄 · 표 머리(기수) · 자본 구간 몇 행 · 자본총계 행(주황 테두리·노란 바탕).
그 사이 자산·부채 행은 '⋯' 한 줄로 접는다 — 원문을 지우는 게 아니라 화면에서 숨기는 것이고, 링크를 열면 전체가 보인다.

출력: site/captures/<종목코드>/<접수번호>_<scope>.png · MySQL pr_capture (viewer_url·image_path)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _db import get_conn  # noqa: E402
from _rules import DART_VIEWER, ROOT, choose_filing, load_rounds, periodic_filings  # noqa: E402
from s07_dart_docs import target_codes  # noqa: E402

OUT = ROOT / "site" / "captures"
JS = r"""
(label) => {
  const clean = s => (s||'').replace(/[\s·ㆍ\.\-()（）\[\]]/g,'');
  const rows = [...document.querySelectorAll('tr')];
  const target = rows.find(r => r.cells.length > 1 && clean(r.cells[0].innerText) === label);
  if (!target) return null;
  const table = target.closest('table');
  const trs = [...table.querySelectorAll('tr')];
  const ti = trs.indexOf(target);
  const head = trs.filter(r => r.querySelector('th') && trs.indexOf(r) < ti);
  const hi = head.length ? trs.indexOf(head[head.length-1]) : -1;
  // 자본 구간 시작(‘자본’ 머리 행)부터 보여 준다. 없으면 대상 위 8행.
  let start = trs.findIndex((r,i) => i > hi && i < ti && clean(r.cells[0]?.innerText) === '자본');
  if (start < 0) start = Math.max(hi+1, ti-8);
  let folded = false;
  trs.forEach((r,i) => {
    if (i > hi && i < start) { r.style.display = 'none'; folded = true; }
    if (i > ti + 1) r.style.display = 'none';
  });
  if (folded) {
    const gap = document.createElement('tr');
    const td = document.createElement('td'); td.colSpan = 10; td.innerText = '⋯ 자산·부채 행 생략 (원문 링크에서 전체 확인) ⋯';
    td.style.cssText = 'text-align:center;color:#888;padding:6px;font-size:12px;background:#f7fafc';
    gap.appendChild(td); trs[start].parentNode.insertBefore(gap, trs[start]);
  }
  target.style.background = '#fff3c4'; target.style.outline = '3px solid #E67200';
  // 표 위의 단위 줄을 찾아 함께 담는다
  let unit = null, el = table.previousElementSibling, hop = 0;
  while (el && hop < 6) { if (/단위/.test(el.innerText||'')) { unit = el; break; } el = el.previousElementSibling; hop++; }
  const top = (unit || table).getBoundingClientRect().top + window.scrollY;
  const tb = table.getBoundingClientRect();
  const bottom = target.getBoundingClientRect().bottom + window.scrollY + 4;
  return {x: Math.max(0, tb.left - 6), y: Math.max(0, top - 6), w: tb.width + 12, h: bottom - top + 12};
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="kind")
    ap.add_argument("--rounds", default="2026.11")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    codes = target_codes(args.set)
    rounds = [r for r in load_rounds() if not args.rounds or r["round"] in args.rounds.split(",")]
    conn = get_conn()
    cur = conn.cursor()
    fil = periodic_filings(conn, codes)
    jobs = []
    for code in codes:
        for r in rounds:
            f = choose_filing(fil.get(code, []), r["base_date"])
            if f:
                jobs.append((code, f[0]))
    jobs = list(dict.fromkeys(jobs))
    cur.execute("SELECT rcept_no, toc_no FROM pr_capture")
    done = {(a, b) for a, b in cur.fetchall()}
    todo = []
    for code, rcp in jobs:
        cur.execute("SELECT v.fs_scope, v.toc_no, t.dcm_no, t.ele_id, t.offset, t.length, t.dtd "
                    "FROM pr_fs_value v JOIN pr_filing_toc t ON t.rcept_no=v.rcept_no AND t.toc_no=v.toc_no "
                    "WHERE v.rcept_no=%s AND v.item='equity_total'", (rcp,))
        for scope, toc, dcm, ele, off, ln, dtd in cur.fetchall():
            if (rcp, toc) not in done:
                todo.append((code, rcp, scope, toc, DART_VIEWER.format(rcp=rcp, dcm=dcm, ele=ele, off=off, len=ln, dtd=dtd)))
    todo = todo[: args.limit or None]
    print(f"캡처 대상 {len(todo)}장")
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1000, "height": 900}, device_scale_factor=2)
        for i, (code, rcp, scope, toc, url) in enumerate(todo, 1):
            try:
                pg.goto(url, wait_until="networkidle", timeout=60000)
                box = pg.evaluate(JS, "자본총계") or pg.evaluate(JS, "총자본")
                if not box:
                    fail.append((rcp, scope, "행 없음"))
                    continue
                path = OUT / code / f"{rcp}_{scope}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(path), clip={"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]},
                              full_page=True)
                cur.execute("REPLACE INTO pr_capture (rcept_no,toc_no,item,viewer_url,image_path) VALUES (%s,%s,%s,%s,%s)",
                            (rcp, toc, "equity_total", url, str(path.relative_to(ROOT / "site")).replace("\\", "/")))
                conn.commit()
            except Exception as e:
                fail.append((rcp, scope, str(e)[:80]))
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} 실패 {len(fail)}", flush=True)
        b.close()
    print(f"완료 {len(todo) - len(fail)}장 · 실패 {len(fail)}")
    for f in fail[:20]:
        print("  실패", f)


if __name__ == "__main__":
    main()
