"""s06 소집공고 XML 원문 내려받기 → '정관의 변경' 절 찾기·저장

1) 원문 — OpenDART document.xml(rcept_no) ZIP 을 풀어 그대로 저장
     data/agm/{종목코드}_{회사명}/{접수일}_{rcept_no}/{rcept_no}.xml (ZIP 안 파일 이름 그대로, 여럿이면 모두)
2) 찾기 — 'III. 경영참고사항 › 2. 주주총회 목적사항별 기재사항' 아래 안건유형 절 중 '정관의 변경'
     ① 코드: TITLE@AASSOCNOTE="L0-0-2-2-0" (증권발행공시규정 제3-15조③ 2호 — agm-comparison/docs/01-DART코드정리.md)
     ② 코드가 없으면: '목적사항별 기재사항' 제목 뒤에 나오는 TITLE 중 글자가 '정관의 변경'(□·띄어쓰기·'일부' 허용)인 것
     절 = 그 TITLE 의 부모 SECTION 요소 전체
     ③ 둘 다 없으면 글로 — '정관의 변경' 제목을 일반 글로 적어 다른 절 안에 들어간 경우 · 본문 끝 별첨 대비표 (text_fallback, 2026-11-19)
3) 저장 — 같은 폴더에
     정관의변경.txt   절 텍스트 (문단 한 줄, 표는 행마다 ' | ', DART 줄바꿈 &cr; → 줄바꿈)
     meta.json        출처·파일 목록(sha256)·주총 구분(정기/임시)·정관변경 절 유무·찾은 방법·글자 수

출력  data/interim/s06_agm_docs.json   rcept_no → meta
"""
import hashlib
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, Http, dart_keys, now_iso, read_json, safe_name, write_json  # noqa: E402
from _common import INTERIM  # noqa: E402

DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
AGM = ROOT / "data" / "agm"
CODE = "L0-0-2-2-0"
WS = re.compile(r"[ \t\r\f\v]+")
TITLE_RX = re.compile(r"^\s*(?:[□■○●◎※\-]|\d+[.)]|[가-하][.)]|\(\d+\))?\s*정관\s*의?\s*(일부\s*)?(변경|개정)")
CR = ""                                   # &cr; 자리표시 (파싱 뒤 줄바꿈으로)


def notice_dir(n: dict, code: str) -> Path:
    return AGM / f"{code or 'NOCODE'}_{safe_name(n['corp_name'])}" / f"{n['rcept_dt']}_{n['rcept_no']}"


def decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace"), "cp949-replace"


def parse(raw: bytes):
    s, enc = decode(raw)
    s = s.lstrip("﻿").lstrip()
    s = re.sub(r"^<\?xml[^>]*\?>", "", s)
    s = s.replace("&cr;", CR)
    root = etree.fromstring(s.encode("utf-8"), etree.XMLParser(recover=True, huge_tree=True))
    return root, enc


def el_text(el) -> str:
    t = "".join(el.itertext()).replace(CR, "\n").replace("\xa0", " ")
    return "\n".join(WS.sub(" ", x).strip() for x in t.split("\n") if x.strip())


def section_text(sec) -> str:
    """절 → 텍스트. 표는 행마다 칸을 ' | ' 로, 칸 안 줄바꿈은 ' / ' 로."""
    lines = []

    def walk(node):
        for ch in node:
            if not isinstance(ch.tag, str):
                continue
            tag = ch.tag.upper()
            if tag == "TABLE":
                for tr in ch.iter("TR"):
                    cells = [el_text(c).replace("\n", " / ") for c in tr if isinstance(c.tag, str)
                             and c.tag.upper() in ("TD", "TH", "TE", "TU")]
                    if any(cells):
                        lines.append(" | ".join(cells))
                lines.append("")
            elif tag in ("TITLE", "P", "SPAN", "A"):
                t = el_text(ch)
                if t:
                    lines.append(t)
            elif tag in ("COLGROUP", "COL", "FILENAME", "IMAGE", "IMG"):
                continue
            else:
                walk(ch)

    walk(sec)
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


def find_sections(root) -> tuple[list, str]:
    titles = [t for t in root.iter("TITLE")]
    coded = [t for t in titles if t.get("AASSOCNOTE") == CODE]
    if coded:
        return [t.getparent() for t in coded], "code"
    after, hits = False, []
    for t in titles:
        txt = el_text(t).replace("\n", " ")
        if "목적사항별" in txt and "기재사항" in txt:
            after = True
            continue
        if after and TITLE_RX.match(txt):
            hits.append(t.getparent())
    if hits:
        return hits, "title"
    fb = text_fallback(root)
    return ([fb], "text") if fb is not None else ([], "")


