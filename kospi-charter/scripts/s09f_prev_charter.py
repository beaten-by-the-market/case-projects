"""s09f 확인필요 회사 — 전년도 사업보고서 첨부 정관 + 그 뒤 소집공고 '정관의 변경' 으로 다시 판별할 재료 모으기

왜: 사용자 지시(2026-11-16) — 확인필요 3사(OCI·삼양패키징: 첨부 PDF 가 Azure Information Protection 으로 잠김,
    SK이터닉스: DART 정관 이미지가 제36조에서 끝남)는 특이사항 탭에 적고, 데이터는 **전년도 사업보고서**를 또 받아
    그 정관과 **그 사이 주주총회소집공고** 정보로 만든다.

단계 (네트워크 — 다른 DART 수집과 겹치지 않게 옆 세션과 시간을 맞춘 뒤에만)
  fetch   ① OpenDART list.json(corp_code, A001, 최종본, 2018-01-01 ~ 기준일) → 지금 쓴 사업보고서보다 앞선 것 중 가장 최근
          ② DART main.do 첨부 목록에서 '정관' → s04.fetch_doc 로 원문·이미지(정관 폴더 규칙 그대로 data/charter/…)
             PDF 첨부면 s04c 와 같은 방법으로 PDF 를 받아 글자층을 뽑는다(잠긴 PDF 면 그 전 해로 한 번 더)
          ③ OpenDART list.json(E006, 최종본, [전년도 보고서 원본 접수일, 기준일]) → document.xml → '정관의 변경' 절
             (s06 의 find_sections·section_text 로) → data/agm/{종목}_{회사}/{접수일}_{rcept_no}/정관의변경.txt
판별 (Anthropic API — s09b·s09d 와 같은 지침)
  tag     전년도 정관 → s09a 발췌 → s09b 프롬프트로 태그 · 소집공고 안건 → s09d 프롬프트로 '가결되면 태그'

출력  data/interim/s09f_prev.json  종목코드 → {prev_rcept_no, prev_report_nm, charter_*, charter_fulltext_txt,
                                    excerpt, tag 결과(output), notices: [{rcept_no, rcept_dt, txt, output(s09d)}]}

사용법
  python -X utf8 scripts/s09f_prev_charter.py fetch
  python -X utf8 scripts/s09f_prev_charter.py tag
  python -X utf8 scripts/s09f_prev_charter.py fetch --sfx kosdaq --codes 452200,228670,362320,067010   # 코스닥 정관 원문 없음 4사
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (AS_OF, DART_WEB, INTERIM, RAW, ROOT, Http, attach_docs_from_html, cached_text, dart_keys,  # noqa: E402
                     main_url, now_iso, read_json, write_json)

CODES = ["456040", "272550", "475150"]
OUT_F = INTERIM / "s09f_prev.json"
LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"


def od_list(http: Http, key: str, corp_code: str, ty: str, bgn: str) -> list[dict]:
    f = RAW / "opendart_prev" / f"{corp_code}_{ty}_{bgn}.json"
    if f.exists():
        return read_json(f)["list"]
    rows, page = [], 1
    while True:
        j = http.get(LIST_URL, params=dict(crtfc_key=key, corp_code=corp_code, bgn_de=bgn, end_de=AS_OF.strftime("%Y%m%d"),
                                           pblntf_detail_ty=ty, last_reprt_at="Y", page_no=page, page_count=100)).json()
        if j.get("status") == "013":
            break
        if j.get("status") != "000":
            raise SystemExit(f"OpenDART {j.get('status')} {j.get('message')}")
        rows += j["list"]
        if page >= j["total_page"]:
            break
        page += 1
    write_json(f, {"list": rows, "fetched_at": now_iso()})
    return rows


def charter_att(http: Http, rcp: str) -> list[dict]:
    from s04_charter import is_charter, parse_att_title
    html = cached_text(RAW / "dart_main_prev" / f"{rcp}.html", lambda: http.get(main_url(rcp)).text)
    out = []
    for i, a in enumerate(attach_docs_from_html(html)):
        a = dict(a, att_order=i, **parse_att_title(a["title"]))
        if is_charter(a["att_name"]):
            out.append(a)
    return out


def fetch_pdf_text(http: Http, d: Path) -> tuple[str, int, list[dict]]:
    """정관 폴더의 viewer html 에서 PDF 링크 → pdf/NNN.pdf 저장 → 글자층 (s04c 와 같은 꼴: [PDF n] / [쪽 n])."""
    from s04c_charter_pdf import PDF_LINK
    import fitz  # PyMuPDF (s04c 와 같다)
    parts, n, pdfs = [], 0, []
    for v in sorted(d.glob("viewer_*.html")):
        for m in PDF_LINK.finditer(v.read_text(encoding="utf-8")):
            url = m.group(1) if m.group(1).startswith("http") else DART_WEB + m.group(1)
            n += 1
            p = d / "pdf" / f"{n:03d}.pdf"
            if not p.exists():
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(http.get(url).content)
            pdfs.append({"file": p.relative_to(d).as_posix(), "src_url": url})
            parts.append(f"[PDF {n:03d}: {p.name}] → {p.relative_to(d).as_posix()}")
            with fitz.open(p) as doc:
                for k, pg in enumerate(doc, 1):
                    parts.append(f"[쪽 {k}]")
                    parts.append(pg.get_text())
    txt = "\n".join(parts)
    (d / "charter_pdf.txt").write_text(txt, encoding="utf-8")
    return txt, len(re.sub(r"\s", "", txt)), pdfs


def report_dividend_section(od: Http, key: str, rcp: str) -> dict:
    """사업보고서 원문(OpenDART document.xml)의 '6. 배당에 관한 사항' 가운데 '나. 배당관련 예측가능성 제공에 관한 사항' 글."""
    import s06_agm_xml as A
    f = RAW / "opendart_doc_prev" / f"{rcp}.zip"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(od.get(DOC_URL, params=dict(crtfc_key=key, rcept_no=rcp)).content)
    with zipfile.ZipFile(f) as z:
        s, _ = A.decode(z.read(sorted(z.namelist(), key=len)[0]))
    i = s.find("배당관련 예측가능성")
    if i < 0:
        return {"rcept_no": rcp, "text": None}
    j = s.find("(2) 배당액 확정일", i)
    seg = s[i:(j if j > 0 else i + 6000)]
    seg = re.sub(r"<(?:TR|P|BR)[^>]*>", "\n", seg, flags=re.I)
    seg = re.sub(r"<T[DH][^>]*>", " | ", seg, flags=re.I)
    seg = re.sub(r"<[^>]+>", "", seg)
    seg = "\n".join(re.sub(r"\s+", " ", ln).strip(" |") for ln in seg.splitlines())
    return {"rcept_no": rcp, "text": re.sub(r"\n{2,}", "\n", seg).strip()}


def fetch(sfx: str = "", codes: list[str] | None = None):
    from s04_charter import fetch_doc, pick
    import s06_agm_xml as A
    from s09a_dividend_excerpt import interim_of
    targets = {r["stock_code"]: r for r in read_json(interim_of(sfx, "s09_targets.json"))}
    if sfx:   # 다른 시장의 전년도 정관·소집공고는 그 시장 수집 폴더와 섞지 않는다 (코스닥: data/charter_kosdaq 은 옆 세션 몫)
        import s04_charter as S4
        S4.CHARTER = ROOT / "data" / f"charter_{sfx}_prev"
        A.AGM = ROOT / "data" / f"agm_{sfx}_prev"
    out = read_json(OUT_F) if OUT_F.exists() else {}
    key = dart_keys()[0]
    od = Http(delay=0.7)
    web, img = Http(delay=1.0), Http(delay=0.5)
    for code in codes or CODES:
        t = targets[code]
        rec = out.get(code, {})
        reps = sorted(od_list(od, key, t["corp_code"], "A001", "20180101"), key=lambda r: r["rcept_dt"], reverse=True)
        older = [r for r in reps if r["rcept_dt"] < t["rcept_no"][:8] and "사업보고서" in r["report_nm"]]
        print(f"{code} {t['corp_name']}: 사업보고서 {len(reps)}건, 지금 {t['rcept_no']} 앞 {len(older)}건")
        for r in older:                                    # 가장 최근부터 — 읽을 수 있는 정관이 나올 때까지
            cands = charter_att(web, r["rcept_no"])
            if not cands:
                print(f"   {r['rcept_no']} {r['report_nm']}: 정관 첨부 없음")
                continue
            a = pick(cands)
            doc = {"corp_code": t["corp_code"], "corp_name": t["corp_name"], "stock_code": code, "att_title": a["title"],
                   "att_date": a["att_date"], "rcpNo": a["rcpNo"], "dcmNo": a["dcmNo"], "att_url": a["url"]}
            m = fetch_doc(web, img, doc)
            d = ROOT / m["folder"]
            full = d / "charter.txt"
            chars = m["text_chars"]
            if m["content_type"] == "pdf":
                _, chars, pdfs = fetch_pdf_text(web, d)
                full = d / "charter_pdf.txt"
                m["pdfs"] = pdfs
            body = re.sub(r"\[(?:PDF|쪽|이미지)[^\]]*\][^\n]*", "", full.read_text(encoding="utf-8"))
            readable = len(re.sub(r"\s", "", body)) >= 1500 or m["n_images"] > 0
            print(f"   {r['rcept_no']} {r['report_nm']}: 정관 {m['content_type']} 글 {chars}자 이미지 {m['n_images']}장"
                  f" → {'사용' if readable else '읽을 수 없음, 그 전 해로'}")
            if not readable:
                continue
            rec.update(prev_rcept_no=r["rcept_no"], prev_rcept_dt=r["rcept_dt"], prev_report_nm=r["report_nm"],
                       charter_folder=m["folder"], charter_content_type=m["content_type"], charter_url=a["url"],
                       charter_att_date=a["att_date"], charter_n_images=m["n_images"],
                       charter_fulltext_txt=full.relative_to(ROOT).as_posix(), images=m["images"])
            break
        # 읽을 수 있는 정관이 어느 해에도 없으면(OCI — 해마다 잠긴 PDF) 지금 사업보고서 본문의 '배당관련 예측가능성' 표를
        # 근거로 쓰고(2024.12 서식 개정 뒤 사업보고서에 '정관상 배당기준일을 배당액 결정 이후로 정할 수 있는지 여부'가 있다),
        # 소집공고는 처음부터(2018~) 본다
        if not rec.get("charter_fulltext_txt"):
            rec["report_dividend_section"] = report_dividend_section(od, key, t["rcept_no"])
        # ③ 그 사이 소집공고 — 전년도 보고서 접수일부터 기준일까지 (정관이 없으면 2018-01-01 부터)
        bgn = rec.get("prev_rcept_dt") or ("20180101" if not rec.get("charter_fulltext_txt") else t["rcept_no"][:8])
        notes = []
        for n in od_list(od, key, t["corp_code"], "E006", bgn):
            ndir = A.notice_dir(n, code)
            txt_f = ndir / "정관의변경.txt"
            if not txt_f.exists():
                raw_f = RAW / "opendart_doc_prev" / f"{n['rcept_no']}.zip"
                if not raw_f.exists():
                    raw_f.parent.mkdir(parents=True, exist_ok=True)
                    raw_f.write_bytes(od.get(DOC_URL, params=dict(crtfc_key=key, rcept_no=n["rcept_no"])).content)
                with zipfile.ZipFile(io.BytesIO(raw_f.read_bytes())) as z:
                    name = sorted(z.namelist(), key=len)[0]
                    root, _ = A.parse(z.read(name))
                secs, _ = A.find_sections(root)
                if secs:
                    ndir.mkdir(parents=True, exist_ok=True)
                    txt_f.write_text("\n\n".join(A.section_text(s) for s in secs), encoding="utf-8")
            notes.append({"rcept_no": n["rcept_no"], "rcept_dt": n["rcept_dt"], "report_nm": n["report_nm"],
                          "txt": txt_f.relative_to(ROOT).as_posix() if txt_f.exists() else None})
        rec["notices"] = notes
        print(f"   소집공고 {len(notes)}건 (정관의 변경 절 {sum(1 for x in notes if x['txt'])}건) · {bgn} ~")
        out[code] = rec
        write_json(OUT_F, out)
    print(f"{now_iso()} DART 웹 요청 끝")


def transcribe():
    """스캔 이미지 정관(전년도)을 s04d 와 같은 요청으로 Opus 전사 → charter_llm.txt (charter.txt 틀, 이미지 줄 아래에 그 쪽 글)."""
    import s04d_charter_llm_ocr as O
    import s09b_dividend_tag_llm as L
    out = read_json(OUT_F)
    c = L.client()
    tot = 0.0
    for code, rec in out.items():
        if not rec.get("charter_folder") or not rec.get("charter_n_images"):
            continue
        d = ROOT / rec["charter_folder"]
        llm_f = d / "charter_llm.txt"
        if not llm_f.exists():
            pages = {}
            for im in rec["images"]:
                cid = f"prev_{code}_{Path(im['file']).stem}"
                msg = c.messages.create(**O.params(cid, {"folder": rec["charter_folder"], "kind": "img", "file": im["file"]}))
                pages[im["file"]] = next((b.text for b in msg.content if b.type == "text"), "").strip()
                tot += L.cost(L.usage_of(msg), batch=False)
            lines = []
            for ln in (d / "charter.txt").read_text(encoding="utf-8").splitlines():
                lines.append(ln)
                m = O._MARK.match(ln)
                if m and m.group(1) in pages:
                    lines.append(pages[m.group(1)])
            llm_f.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"{code}: {len(pages)}쪽 전사 → {llm_f.relative_to(ROOT)}")
        if rec.get("charter_fulltext_txt") != llm_f.relative_to(ROOT).as_posix():
            rec["charter_fulltext_txt"] = llm_f.relative_to(ROOT).as_posix()
            rec.pop("output", None)                        # 전사본으로 다시 판별
            for n in rec.get("notices") or []:
                n.pop("output", None)
    write_json(OUT_F, out)
    print(f"전사 ${tot:.2f} (동기 호출 값)")


def tag():
    import s09a_dividend_excerpt as X
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    out = read_json(OUT_F)
    targets = {r["stock_code"]: r for r in read_json(INTERIM / "s09_targets.json")}
    c = L.client()
    sp, sp_after = L.prompt(), D.after_prompt()
    tot = 0.0
    for code, rec in out.items():
        if not rec.get("charter_fulltext_txt"):
            # 어느 해 정관도 읽을 수 없는 회사 — 사업보고서 '배당관련 예측가능성' 표 + 소집공고 '정관의 변경' 안건으로 판별
            t = targets[code]
            sec = (rec.get("report_dividend_section") or {}).get("text") or ""
            parts = [f"회사: {t['corp_name']} ({code}) · 결산월 {t.get('settle_month')}",
                     "정관 원문을 읽을 수 없다(사업보고서마다 첨부 정관 PDF 가 Azure Information Protection 으로 잠겨 있다). "
                     "대신 아래 자료로 **지금 정관의 결산배당 기준일 규정**을 판별하라. 주주총회 안건은 원안대로 가결된 것으로 본다"
                     "(가결 여부는 따로 확인한다). '변경 후' 칸의 문구를 정관의 현재 문구로 보고, quotes 는 아래 글에서 글자 그대로 복사한다.",
                     "", f"<사업보고서 {t['rcept_no']} — 6. 배당에 관한 사항 · 나. 배당관련 예측가능성 제공에 관한 사항>", sec,
                     "</사업보고서>"]
            for n in sorted(rec.get("notices") or [], key=lambda x: x["rcept_dt"]):
                if n.get("txt"):
                    parts += ["", f"<정관의 변경 안건 · 소집공고 {n['rcept_dt']}_{n['rcept_no']}>",
                              D.amend_excerpt(n["txt"]), "</정관의 변경 안건>"]
            ut = "\n".join(parts)
            if not rec.get("output"):
                msg = c.messages.create(model=L.MODEL, max_tokens=L.MAX_TOKENS,
                                        system=[{"type": "text", "text": sp, "cache_control": {"type": "ephemeral"}}],
                                        messages=[{"role": "user", "content": ut}],
                                        output_config={"effort": L.EFFORT, "format": {"type": "json_schema", "schema": L.SCHEMA}})
                o, err = L.parse_message(msg)
                tot += L.cost(L.usage_of(msg), batch=False)
                rec.update(output=o, error=err, prompt_sha256=L.sha(sp), model=L.MODEL, at=now_iso(), mode="report+notices",
                           input_text=ut)
            o = rec["output"] or {}
            rec["quotes"] = o.get("quotes") or []
            print(f"{code} {t['corp_name']} (정관 없음 — 사업보고서 표 + 안건): {o.get('tag')} · {o.get('basis_article')} · "
                  f"{o.get('note', '')[:140]}")
            write_json(OUT_F, out)
            continue
        t = dict(targets[code], charter_fulltext_txt=rec["charter_fulltext_txt"],
                 charter_content_type=rec["charter_content_type"], charter_att_date=rec["charter_att_date"])
        e = X.excerpt_of(t)
        rec["excerpt_chars"] = e["excerpt_chars"]
        if not rec.get("output"):
            p = L.params(e, t, "excerpt", sp)
            msg = c.messages.create(**p)
            o, err = L.parse_message(msg)
            u = L.usage_of(msg)
            tot += L.cost(u, batch=False)
            rec.update(output=o, error=err, usage=u, prompt_sha256=L.sha(sp), model=L.MODEL, at=now_iso())
        o = rec["output"] or {}
        rec["quotes"] = o.get("quotes") or []
        print(f"{code} {t['corp_name']} 전년도 정관({rec['prev_report_nm']}): {o.get('tag')} · {o.get('basis_article')} · {o.get('note', '')[:100]}")
        base = o
        for n in rec.get("notices") or []:
            if not n.get("txt") or n.get("output"):
                continue
            txt = (ROOT / n["txt"]).read_text(encoding="utf-8")
            from s09c_dividend_build import DIVAMEND
            if not DIVAMEND.search(txt):
                n["output"] = {"changes_record_date": False, "tag_after": base.get("tag"), "quotes_after": [],
                               "interim_after": base.get("interim"), "quarterly_after": base.get("quarterly"),
                               "confidence": "높음", "note": "안건에 기준일 판별 문구 없음 (호출 안 함)"}
                continue
            ut = D.user_text({**t, "amend_hits": [n["txt"]]}, e, base)
            msg = c.messages.create(model=L.MODEL, max_tokens=L.MAX_TOKENS,
                                    system=[{"type": "text", "text": sp_after, "cache_control": {"type": "ephemeral"}}],
                                    messages=[{"role": "user", "content": ut}],
                                    output_config={"effort": L.EFFORT, "format": {"type": "json_schema", "schema": D.SCHEMA}})
            o2, err = L.parse_message(msg)
            tot += L.cost(L.usage_of(msg), batch=False)
            n.update(output=o2, error=err, prompt_sha256=L.sha(sp_after))
            if o2 and o2.get("changes_record_date"):
                base = {**base, "tag": o2["tag_after"]}
            print(f"   안건 {n['rcept_no']}: 바뀜 {(o2 or {}).get('changes_record_date')} → {(o2 or {}).get('tag_after')} · {(o2 or {}).get('note', '')[:90]}")
        write_json(OUT_F, out)
    print(f"합계 ${tot:.2f} (동기 호출 값)")


def ingest(sfx: str):
    """API 대신 서브에이전트가 판별한 결과(data/interim/s09f_agent_{sfx}/out/{code}.json = {output, notices}) 를 s09f 결과에 넣는다.
    스캔 정관은 서브에이전트가 같은 폴더에 charter_llm.txt(전사본)를 써 두었으면 그것을 정관 전문으로 쓴다."""
    import s09b_dividend_tag_llm as L
    import s09d_dividend_after_agm as D
    out = read_json(OUT_F)
    d = INTERIM / f"s09f_agent_{sfx}" / "out"
    for code, rec in out.items():
        f = d / f"{code}.json"
        if not f.exists():
            print(f"{code}: 서브에이전트 결과 없음")
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        err = L._check(j.get("output"))
        if err:
            raise SystemExit(f"{code} 판별 형식 오류: {err}")
        if rec.get("charter_folder"):
            llm_f = ROOT / rec["charter_folder"] / "charter_llm.txt"
            if rec.get("charter_n_images") and llm_f.exists():
                rec["charter_fulltext_txt"] = llm_f.relative_to(ROOT).as_posix()
        rec.update(output=j["output"], quotes=j["output"].get("quotes") or [], model=L.MODEL, runner="claude-code-subagent",
                   prompt_sha256=L.sha(L.prompt()), at=now_iso(), mode="report+notices" if not rec.get("charter_fulltext_txt") else "excerpt")
        for n in rec.get("notices") or []:
            o2 = (j.get("notices") or {}).get(n["rcept_no"])
            if o2 is not None:
                err = L._check(o2, D.SCHEMA)
                if err:
                    raise SystemExit(f"{code} 안건 {n['rcept_no']} 형식 오류: {err}")
                n.update(output=o2, prompt_sha256=L.sha(D.after_prompt()))
        print(f"{code}: {j['output']['tag']} · 안건 {sum(1 for n in rec.get('notices') or [] if n.get('output'))}건")
    write_json(OUT_F, out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "transcribe", "tag", "ingest"])
    ap.add_argument("--sfx", default="", help="코스닥 등 다른 표 — fetch 만 (판별은 API 대신 서브에이전트, docs/04 참고)")
    ap.add_argument("--codes", default="", help="fetch 대상 종목코드 (쉼표) — 없으면 CODES")
    a = ap.parse_args()
    if a.sfx:
        from s09a_dividend_excerpt import interim_of
        OUT_F = interim_of(a.sfx, "s09f_prev.json")
    if a.cmd == "fetch":
        fetch(a.sfx, [c.strip() for c in a.codes.split(",") if c.strip()] or None)
    elif a.cmd == "ingest":
        ingest(a.sfx or "kospi")
    else:
        if a.sfx:
            raise SystemExit("--sfx 는 fetch 만 — 판별은 서브에이전트로 (API 를 쓰지 않는다)")
        {"transcribe": transcribe, "tag": tag}[a.cmd]()
