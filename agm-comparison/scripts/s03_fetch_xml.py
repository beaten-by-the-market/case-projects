"""s03 표본 원문 → data/raw/xml/{rcept_no}/  (OpenDART document.xml ZIP 을 풀어 그대로 저장)

ZIP 안 파일 전부(본문 + 첨부)를 원래 이름으로 저장. 014(파일 없음)는 logs/s03_missing.txt.
이미 폴더가 있으면 건너뛴다.

사용법
    python scripts/s03_fetch_xml.py [--sample data/interim/sample.csv]
"""
import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT, Keys, Net  # noqa: E402

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
RAW = ROOT / "data/raw/xml"


def fetch(keys: Keys, rcp: str) -> str:
    d = RAW / rcp
    if d.exists() and any(d.iterdir()):
        return "cached"
    while True:
        r = Net.get(DOC_URL, params={"crtfc_key": keys.cur, "rcept_no": rcp}, timeout=180)
        if r.content[:2] == b"PK":
            break
        st = re.search(r"<status>(\d+)</status>", r.text[:600])
        st = st.group(1) if st else "?"
        if st == "020":
            keys.rotate()
            continue
        return f"status{st}"
    d.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            (d / Path(name).name).write_bytes(zf.read(name))
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=str(ROOT / "data/interim/sample.csv"))
    a = ap.parse_args()
    keys = Keys()
    rows = list(csv.DictReader(open(a.sample, encoding="utf-8-sig")))
    bad = []
    for i, r in enumerate(rows, 1):
        st = fetch(keys, r["rcept_no"])
        print(f"{i}/{len(rows)} {r['rcept_no']} {r['stratum']} {st}", flush=True)
        if st.startswith("status"):
            bad.append(f"{r['rcept_no']}\t{st}")
    (ROOT / "logs/s03_missing.txt").write_text("\n".join(bad), encoding="utf-8")


if __name__ == "__main__":
    main()