# ③ 코드 · 제목이 없으면 글로 (2026-11-19, 사용자 질문 "정관 변경을 다른 태그 · 기타에 넣은 곳은 없나") — '□ 정관의 변경' 제목을 TITLE 이
#    아닌 글로 적어 '재무제표의 승인' 절 안에 들어가 있거나(대동금속 · 나인앤컴퍼니 · 모티브링크 · 팜스빌 · LB세미콘), 공고 본문 끝에 별첨 대비표로
#    붙인 경우(이오테크닉스). 시작: DART 표준 문구 '가. 집중투표 배제를 위한 정관의 변경' · '그 외의 정관변경에 관한 건', 또는 '정관 (일부) 변경의 건'
#    바로 뒤(블록 3개 안)에 대비표 머리(현행 · 변경전). 끝: 다음 안건 머리(□ … · 다른 L0-0-2-* 제목 · 의안 : …) · 'IV. 사업보고서' · '※ 참고사항'.
#    그 사이 원문 블록(문단 · 표)을 모은 가짜 절을 돌려줘 section_text 가 표를 ' | ' 로 펴게 한다. 조 머리(제N조)가 없으면 버린다.
FB_START1 = re.compile(r"집\s*중\s*투\s*표\s*배\s*제\s*를\s*위\s*한\s*정\s*관|그\s*외\s*의\s*정\s*관\s*변\s*경\s*에\s*관\s*한\s*건")
FB_START2 = re.compile(r"정\s*관\s*(?:의\s*)?(?:일\s*부\s*)?(?:변\s*경|개\s*정)\s*(?:의\s*)?(?:건|안)")
FB_TABLE = re.compile(r"현\s*행|변\s*경\s*전")
FB_END = re.compile(r"^\s*[□■]\s*(?!\s*(?:제\s*\d+\s*호\s*의\s*안\s*[:：]?\s*)?정\s*관)|^\s*(?:IV|Ⅳ)\s*\.\s*사\s*업\s*보\s*고\s*서|^\s*※\s*참\s*고\s*사\s*항|"
                    r"^\s*(?:제\s*\d+\s*(?:-\s*\d+\s*)?호\s*)?의\s*안\s*[:：](?!\s*정\s*관)|^\s*\[\s*제\s*\d+\s*호\s*의\s*안\s*\](?!\s*정\s*관)")
FB_HEAD = re.compile(r"(?:제|第)\s*\d{1,3}\s*(?:조|條)")


def _blocks(root) -> list:
    """원문 블록(문단 · 표 · 제목) — 표나 문단 안에 든 것은 빼고 문서 순서대로."""
    out = []
    for el in root.iter():
        if not isinstance(el.tag, str) or el.tag.upper() not in ("P", "TABLE", "TITLE"):
            continue
        if any(isinstance(a.tag, str) and a.tag.upper() in ("TABLE", "P") for a in el.iterancestors()):
            continue
        out.append(el)
    return out


def text_fallback(root):
    import copy
    bl = _blocks(root)
    tx = [el_text(b).replace("\n", " ") for b in bl]
    i0 = next((k for k, t in enumerate(tx) if "목적사항별" in t and "기재사항" in t), 0)
    start = None
    for lo in (i0, 0):                       # 목적사항 뒤 먼저, 없으면(본문 끝 별첨) 처음부터
        for k in range(lo, len(bl)):
            if FB_START1.search(tx[k]) or (FB_START2.search(tx[k]) and FB_TABLE.search(" ".join(tx[k:k + 4]))):
                start = k
                break
        if start is not None:
            break
    if start is None:
        return None
    end = len(bl)
    for k in range(start + 1, min(len(bl), start + 600)):
        code = bl[k].get("AASSOCNOTE") or "" if bl[k].tag.upper() == "TITLE" else ""
        if FB_END.search(tx[k]) or (code.startswith("L0-0-2-") and code != CODE) or code.startswith("D-4"):
            end = k
            break
    if not FB_HEAD.search(" ".join(tx[start:end])):
        return None
    sec = etree.Element("SECTION-FALLBACK")
    for b in bl[start:end]:
        sec.append(copy.deepcopy(b))
    return sec


