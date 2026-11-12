"""s08 거래소 '주주총회소집결의' 공시 · '의결권대리행사권유참고서류' 와 소집공고 비교

표본(sample·sample_extra) 중 상장사(corp_cls Y·K·N), 2021년 이후 원본 소집공고마다
같은 회사의 list.json(소집공고 60일 전 ~ 당일)을 불러
  - 거래소 '주주총회소집결의'(가장 가까운 것) → 시차(일), 원문 → data/raw/krx/
  - 같은 날 '의결권대리행사권유참고서류'(D003) → 원문 → data/raw/d003/ (최대 40건)
출력 data/interim/krx_convene.csv
OpenDART 의 거래소 공시 원문은 ZIP 안 .xml 이름이지만 내용은 KIND 양식(xforms)을 그린 HTML 이다.
"""
import csv
import io
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _dart import ROOT, Keys, Net  # noqa: E402

LIST = "https://opendart.fss.or.kr/api/list.json"
DOC = "https://opendart.fss.or.kr/api/document.xml"


def d(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def fetch(keys, rcp, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    if list(outdir.glob(f"{rcp}*")):
        return "cached"
    r = Net.get(DOC, params={"crtfc_key": keys.cur, "rcept_no": rcp}, timeout=120)
    if r.content[:2] != b"PK":
        m = re.search(r"<status>(\d+)</status>", r.text[:600])
        return f"status{m.group(1) if m else '?'}"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for n in zf.namelist():
            (outdir / Path(n).name).write_bytes(zf.read(n))
    return "ok"


def main():
    keys = Keys()
    src = []
    for name in ("sample.csv", "sample_extra.csv"):
        src += list(csv.DictReader((ROOT / "data/interim" / name).open(encoding="utf-8-sig")))
    src = [r for r in src if r["corp_cls"] in ("Y", "K", "N") and r["rcept_dt"] >= "20210101"
           and not r["report_nm"].startswith("[")]
    out, n_d003 = [], 0
    for i, r in enumerate(src, 1):
        a = (d(r["rcept_dt"]) - timedelta(days=60)).strftime("%Y%m%d")
        j = Net.get(LIST, params={"crtfc_key": keys.cur, "corp_code": r["corp_code"], "bgn_de": a,
                                  "end_de": r["rcept_dt"], "page_count": 100}, timeout=60).json()
        lst = j.get("list", [])
        conv = [x for x in lst if "주주총회소집결의" in x["report_nm"].replace(" ", "")]
        conv.sort(key=lambda x: x["rcept_no"], reverse=True)
        d003 = [x for x in lst if x["report_nm"].startswith("의결권대리행사권유참고서류")
                and x["rcept_dt"] == r["rcept_dt"]]
        row = {"e006": r["rcept_no"], "e006_dt": r["rcept_dt"], "corp_name": r["corp_name"],
               "corp_cls": r["corp_cls"], "conv": "", "conv_dt": "", "lag_days": "", "conv_st": "",
               "d003": "", "d003_flr": "", "d003_st": ""}
        if conv:
            c = conv[0]
            row.update(conv=c["rcept_no"], conv_dt=c["rcept_dt"],
                       lag_days=(d(r["rcept_dt"]) - d(c["rcept_dt"])).days,
                       conv_st=fetch(keys, c["rcept_no"], ROOT / "data/raw/krx"))
        if d003:
            x = d003[0]
            row.update(d003=x["rcept_no"], d003_flr=x["flr_nm"])
            if n_d003 < 40:
                row["d003_st"] = fetch(keys, x["rcept_no"], ROOT / "data/raw/d003")
                n_d003 += 1
        out.append(row)
        print(i, len(src), row["corp_name"], row["lag_days"], row["conv_st"], row["d003_st"], flush=True)
    with (ROOT / "data/interim/krx_convene.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
