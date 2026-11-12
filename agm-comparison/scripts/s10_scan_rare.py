"""s10 소집공고 스캔 — 미관찰 안건유형(7·16·17호) 찾기

filings_e006.csv 중 아직 받지 않은 공고를 document.xml 로 받아 메모리에서 안건유형 코드(L0-0-2-N-0)만 뽑는다.
  - 모든 공고의 코드 목록 → data/interim/scan_rare.csv (이어받기: 이미 적힌 rcept_no 는 건너뜀)
  - 7·16·17호가 나온 공고만 원문 저장 → data/raw/xml/{rcept_no}/
  - eng17: 17호 절 제목의 영문(ENG 속성, 서식 6.0~) — 있으면 기록

기본(인자 없음): 원본 공고 중 2~3월 외 접수분 전부(1차 스캔, 7·16·17호 첫 관찰).
  --since YYYYMMDD  이 날짜 이후 접수분만
  --corr            정정공고도 포함
  --peak            2~3월 접수분도 포함
  --stop-eng17      영문 제목이 붙은 17호를 찾으면 멈춤
2차 스캔(17호 영문 제목 찾기): --since 20250101 --corr --peak --stop-eng17
  순서: 정정공고 → 원본, 각각 최근 접수부터.
OpenDART 는 IP 단위로 막으므로 다른 수집과 동시에 돌리지 말 것.
"""
import argparse
import csv
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT, Keys, Net  # noqa: E402

DOC = "https://opendart.fss.or.kr/api/document.xml"
RARE = {7, 16, 17}
CODE = re.compile(rb'AASSOCNOTE="L0-0-2-(\d+)-0"')
ENG17 = re.compile(rb'<TITLE[^>]*AASSOCNOTE="L0-0-2-17-0"[^>]*>')
OUT = ROOT / "data/interim/scan_rare.csv"
FIELDS = ["rcept_no", "rcept_dt", "corp_name", "corp_cls", "report_nm", "status", "codes", "rare", "eng17"]


def get(keys, rcp):
    """네트워크 끊김(DNS 실패 등)은 1분씩 기다리며 10번까지 다시."""
    for k in range(10):
        try:
            return Net.get(DOC, params={"crtfc_key": keys.cur, "rcept_no": rcp}, timeout=120)
        except requests.RequestException:
            if k == 9:
                raise
            time.sleep(60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--corr", action="store_true")
    ap.add_argument("--peak", action="store_true")
    ap.add_argument("--stop-eng17", action="store_true")
    a = ap.parse_args()

    keys = Keys()
    rows = list(csv.DictReader((ROOT / "data/interim/filings_e006.csv").open(encoding="utf-8-sig")))
    have = {p.name for p in (ROOT / "data/raw/xml").iterdir()}
    done = set()
    if OUT.exists():
        old = list(csv.DictReader(OUT.open(encoding="utf-8-sig")))
        done = {r["rcept_no"] for r in old}
        if old and "eng17" not in old[0]:          # 1차 스캔 파일(열 적음) → 새 열 맞춰 다시 쓰기
            with OUT.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerows({k: r.get(k, "") for k in FIELDS} for r in old)
    todo = [r for r in rows if r["rcept_no"] not in have and r["rcept_no"] not in done
            and r["rcept_dt"] >= a.since
            and (a.corr or not r["report_nm"].startswith("["))
            and (a.peak or r["rcept_dt"][4:6] not in ("02", "03"))]
    todo.sort(key=lambda r: r["rcept_no"], reverse=True)
    todo.sort(key=lambda r: not r["report_nm"].startswith("["))   # 정정공고 먼저(안정 정렬 → 각 묶음 안은 최근순)
    new = not OUT.exists()
    f = OUT.open("a", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    print("todo", len(todo), flush=True)
    hits = 0
    for i, r in enumerate(todo, 1):
        while True:
            resp = get(keys, r["rcept_no"])
            if resp.content[:2] == b"PK":
                st = "ok"
                break
            m = re.search(r"<status>(\d+)</status>", resp.text[:600])
            st = f"status{m.group(1) if m else '?'}"
            if st == "status020":
                keys.rotate()
                continue
            break
        codes, eng = [], ""
        if st == "ok":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                blobs = {n: zf.read(n) for n in zf.namelist()}
            codes = sorted({int(c) for b in blobs.values() for c in CODE.findall(b)})
            for b in blobs.values():
                for t in ENG17.findall(b):
                    m = re.search(rb'ENG="([^"]*)"', t)
                    if m and m.group(1).strip():
                        eng = m.group(1).decode("utf-8", "ignore")
            if RARE & set(codes):
                d = ROOT / "data/raw/xml" / r["rcept_no"]
                d.mkdir(parents=True, exist_ok=True)
                for n, b in blobs.items():
                    (d / Path(n).name).write_bytes(b)
                hits += 1
        rare = sorted(RARE & set(codes))
        w.writerow({"rcept_no": r["rcept_no"], "rcept_dt": r["rcept_dt"], "corp_name": r["corp_name"],
                    "corp_cls": r["corp_cls"], "report_nm": r["report_nm"], "status": st,
                    "codes": " ".join(map(str, codes)), "rare": " ".join(map(str, rare)), "eng17": eng})
        f.flush()
        if rare or i % 200 == 0:
            print(i, len(todo), r["rcept_dt"], r["corp_name"], r["report_nm"][:12], "rare", rare, "eng17", eng,
                  "hits", hits, flush=True)
        if a.stop_eng17 and eng:
            print("FOUND eng17", r["rcept_no"], r["corp_name"], eng, flush=True)
            break
    f.close()
    print("done", i if todo else 0, "/", len(todo), "hits", hits)


if __name__ == "__main__":
    main()