_KIND_TITLE = re.compile(r"소집\s*공고\s*\(([^)]{0,30}?)(정기|임시|종류)")   # 주주총회 소집공고 (제10기 임시주주총회)·(임시)
_KIND_SENT = re.compile(r"(정기|임시|종류)\s*주\s*주\s*총\s*회\s*를")       # …임시주주총회를 아래와 같이 개최
_KIND_NTH = re.compile(r"제\s*\d+\s*기\s*(정기|임시)")


def agm_kind(root) -> str:
    """주총 구분(정기·임시·종류). 원문에서 **처음 나오는** 것 하나만 — 제목 → 소집 문장 → '제N기 정기' 순.
    원문 뒤쪽의 이사회 활동표('임시주주총회 소집의 건')·정관 조문에도 같은 낱말이 나오므로 여러 개를 모으면 틀린다."""
    t = el_text(root).replace("\n", " ")
    for rx in (_KIND_TITLE, _KIND_SENT, _KIND_NTH):
        m = rx.search(t)
        if m:
            return m.groups()[-1]
    return ""


def main():
    notices = {n["rcept_no"]: n for n in read_json(INTERIM / "s05_agm_notices.json")}
    amap = read_json(INTERIM / "s05_agm_map.json")
    reports = {r["rcept_no"]: r for r in read_json(INTERIM / "s01_reports.json")}
    market = read_json(INTERIM / "s02_market.json")
    code_of = {}
    for rno, v in amap.items():
        code = reports[rno]["stock_code"] or market[rno]["kind_code"]
        for n in v["notices"]:
            code_of[n] = code
    targets = sorted(code_of)
    print(f"소집공고 원문 {len(targets)}건", flush=True)

    out_f = INTERIM / "s06_agm_docs.json"
    out = read_json(out_f) if out_f.exists() else {}
    http, keys, ki = Http(delay=0.5, timeout=120), dart_keys(), 0
    for i, rno in enumerate(targets, 1):
        n = notices[rno]
        d = notice_dir(n, code_of[rno])
        meta_f = d / "meta.json"
        if meta_f.exists():
            out[rno] = read_json(meta_f)
            continue
        d.mkdir(parents=True, exist_ok=True)
        files = sorted(d.glob("*.xml"))
        if not files:
            while True:
                r = http.get(DOC_URL, params={"crtfc_key": keys[ki], "rcept_no": rno})
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
        root, enc = parse(main_f.read_bytes())
        secs, how = find_sections(root)
        if not secs and len(files) > 1:                 # 본문이 아닌 파일에 있을 때
            for f in files:
                if f == main_f:
                    continue
                r2, _ = parse(f.read_bytes())
                secs, how = find_sections(r2)
                if secs:
                    how += f"@{f.name}"
                    break
        txt_rel = None
        chars = 0
        if secs:
            body = "\n\n".join(section_text(s) for s in secs)
            chars = len(re.sub(r"\s", "", body))
            (d / "정관의변경.txt").write_text(body, encoding="utf-8")
            txt_rel = (d / "정관의변경.txt").relative_to(ROOT).as_posix()
        meta = {"rcept_no": rno, "corp_code": n["corp_code"], "corp_name": n["corp_name"], "stock_code": code_of[rno],
                "report_nm": n["report_nm"], "rcept_dt": n["rcept_dt"], "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}",
                "agm_kind": agm_kind(root), "has_charter_amend": bool(secs), "detect": how, "n_sections": len(secs),
                "section_chars": chars, "charter_amend_txt": txt_rel, "main_xml": main_f.name, "encoding": enc,
                "files": [{"name": f.name, "bytes": f.stat().st_size,
                           "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in files],
                "folder": d.relative_to(ROOT).as_posix(), "fetched_at": now_iso()}
        write_json(meta_f, meta)
        out[rno] = meta
        if i % 50 == 0:
            write_json(out_f, out)
            print(f"  {i}/{len(targets)}", flush=True)
    write_json(out_f, out)
    ok = [m for m in out.values() if "error" not in m]
    print(f"원문 {len(ok)}/{len(targets)} · 정관의 변경 있음 {sum(m['has_charter_amend'] for m in ok)} · "
          f"찾은 방법 {dict(Counter(m['detect'] or '-' for m in ok))} · 주총 구분 {dict(Counter(m['agm_kind'] or '?' for m in ok))}")
    print("  절 글자 수 0~199:", sum(1 for m in ok if m["has_charter_amend"] and m["section_chars"] < 200))


if __name__ == "__main__":
    main()
