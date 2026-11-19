"""s10c 배당기준일 변경 이력 — 이미 배포한 판과 견주어 판정이 바뀐 회사를 기록에 덧붙인다

왜: 사용자 지시(2026-11-19) — 페이지를 한 번 배포한 뒤 2024 · 2025년 소집공고를 더 반영해 판정이 바뀐 회사
    (2025 사업보고서에 개정 전 옛 정관이 붙어 있던 회사)를 따로 모아 보여 줘야 한다. 이미 배포한 상태에서 바꾸는 것이라
    변화 관리가 필요하다.

방법  배포본 = git 의 `--base`(기본 origin/main) 에 있는 site/dividend.js, 새 판 = 지금 site/dividend.js(s10 이 방금 만든 것).
      회사(시장 + 종목코드)마다 정관 태그(tag_current) · 근거 종류(basis_kind) · 신고 대조(filed_cmp)가 다르면 한 건으로 적는다.
      같은 반영일 · 같은 회사 건은 다시 돌리면 덮어쓴다(기록이 겹치지 않게). 앞선 반영일 기록은 그대로 둔다.
출력  data/final/dividend_changes.json  [{date, label, base, market, stock_code, corp_name, tag_before, tag_after,
      basis_before, basis_after, filed, filed_cmp_before, filed_cmp_after, kind, text, notice_url, notice_rcept_no,
      result_url, result_acptno, agm_date}]  → s10 이 dividend.js 'dividend_changes' 표로 싣는다 (웹페이지 '변경 이력' 탭)

    python -X utf8 scripts/s10_dividend_site.py            # 새 판 만들기
    python -X utf8 scripts/s10c_change_log.py --date 2026-11-19 --label "2024·2025년 소집공고 추가 반영"
    python -X utf8 scripts/s10_dividend_site.py            # 기록을 싣고 다시 만들기
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import FINAL, ROOT, read_json, write_json  # noqa: E402

SITE_JS = ROOT / "site" / "dividend.js"
LOG = FINAL / "dividend_changes.json"
KIND = {"early": "첨부 정관이 옛 판 (1~2년 앞선 주총에서 이미 바뀜)", "pre": "사업보고서보다 먼저 접수된 정기주총 안건",
        "post": "사업보고서 제출 뒤 주총 안건"}


def rows_of(js: str) -> dict[tuple[str, str], dict]:
    d = json.loads(js[js.index("{"):js.rindex("}") + 1])
    t = d["tables"]["dividend"]
    return {(r[t["cols"].index("market")], r[t["cols"].index("stock_code")]): dict(zip(t["cols"], r)) for r in t["rows"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main", help="배포본 git 참조")
    ap.add_argument("--date", required=True, help="반영일 (YYYY-MM-DD)")
    ap.add_argument("--label", required=True, help="이번 반영의 이름")
    a = ap.parse_args()
    rel = SITE_JS.relative_to(ROOT.parent).as_posix()
    base_hash = subprocess.run(["git", "rev-parse", "--short", a.base], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    old_js = subprocess.run(["git", "show", f"{a.base}:{rel}"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    old, new = rows_of(old_js), rows_of(SITE_JS.read_text(encoding="utf-8"))
    out = []
    for k, x in new.items():
        o = old.get(k)
        if not o:
            continue
        if (o["tag_current"], o["basis_kind"], o.get("filed_cmp")) == (x["tag_current"], x["basis_kind"], x.get("filed_cmp")):
            continue
        out.append({"date": a.date, "label": a.label, "base": base_hash, "market": x["market"], "stock_code": x["stock_code"],
                    "corp_name": x["corp_name"], "tag_before": o["tag_current"], "tag_after": x["tag_current"],
                    "basis_before": o["basis_kind"], "basis_after": x["basis_kind"], "filed": x.get("filed"),
                    "filed_cmp_before": o.get("filed_cmp"), "filed_cmp_after": x.get("filed_cmp"),
                    "kind": KIND.get(x.get("basis_notice_when") or "", "근거 바뀜") if o["tag_current"] != x["tag_current"] else "근거만 바뀜",
                    "text": x.get("note") or x.get("basis_note") or "",
                    "notice_url": x.get("basis_notice_url"), "notice_rcept_no": x.get("basis_notice_rcept_no"),
                    "result_url": x.get("basis_result_url"), "result_acptno": x.get("basis_result_acptno"), "agm_date": x.get("basis_agm_date")})
    gone = [k for k in old if k not in new]
    log = read_json(LOG) if LOG.exists() else []
    keep = [e for e in log if not (e["date"] == a.date and (e["market"], e["stock_code"]) in {(c["market"], c["stock_code"]) for c in out})]
    keep = [e for e in keep if not (e["date"] == a.date and e["label"] == a.label)] if out else keep
    log2 = sorted(keep + out, key=lambda e: (e["date"], e["market"] != "코스피", e["stock_code"]), reverse=False)
    write_json(LOG, log2)
    print(f"배포본 {a.base}({base_hash}) 대비 바뀐 회사 {len(out)} · 배포본에만 있던 행 {len(gone)} → {LOG.relative_to(ROOT)} (모두 {len(log2)}건)")
    for e in out:
        print(f"  {e['market']} {e['stock_code']} {e['corp_name']}: {e['tag_before']} → {e['tag_after']} · 신고 대조 {e['filed_cmp_before']} → {e['filed_cmp_after']} · {e['kind']}")


if __name__ == "__main__":
    main()
