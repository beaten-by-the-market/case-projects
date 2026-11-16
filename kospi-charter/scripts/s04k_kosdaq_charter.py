"""s04k 코스닥 행의 정관 첨부 → 원문 내려받기 — s04_charter.py 와 같은 규칙, 대상·저장 위치만 코스닥

  · 정관 고르기·내려받기·텍스트 변환·종류 판정(text/image/mixed/pdf/empty)은 s04_charter 의 함수를 그대로 쓴다
    (is_charter · pick · parse_att_title · fetch_doc · repair). s04_charter.CHARTER 만 data/charter_kosdaq 로 바꾼다
  · 첨부 main.do 캐시는 코스피와 같은 data/raw/dart_att/{rcpNo}_{dcmNo}.html (문서번호로 이름이 붙어 겹치지 않는다)
  · DART 웹 — _common.Http 의 호스트 단위 분당 80건 상한 (화면·이미지·재시도 합산). 다른 DART 수집과 동시에 돌리지 않는다

저장  data/charter_kosdaq/{종목코드}_{회사명}/{첨부일자}_{dcmNo}/  viewer_NN.html · charter.txt · img/ · meta.json
출력  data/interim/kosdaq/s04_charter.json   rcept_no → 대표 정관·후보 수·문서 키
      data/interim/kosdaq/s04_docs.json      문서(rcpNo_dcmNo) → meta

실행  python -X utf8 scripts/s04k_kosdaq_charter.py [--limit N] [--repair]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import ROOT, Http, read_json, write_json  # noqa: E402
from _kosdaq import KQ_CHARTER, KQ_INTERIM, kosdaq_rows, patch  # noqa: E402
import s04_charter as s4  # noqa: E402

patch(s4, CHARTER=KQ_CHARTER)


def main(limit: int = 0):
    rows, market = kosdaq_rows()
    main_pages = read_json(KQ_INTERIM / "s03_main.json")

    per_row, docs, names = {}, {}, Counter()
    for r in rows:
        pg = main_pages.get(r["rcept_no"])
        if pg is None:
            per_row[r["rcept_no"]] = {"charter_status": "main_page_missing"}
            continue
        cands = []
        for i, a in enumerate(pg["att"]):
            a = dict(a, att_order=i, **s4.parse_att_title(a["title"]))
            names[a["att_name"]] += 1
            if s4.is_charter(a["att_name"]):
                cands.append(a)
        if not cands:
            per_row[r["rcept_no"]] = {"charter_status": "no_charter_attachment", "n_att": len(pg["att"])}
            continue
        a = s4.pick(cands)
        code = r["stock_code"] or market[r["rcept_no"]]["kind_code"]
        key = f"{a['rcpNo']}_{a['dcmNo']}"
        docs.setdefault(key, {"corp_code": r["corp_code"], "corp_name": r["corp_name"], "stock_code": code,
                              "att_title": a["title"], "att_date": a["att_date"], "rcpNo": a["rcpNo"],
                              "dcmNo": a["dcmNo"], "att_url": a["url"], "used_by": []})
        docs[key]["used_by"].append(r["rcept_no"])
        per_row[r["rcept_no"]] = {"charter_status": "ok", "doc_key": key, "n_charter_att": len(cands),
                                  "charter_title": a["title"], "charter_url": a["url"]}

    print(f"코스닥 행 {len(per_row)} · 정관 문서 {len(docs)}개 · 상태 {dict(Counter(v['charter_status'] for v in per_row.values()))}",
          flush=True)
    print("  첨부 이름 상위:", names.most_common(14))
    print("  '정관' 이 들어간 첨부 이름:", sorted({n for n in names if "정관" in n.replace(' ', '')}), flush=True)
    write_json(KQ_INTERIM / "s04_charter.json", per_row)

    http, img_http = Http(delay=1.0), Http(delay=0.5)
    docs_f = KQ_INTERIM / "s04_docs.json"
    metas = read_json(docs_f) if docs_f.exists() else {}
    items = sorted(docs.items(), key=lambda kv: kv[1]["stock_code"])
    if limit:
        items = items[:limit]                        # 파일럿
    for i, (key, doc) in enumerate(items, 1):
        try:
            m = s4.fetch_doc(http, img_http, doc)
        except RuntimeError as e:
            print(f"  실패 {key} {doc['corp_name']}: {e}", flush=True)
            continue
        m["used_by_rcept_no"] = doc["used_by"]
        write_json(ROOT / m["folder"] / "meta.json", m)
        metas[key] = m
        if i % 25 == 0:
            print(f"  {i}/{len(items)} {doc['corp_name']} {m['content_type']} img={m['n_images']}", flush=True)
            write_json(docs_f, metas)
    metas = {k: v for k, v in metas.items() if k in docs}
    write_json(docs_f, metas)
    print("정관 원문 종류:", dict(Counter(m["content_type"] for m in metas.values())),
          "· 이미지", sum(m["n_images"] for m in metas.values()), "장 · 이미지 오류",
          sum(m["n_image_errors"] for m in metas.values()), f"· 받은 문서 {len(metas)}/{len(docs)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="파일럿: 앞 N개 문서만")
    ap.add_argument("--repair", action="store_true", help="받아 둔 이미지 중 깨진 것만 다시 받기")
    a = ap.parse_args()
    s4.repair() if a.repair else main(a.limit)
