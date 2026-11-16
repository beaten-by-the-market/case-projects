"""s04ck 코스닥 PDF 첨부 정관 → PDF 받기·글자 뽑기 — s04c_charter_pdf.py 를 그대로 돌리고 위치만 코스닥

  · 대상: data/charter_kosdaq/*/*/ 의 viewer_*.html 에 download.do …flNm=*.pdf 링크가 있는 문서 (규칙은 s04c 와 같다, 01 R5-8)
  · s04c_charter_pdf 의 CHARTER → data/charter_kosdaq, INTERIM → data/interim/kosdaq 로 바꿔 main() 을 부른다
  · DART 웹(download.do) — 호스트 단위 분당 80건. 다른 DART 수집과 동시에 돌리지 않는다
  · 글자층 없는 쪽을 그린 PNG 는 코스피와 같은 data/raw/pdf_pages/{첨부일자}_{dcmNo}/ (문서번호로 겹치지 않는다)
  · 끝에 clean_control() — PDF 글자층에서 나온 제어문자(\\x00-\\x08·\\x0b·\\x0c·\\x0e-\\x1f·\\x7f)를 charter_pdf.txt 에서 지우고
    글자 수(pdf.json·색인 total_chars)를 다시 센다. 셀레스트라 352770 PDF 는 띄어쓰기마다 '\\x01 ' 이 나와(4,689자)
    '제1조\\x01 (상호)' 처럼 문구 검색이 안 됐다(2026-11-16). 코스피 PDF 31개에는 없었다. 지운 수는 pdf.json control_chars_removed

출력  data/charter_kosdaq/…/pdf/ · charter_pdf.txt · pdf.json,  data/interim/kosdaq/s04c_pdf.json
실행  python -X utf8 scripts/s04ck_kosdaq_pdf.py [--limit N] [--force]
      python -X utf8 scripts/s04ck_kosdaq_pdf.py --clean-only      # 받기 없이 제어문자 지우기만 (네트워크 없음)
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, read_json, write_json  # noqa: E402
from _kosdaq import KQ_CHARTER, KQ_INTERIM, patch  # noqa: E402
import s04c_charter_pdf as s4c  # noqa: E402

patch(s4c, CHARTER=KQ_CHARTER, INTERIM=KQ_INTERIM)

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_control() -> int:
    """charter_pdf.txt 의 제어문자를 지우고 글자 수를 다시 센다 (s04c 와 같은 셈: '[' 로 시작하는 표시 줄 빼고 공백 제외)."""
    index_f = KQ_INTERIM / "s04c_pdf.json"
    index = read_json(index_f) if index_f.exists() else {}
    fixed = 0
    for tf in sorted(KQ_CHARTER.glob("*/*/charter_pdf.txt")):
        text = tf.read_text(encoding="utf-8")
        n = len(CTRL.findall(text))
        if not n:
            continue
        text = CTRL.sub("", text)
        tf.write_text(text, encoding="utf-8")
        d = tf.parent
        chars = len(re.sub(r"\s", "", "\n".join(x for x in text.splitlines() if not x.startswith("["))))
        pj = d / "pdf.json"
        if pj.exists():
            info = read_json(pj)
            info["control_chars_removed"] = info.get("control_chars_removed", 0) + n
            info["total_chars"] = chars
            write_json(pj, info)
        rel = d.relative_to(ROOT).as_posix()
        if rel in index:
            index[rel]["total_chars"] = chars
        fixed += 1
        print(f"  제어문자 {n:,}자 지움 · 글자 {chars:,} — {rel}", flush=True)
    if fixed:
        write_json(index_f, index)
    print(f"제어문자를 지운 PDF 글 {fixed}개")
    return fixed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 앞 N개 문서만")
    ap.add_argument("--clean-only", action="store_true", help="받기 없이 제어문자 지우기만")
    a = ap.parse_args()
    if not a.clean_only:
        s4c.main(a.force, a.limit)
    clean_control()
