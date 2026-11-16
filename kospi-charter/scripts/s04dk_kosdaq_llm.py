"""s04dk 코스닥 스캔 쪽 → Claude Opus 5.5 전사 (Message Batches API) — s04d_charter_llm_ocr.py 를 그대로, 위치만 코스닥

  · 대상·모델·프롬프트·이미지 크기·배치 크기는 s04d 와 같다 (01 R5-9)
  · 요청 ID(p00001 …)는 정관 폴더 순서로 매겨지므로 시장마다 따로 매겨진다 → 코스닥 결과·배치 기록·보낸 JPEG 는
    data/raw/llm_ocr_kosdaq/ · data/interim/kosdaq/s04d_*.json 에 따로 둔다 (코스피 results.jsonl 과 섞이지 않게)
  · 비용이 든다 — submit 전에 pilot 으로 장당 토큰을 보고, 사용자 확인을 받고 보낸다

사용법 (s04d 와 같다)
  python -X utf8 scripts/s04dk_kosdaq_llm.py pilot --n 3
  python -X utf8 scripts/s04dk_kosdaq_llm.py submit | status | collect | organize
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kosdaq import KQ_CHARTER, KQ_INTERIM, KQ_LLM, patch  # noqa: E402
import s04d_charter_llm_ocr as s4d  # noqa: E402

patch(s4d, CHARTER=KQ_CHARTER, INTERIM=KQ_INTERIM, LLM=KQ_LLM,
      PAGES_F=KQ_INTERIM / "s04d_pages.json", BATCHES_F=KQ_INTERIM / "s04d_batches.json",
      RESULTS_F=KQ_LLM / "results.jsonl", INDEX_F=KQ_INTERIM / "s04d_llm.json")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pilot", "submit", "status", "collect", "organize"])
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--ids", nargs="*", default=[])
    a = ap.parse_args()
    {"pilot": lambda: s4d.cmd_pilot(a.n, a.ids), "submit": s4d.cmd_submit, "status": s4d.cmd_status,
     "collect": s4d.cmd_collect, "organize": s4d.organize}[a.cmd]()
