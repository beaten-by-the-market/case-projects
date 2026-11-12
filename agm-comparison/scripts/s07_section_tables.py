"""s07 안건유형 절(L0-0-2-N-*) 안의 표 구조 전수 추출

안건 절 안 표에는 셀 코드(ACODE·AUNIT)가 없다(ACLASS="NORMAL"). 대신 작성기 서식이
고정 소제목(P "가. 후보자의 성명ㆍ생년월일…")과 머리행(THEAD/TH)이 정해진 표를 미리 넣어 둔다.
표마다 (절 코드, 바로 앞 소제목, 머리행 서명)을 뽑아 문서 간 일치도를 본다.

출력
  data/interim/section_tables.csv         표 1개 = 1행
  data/final/section_table_summary.csv    (절, 머리행 서명)별 문서 수·절 보유 문서 대비 비율·서식 버전
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT  # noqa: E402
from s04_extract_codes import load  # noqa: E402

RAW = ROOT / "data/raw/xml"
SUBHEAD = re.compile(r"^\s*(?:[가-하]|\d{1,2}|\(\d{1,2}\)|[①-⑳])[\.\)]\s*\S")
WS = re.compile(r"\s+")


def txt(el) -> str:
    return WS.sub(" ", "".join(el.itertext())).strip()


def header_sig(tbl):
    thead = tbl.find("THEAD")
    if thead is not None:
        cells = [txt(c) for c in thead.iter("TH", "TE", "TD", "TU")]
        return 1, " | ".join(re.sub(r"\s", "", c) for c in cells if c)
    tr = tbl.find(".//TR")
    if tr is None:
        return 0, ""
    cells = [txt(c) for c in tr if isinstance(c.tag, str)]
    return 0, " | ".join(re.sub(r"\s", "", c)[:30] for c in cells if c)


def main():
    rows = []
    for d in sorted(RAW.iterdir()):
        f = next(d.glob("*.xml"), None)
        if f is None:
            continue
        root = load(f)
        fv = root.find(".//FORMULA-VERSION")
        fver = (fv.text or "").strip() if fv is not None else ""
        sec, sub, k = "", "", 0
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            if el.tag == "TITLE" and el.get("AASSOCNOTE"):
                sec, sub, k = el.get("AASSOCNOTE"), "", 0
            elif el.tag == "P" and sec.startswith("L0-0-2-") and el.getparent().tag not in ("TD", "TH", "TE", "TU"):
                t = txt(el)
                if SUBHEAD.match(t) and len(t) < 120:
                    sub = t
            elif el.tag == "TABLE" and sec.startswith("L0-0-2-"):
                if any(a.tag == "TABLE" for a in el.iterancestors()):
                    continue
                k += 1
                has_thead, sig = header_sig(el)
                rows.append({"rcept_no": d.name, "formula": fver, "section": sec, "tbl_no": k,
                             "subhead": sub[:100], "has_thead": has_thead, "afixtable": el.get("AFIXTABLE", ""),
                             "n_tr": len(el.findall(".//TR")), "header_sig": sig[:300]})
    with (ROOT / "data/interim/section_tables.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    sec_docs = defaultdict(set)
    for o in csv.DictReader((ROOT / "data/interim/code_occ.csv").open(encoding="utf-8-sig")):
        if o["value"].startswith("L0-0-2-"):
            sec_docs[o["value"]].add(o["rcept_no"])
    g = defaultdict(lambda: {"docs": set(), "subs": defaultdict(int), "fv": set()})
    for r in rows:
        x = g[(r["section"], r["header_sig"])]
        x["docs"].add(r["rcept_no"])
        x["subs"][r["subhead"]] += 1
        x["fv"].add(r["formula"])
    out = []
    for (sec, sig), x in g.items():
        n = len(sec_docs.get(sec, ())) or 1
        out.append({"section": sec, "n_sec_docs": n, "header_sig": sig, "n_docs": len(x["docs"]),
                    "share": round(len(x["docs"]) / n, 3), "formulas": ";".join(sorted(x["fv"])),
                    "top_subhead": max(x["subs"], key=x["subs"].get)})
    out.sort(key=lambda r: (int(r["section"].split("-")[3]), r["section"], -r["n_docs"]))
    with (ROOT / "data/final/section_table_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"표 {len(rows)}개 / (절, 머리행) 조합 {len(out)}")


if __name__ == "__main__":
    main()
