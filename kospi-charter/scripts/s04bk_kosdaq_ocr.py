"""s04bk 코스닥 스캔 정관 → Windows 내장 OCR — s04b_charter_ocr.py 를 그대로 돌리고 위치만 코스닥

  · 대상: data/charter_kosdaq/*/*/meta.json 중 content_type 이 image·mixed 인 문서 (규칙·설정은 s04b 와 같다, 01 R5-7)
  · s04b_charter_ocr 의 CHARTER → data/charter_kosdaq, INTERIM → data/interim/kosdaq 로 바꿔 main() 을 부른다
    (s04b.main 은 공용 입력을 읽지 않고 CHARTER 를 훑어 INTERIM 에 색인만 쓴다)
  · 네트워크를 쓰지 않는다. s04k 가 받는 도중에 돌려도 meta.json 이 있는(받기가 끝난) 문서만 한다

출력  data/charter_kosdaq/…/charter_ocr.txt · ocr.json,  data/interim/kosdaq/s04b_ocr.json
실행  python -X utf8 scripts/s04bk_kosdaq_ocr.py [--limit N] [--force] [--workers 3]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kosdaq import KQ_CHARTER, KQ_INTERIM, patch  # noqa: E402
import s04b_charter_ocr as s4b  # noqa: E402

patch(s4b, CHARTER=KQ_CHARTER, INTERIM=KQ_INTERIM)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 할 일 가운데 앞 N개 문서만")
    ap.add_argument("--force", action="store_true", help="끝난 문서도 다시 OCR")
    ap.add_argument("--workers", type=int, default=3, help="동시에 OCR 할 쪽 수 (1~4)")
    a = ap.parse_args()
    s4b.main(a.limit, a.force, a.workers)
