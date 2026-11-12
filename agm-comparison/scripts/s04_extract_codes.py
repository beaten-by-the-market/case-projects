"""s04 원문 XML 의 표준 코드 속성 전수 추출

DART 작성기(dart4.xsd) 서식은 요소에 코드 속성을 단다. 소집공고에서 의미 있는 것:
  DOCUMENT-NAME@ACODE   서식(문서) 코드
  FORMULA-VERSION@ADATE 서식 버전 일자
  TITLE@AASSOCNOTE      목차 절 코드 (D-…: 본문 고정 절, L0-0-2-N-…: '목적사항별 기재사항' 안건유형 절)
  TABLE(-GROUP)@ACLASS  표 성격 (EXTRACTION = 추출 대상 표 등)
  TE|TU@ACODE           셀(항목) 코드
  TU@AUNIT/@AUNITVALUE  단위 항목 코드와 값(날짜·구분 코드)

출력
  data/interim/code_occ.csv    등장 1건 = 1행 (rcept_no, 요소, 속성, 값, 제목/본문 앞부분, 상위 절 코드)
  data/final/code_summary.csv  (속성, 값)별 문서 수·연도 범위·서식버전·대표 제목
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402

RAW = ROOT / "data/raw/xml"
ATTRS = ("ACODE", "AASSOCNOTE", "AUNIT", "ACLASS")
WS = re.compile(r"\s+")
LEAD = re.compile(r"^\s*(?:[□■○●◎※]|\d+\.|[가-하]\.|[①-⑳]|[IVX]+\.)\s*")


def text_of(el, n=120) -> str:
    return WS.sub(" ", "".join(el.itertext())).strip()[:n]


def load(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8", "cp949"):
        try:
            s = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    s = re.sub(r"^<\?xml[^>]*\?>", "", s.lstrip("\ufeff").lstrip())
    parser = etree.XMLParser(recover=True, huge_tree=True)
    return etree.fromstring(s.encode("utf-8"), parser)


def main():
    meta = {}
    for name in ("sample.csv", "sample_extra.csv", "sample_targets.csv"):
        p = ROOT / "data/interim" / name
        if p.exists():
            meta.update({r["rcept_no"]: r for r in csv.DictReader(p.open(encoding="utf-8-sig"))})
    p = ROOT / "data/interim/scan_rare.csv"   # s10 스캔에서 7·16·17호가 나와 원문을 저장한 공고
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8-sig")):
            if r["rare"] and r["rcept_no"] not in meta:
                meta[r["rcept_no"]] = {**r, "stratum": f"scan|{r['rare'].replace(' ', ',')}호"}
    occ = []
    for d in sorted(RAW.iterdir()):
        rcp = d.name
        for f in sorted(d.glob("*.xml")):
            root = load(f)
            fv = root.find(".//FORMULA-VERSION")
            fver = f"{fv.text.strip() if fv is not None and fv.text else ''}@{fv.get('ADATE', '') if fv is not None else ''}"
            # 문서 순서대로 걷되, 직전 TITLE@AASSOCNOTE 를 '현재 절'로 기억
            cur_sec = ""
            for el in root.iter():
                if not isinstance(el.tag, str):
                    continue
                if el.tag == "TITLE" and el.get("AASSOCNOTE"):
                    cur_sec = el.get("AASSOCNOTE")
                for a in ATTRS:
                    v = el.get(a)
                    if v is None or (a == "ACLASS" and v == "NORMAL"):
                        continue
                    extra = el.get("AUNITVALUE", "") if a == "AUNIT" else ""
                    occ.append({"rcept_no": rcp, "file": f.name, "year": rcp[:4],
                                "corp_cls": meta.get(rcp, {}).get("corp_cls", ""),
                                "report_nm": meta.get(rcp, {}).get("report_nm", ""),
                                "stratum": meta.get(rcp, {}).get("stratum", ""),
                                "formula": fver, "tag": el.tag, "attr": a, "value": v, "unitvalue": extra,
                                "section": cur_sec, "text": text_of(el)})
    cols = list(occ[0])
    with (ROOT / "data/interim/code_occ.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(occ)

    g = defaultdict(list)
    for o in occ:
        g[(o["attr"], o["tag"], o["value"])].append(o)
    out = []
    for (a, tag, v), lst in g.items():
        docs = {o["rcept_no"] for o in lst}
        titles = Counter(LEAD.sub("", o["text"])[:40] for o in lst)
        out.append({"attr": a, "tag": tag, "value": v, "n_docs": len(docs), "n_occ": len(lst),
                    "yr_min": min(o["year"] for o in lst), "yr_max": max(o["year"] for o in lst),
                    "formulas": ";".join(sorted({o["formula"] for o in lst})),
                    "sections": ";".join(sorted({o["section"] for o in lst}))[:200],
                    "unitvalues": ";".join(sorted({o["unitvalue"] for o in lst if o["unitvalue"]}))[:200],
                    "top_texts": " | ".join(f"{t}({c})" for t, c in titles.most_common(4))})
    out.sort(key=lambda r: (r["attr"], r["value"]))
    with (ROOT / "data/final/code_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"등장 {len(occ)} / 코드 {len(out)}")


if __name__ == "__main__":
    main()
