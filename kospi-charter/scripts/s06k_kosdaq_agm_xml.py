"""s06k 코스닥 소집공고 XML 원문 → '정관의 변경' 절 찾기·저장 — s06_agm_xml.py 와 같은 규칙, 대상·저장 위치만 코스닥

  · 원문 받기·풀기, 절 찾기(코드 L0-0-2-2-0 → 없으면 제목), 절 텍스트, 주총 구분은 s06_agm_xml 의 함수를 그대로 쓴다
    (parse · find_sections · section_text · agm_kind · notice_dir). s06_agm_xml.AGM 만 data/agm_kosdaq 로 바꾼다
  · OpenDART document.xml — 0.5초 간격, 응답 대기 120초, 키 한도(020)면 다음 키

저장  data/agm_kosdaq/{종목코드}_{회사명}/{접수일}_{rcept_no}/  {rcept_no}.xml · 정관의변경.txt · meta.json
출력  data/interim/kosdaq/s06_agm_docs.json   rcept_no → meta
"""
import hashlib
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import INTERIM, ROOT, Http, dart_keys, now_iso, read_json, write_json  # noqa: E402
from _kosdaq import KQ_AGM, KQ_INTERIM, patch  # noqa: E402
import s06_agm_xml as s6  # noqa: E402

patch(s6, AGM=KQ_AGM)


def main():
    notices = {n["rcept_no"]: n for n in read_json(KQ_INTERIM / "s05_agm_notices.json")}
    amap = read_json(KQ_INTERIM / "s05_agm_map.json")
    reports = {r["rcept_no"]: r for r in read_json(INTERIM / "s01_reports.json")}
    market = read_json(INTERIM / "s02_market.json")
    code_of = {}
    for rno, v in amap.items():
        code = reports[rno]["stock_code"] or market[rno]["kind_code"]
        for n in v["notices"]:
            code_of[n] = code
    targets = sorted(code_of)
    print(f"소집공고 원문 {len(targets)}건", flush=True)

    out_f = KQ_INTERIM / "s06_agm_docs.json"
    out = read_json(out_f) if out_f.exists() else {}
    http, keys, ki = Http(delay=0.5, timeout=120), dart_keys(), 0
    for i, rno in enumerate(targets, 1):
        n = notices[rno]
        d = s6.notice_dir(n, code_of[rno])
        meta_f = d / "meta.json"
        if meta_f.exists():
            out[rno] = read_json(meta_f)
            continue
        d.mkdir(parents=True, exist_ok=True)
        files = sorted(d.glob("*.xml"))
        if not files:
            while True:
                r = http.get(s6.DOC_URL, params={"crtfc_key": keys[ki], "rcept_no": rno})
                if r.content[:2] == b"PK":
                    break
                st = re.search(rb"<status>(\d+)</status>", r.content)
                st = st.group(1).decode() if st else "?"
                if st == "020" and ki + 1 < len(keys):
                    ki += 1
                    continue
                break
            if r.content[:2] != b"PK":
                meta = {"rcept_no": rno, "error": f"document.xml status {st}", "folder": d.relative_to(ROOT).as_posix()}
                write_json(meta_f, meta)
                out[rno] = meta
                print(f"  원문 없음 {rno} {n['corp_name']} ({st})", flush=True)
                continue
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            for name in zf.namelist():
                (d / Path(name).name).write_bytes(zf.read(name))
            files = sorted(d.glob("*.xml"))

        main_f = next((f for f in files if f.stem == rno), max(files, key=lambda f: f.stat().st_size))
        root, enc = s6.parse(main_f.read_bytes())
        secs, how = s6.find_sections(root)
        if not secs and len(files) > 1:                 # 본문이 아닌 파일에 있을 때
            for f in files:
                if f == main_f:
                    continue
                r2, _ = s6.parse(f.read_bytes())
                secs, how = s6.find_sections(r2)
                if secs:
                    how += f"@{f.name}"
                    break
        txt_rel = None
        chars = 0
        if secs:
            body = "\n\n".join(s6.section_text(s) for s in secs)
            chars = len(re.sub(r"\s", "", body))
            (d / "정관의변경.txt").write_text(body, encoding="utf-8")
            txt_rel = (d / "정관의변경.txt").relative_to(ROOT).as_posix()
        meta = {"rcept_no": rno, "corp_code": n["corp_code"], "corp_name": n["corp_name"], "stock_code": code_of[rno],
                "report_nm": n["report_nm"], "rcept_dt": n["rcept_dt"],
                "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}",
                "agm_kind": s6.agm_kind(root), "has_charter_amend": bool(secs), "detect": how, "n_sections": len(secs),
                "section_chars": chars, "charter_amend_txt": txt_rel, "main_xml": main_f.name, "encoding": enc,
                "files": [{"name": f.name, "bytes": f.stat().st_size,
                           "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in files],
                "folder": d.relative_to(ROOT).as_posix(), "fetched_at": now_iso()}
        write_json(meta_f, meta)
        out[rno] = meta
        if i % 50 == 0:
            write_json(out_f, out)
            print(f"  {i}/{len(targets)}", flush=True)
    out = {k: v for k, v in out.items() if k in code_of}
    write_json(out_f, out)
    ok = [m for m in out.values() if "error" not in m]
    print(f"원문 {len(ok)}/{len(targets)} · 정관의 변경 있음 {sum(m['has_charter_amend'] for m in ok)} · "
          f"찾은 방법 {dict(Counter(m['detect'] or '-' for m in ok))} · 주총 구분 {dict(Counter(m['agm_kind'] or '?' for m in ok))}")
    print("  절 글자 수 0~199:", sum(1 for m in ok if m["has_charter_amend"] and m["section_chars"] < 200))


if __name__ == "__main__":
    main()
