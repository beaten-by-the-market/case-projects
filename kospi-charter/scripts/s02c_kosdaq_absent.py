"""s02c 코스닥인데 목록에 없는 회사 — KIND 기준일 현재 코스닥 상장사 중 사업보고서 행이 없는 회사와 그 근거

코스피 s02b_kospi_absent.py 의 **최종본(2026-11-16 19:4x)을 복사해 시장·저장 위치만 바꿨다** (s02b 는 다른 세션 작업이라
import 하지 않는다). 절차·사유 판정은 s02b 와 같고, 덧붙인 것은 하나다:
  · 고유번호 찾기 — 종목코드·(종목코드 있는) 회사명으로 못 찾으면 **종목코드 없는 회사까지 회사명으로** 찾는다(이름이 하나뿐일 때만).
    기준일 당일 상장사는 corpCode.xml 에 아직 종목코드가 없다 (영광와이케이엠씨 345290, 상장일 2026-11-16 — 고유번호 00960234,
    stock_code 빈 값). 찾은 방법은 corp_code_match_by(code · name · name_unlisted)

코스닥 정관 표(kosdaq_charter)는 '최근 1년 사업보고서'에서 출발하므로, 그 기간에 사업보고서를 내지 않은 상장사는
애초에 들어올 수 없다. 이 단계는 그런 회사를 KIND 목록과 맞춰 골라내고, 회사마다 OpenDART 로 근거를 남긴다.

  · 대상 = data/interim/s02_listed_now.csv 의 코스닥 회사(회사 단위, 종목코드 기준) − s02_market.json 에서 코스닥으로 맞춘 회사
  · 회사마다 OpenDART (고유번호를 주면 검색기간 제한이 없다)
      ① list.json  A001 · 최종본 여부 무관 · 1999-01-01 ~ 기준일   → 사업보고서 전체 이력 (연장신고서 제외)
      ② list.json  유형 무관 · 최종본 · 조회기간(BGN ~ 기준일)       → 그 기간에 대신 낸 공시
      ③ company.json                                               → 결산월(acc_mt)
  · 회사마다 KIND (사용자 확인 2026-11-16: 투자회사는 KIND 에 '기타신고사항'으로 낸다)
      ④ disclosure_details  repIsuSrtCd=A+종목코드 · 조회기간 · 최종본   → KIND 공시 제목별 건수
      ⑤ '기타신고사항' 본문(disclosure_content_html)의 '제목' 칸        → 실제 내용 (자산운용보고서 게시·감사보고서 제출 등)
         제목을 MISC_GROUPS 로 묶어 kind_misc_groups(영업보고서·자산운용보고서·결산·감사·정관 변경·투자설명서 갱신·그 밖)
  · 사유 (reason_code)
      new_listing        조회기간 안 신규상장 + 상장 뒤 사업보고서 없음 → 첫 사업보고서 기한(결산기 말 + 90일, 자본시장법 제159조)
      no_annual_report   사업보고서를 낸 적이 없음 (예: 투자회사)
      no_report_in_window  예전에는 냈지만 조회기간 안에는 없음
      report_in_window   조회기간 안에 사업보고서가 있는데 목록에 없음 → 수집 누락 의심 (0건이어야 한다)
  · KIND 상장현황 요약(listed_issue_summary)도 받아 회사 수·종목 수를 함께 남긴다 (기준일이 안 되면 직전 영업일)

출력
  data/interim/kosdaq/s02c_kosdaq_absent.json   {market, snap_date, window, kind_detail, kind_summary, absent: [...]}
  data/raw/opendart_absent_kosdaq/              응답 원본 (다시 돌리면 캐시를 읽는다)
  data/raw/kind/summary_YYYYMMDD.csv            KIND 상장현황 요약 (모든 시장 — 코스피 단계와 같은 파일)
  data/raw/kind/absent_kosdaq/                  KIND 공시 목록 csv · 기타신고사항 본문 html
"""
import argparse
import calendar
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import AS_OF, BGN, INTERIM, RAW, Http, dart_keys, read_json, write_json  # noqa: E402
from _kosdaq import KQ_INTERIM, MARKET  # noqa: E402

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
OUT = RAW / "opendart_absent_kosdaq"
HIST_BGN = date(1999, 1, 1)                     # DART 전자공시 시작 무렵 — 이력 전체
KIND_OUT = RAW / "kind" / "absent_kosdaq"
KIND_MKT = "코스닥"                              # KIND 상장현황 요약의 '시장' 열 (코스닥시장)
SUMMARY_GROUPS = ("주권", "외국주권", "기업인수목적회사", "소계", "주식예탁증권(DR)")
MISC = "기타신고사항"
# 기타신고사항 제목 → 성격 (앞에서부터 처음 맞는 것). 투자회사는 사업보고서 대신 이 서식으로 분기·결산 보고를 알린다
MISC_GROUPS = [("영업보고서", r"영업보고서"), ("자산운용보고서", r"자산운용보고서"), ("결산·감사", r"감사보고서|결산|재무"),
               ("정관 변경", r"정관"), ("투자설명서 갱신", r"투자설명서"), ("그 밖", r"")]
_PERIOD = re.compile(r"^\s*(?:\d{4}\s*년\s*도?\s*)?(?:제?\s*\d+\s*기\s*)?(?:\d\s*분기|상반기|하반기|반기|연간|결산)?\s*")


def norm_name(s: str) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").upper()


def corp_codes() -> tuple[dict, dict, dict]:
    """corpCode.xml → (종목코드 → 고유번호, 회사명 → 고유번호(종목코드 있는 회사), 회사명 → [고유번호…](종목코드 없는 회사)).
    zip 은 코스피 단계(s02b)가 받아 둔 것을 읽기만 한다."""
    f = RAW / "opendart_corpcode.zip"
    if not f.exists():
        raise SystemExit(f"{f} 가 없다 — s02b_kospi_absent.py 가 받는다 (이 스크립트는 읽기만 한다)")
    with zipfile.ZipFile(f) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    by_code, by_name, unlisted = {}, {}, {}
    for e in root.iter("list"):
        cc, sc, nm = (e.findtext(t, "").strip() for t in ("corp_code", "stock_code", "corp_name"))
        if sc:
            by_code[sc] = cc
            by_name.setdefault(norm_name(nm), cc)
        else:
            unlisted.setdefault(norm_name(nm), []).append(cc)
    return by_code, by_name, unlisted


def api(http: Http, keys: list[str], url: str, params: dict, cache: Path) -> dict:
    """OpenDART 호출 + 캐시. 키 한도(020)면 다음 키."""
    if cache.exists():
        return read_json(cache)
    for k in keys:
        j = http.get(url, params={"crtfc_key": k, **params}).json()
        if j.get("status") != "020":
            break
    else:
        raise SystemExit("OpenDART 키 전부 한도 초과(020)")
    if j.get("status") not in ("000", "013"):
        raise SystemExit(f"OpenDART 오류 {j.get('status')} {j.get('message')} {url} {params}")
    write_json(cache, j)
    return j


def filings(http, keys, corp_code: str, tag: str, **params) -> list[dict]:
    rows, page = [], 1
    while True:
        j = api(http, keys, LIST_URL, {"corp_code": corp_code, "page_no": page, "page_count": 100, **params},
                OUT / f"{corp_code}_{tag}_p{page:03d}.json")
        if j.get("status") == "013":
            return rows
        rows += j["list"]
        if page >= j["total_page"]:
            return rows
        page += 1


def form_of(nm: str) -> str:
    """보고서명 → 서식 이름 (앞 [기재정정] 등, 뒤 (YYYY.MM)·(자회사의 주요경영사항) 등 괄호 제거)."""
    nm = re.sub(r"^(\[[^\]]*\])+", "", nm or "").strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", nm).strip()


def kind_disclosures(code: str) -> pd.DataFrame:
    """KIND 공시 상세검색 — 회사·조회기간·최종본. csv 캐시."""
    f = KIND_OUT / f"disclosures_{code}_{BGN:%Y%m%d}_{AS_OF:%Y%m%d}.csv"
    if f.exists():
        return pd.read_csv(f, dtype=str, keep_default_na=False)
    from krx_kind_data_api import fetch

    parts, page = [], 1
    while True:
        df = fetch("disclosure_details", repIsuSrtCd=code, fromDate=f"{BGN:%Y-%m-%d}", toDate=f"{AS_OF:%Y-%m-%d}",
                   currentPageSize=100, pageIndex=page).astype(str)
        parts.append(df)
        time.sleep(1.2)
        if len(df) < 100:
            break
        page += 1
    df = pd.concat(parts, ignore_index=True).drop_duplicates("접수번호")
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False, encoding="utf-8")
    return df


def kind_misc_title(acptno: str) -> str:
    """KIND '기타신고사항' 본문의 '제목' 칸. html 캐시."""
    from bs4 import BeautifulSoup

    f = KIND_OUT / "content" / f"{acptno}.html"
    if not f.exists():
        from krx_kind_data_api import disclosure_content_html

        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(disclosure_content_html(acptno), encoding="utf-8")
        time.sleep(1.2)
    t = re.sub(r"\s+", " ", BeautifulSoup(f.read_text(encoding="utf-8"), "lxml").get_text(" ", strip=True))
    m = re.search(r"제목 (.+?) 내용", t)
    return m.group(1).strip() if m else ""


def first_due(listed: date, acc_mt: int) -> tuple[str, str]:
    """상장일 뒤 처음 끝나는 사업연도 말과 사업보고서 기한(사업연도 경과 후 90일, 자본시장법 제159조)."""
    y = listed.year if listed.month <= acc_mt else listed.year + 1
    end = date(y, acc_mt, calendar.monthrange(y, acc_mt)[1])
    return str(end), str(end + timedelta(days=90))


def kind_summary(snap: str) -> dict | None:
    """KIND 상장현황 요약 — 기준일이 안 되면 직전 영업일 (2026-11-16 은 KINDParseError 였다)."""
    from krx_kind_data_api import fetch

    d0 = date.fromisoformat(f"{snap[:4]}-{snap[4:6]}-{snap[6:]}")
    for k in range(8):
        d = d0 - timedelta(days=k)
        if d.weekday() >= 5:                     # 주말은 직전 영업일 값이 나오므로 건너뛴다 (날짜 표기가 어긋남)
            continue
        f = RAW / "kind" / f"summary_{d:%Y%m%d}.csv"
        if f.exists():
            df = pd.read_csv(f, dtype=str, keep_default_na=False)
        else:
            try:
                df = fetch("listed_issue_summary", selDate=f"{d:%Y-%m-%d}").astype(str)
            except Exception as e:  # noqa: BLE001
                print(f"  KIND 요약 {d} 실패: {type(e).__name__}", flush=True)
                time.sleep(1)
                continue
            if df.empty:
                continue
            df.to_csv(f, index=False, encoding="utf-8")
        k_ = df[df["시장"].str.contains(KIND_MKT)]
        rows = {r["구분"]: {"companies": int(r["회사수"]), "issues": int(r["종목수"])} for _, r in k_.iterrows()
                if r["회사수"].isdigit() and r["구분"] in SUMMARY_GROUPS}
        sub, dr = rows.get("소계", {}), rows.get("주식예탁증권(DR)", {})
        return {"date": f"{d:%Y-%m-%d}", "file": f"data/raw/kind/{f.name}", "groups": rows,
                "companies_with_dr": sub.get("companies", 0) + dr.get("companies", 0),
                "issues_with_dr": sub.get("issues", 0) + dr.get("issues", 0)}
    return None


def main(refresh: bool = False):
    now = pd.read_csv(INTERIM / "s02_listed_now.csv", dtype=str, keep_default_na=False)
    market = read_json(INTERIM / "s02_market.json")
    snap = next(iter(market.values()))["snap_date"]
    kq = now[now["market"] == MARKET].drop_duplicates("종목코드")
    matched = {v["kind_code"] for v in market.values() if v["market"] == MARKET}
    absent = kq[~kq["종목코드"].isin(matched)]
    detail = {"date": f"{snap[:4]}-{snap[4:6]}-{snap[6:]}", "companies": len(kq),
              "groups": kq.groupby("sec_group").size().to_dict(), "in_list": len(kq) - len(absent),
              "absent": len(absent)}
    print(f"KIND {snap} {MARKET} {len(kq)}사 · 목록에 있음 {detail['in_list']} · 없음 {len(absent)}")

    keys = dart_keys()
    http = Http(delay=0.35)
    if refresh:
        for f in OUT.glob("*.json"):
            f.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    by_code, by_name, unlisted = corp_codes()

    out = []
    for _, x in absent.iterrows():
        code, name, grp, listed = x["종목코드"], x["회사명"], x["sec_group"], x["상장일"]
        cc, how = by_code.get(code, ""), "code"
        if not cc:
            cc, how = by_name.get(norm_name(name), ""), "name"
        if not cc and len(unlisted.get(norm_name(name), [])) == 1:     # 기준일 당일 상장 등 — corpCode 에 종목코드가 아직 없음
            cc, how = unlisted[norm_name(name)][0], "name_unlisted"
        rec = {"stock_code": code, "corp_name": name, "sec_group": grp, "listed_date": listed, "corp_code": cc,
               "corp_code_match_by": how if cc else None}
        if not cc:
            rec.update(reason_code="no_corp_code", reason="OpenDART 고유번호를 찾지 못함")
            out.append(rec)
            continue
        hist = [r for r in filings(http, keys, cc, "A001_all", pblntf_detail_ty="A001", last_reprt_at="N",
                                   bgn_de=f"{HIST_BGN:%Y%m%d}", end_de=f"{AS_OF:%Y%m%d}")
                if "연장신고서" not in r["report_nm"]]
        win = filings(http, keys, cc, "all_Y", last_reprt_at="Y", bgn_de=f"{BGN:%Y%m%d}", end_de=f"{AS_OF:%Y%m%d}")
        co = api(http, keys, COMPANY_URL, {"corp_code": cc}, OUT / f"{cc}_company.json")
        acc = int(co["acc_mt"]) if str(co.get("acc_mt", "")).isdigit() else None
        hist.sort(key=lambda r: r["rcept_no"])
        win.sort(key=lambda r: r["rcept_no"])
        in_win = [r for r in hist if f"{BGN:%Y%m%d}" <= r["rcept_dt"] <= f"{AS_OF:%Y%m%d}"]
        forms = Counter(form_of(r["report_nm"]) for r in win)
        rec.update(acc_mt=acc, n_annual_reports_all=len(hist), n_annual_reports_window=len(in_win),
                   last_annual_report_dt=hist[-1]["rcept_dt"] if hist else None,
                   last_annual_report_nm=hist[-1]["report_nm"].strip() if hist else None,
                   last_annual_report_rcept_no=hist[-1]["rcept_no"] if hist else None,
                   n_filings_window=len(win), filing_forms_window=dict(forms.most_common()),
                   last_filing_dt=win[-1]["rcept_dt"] if win else None,
                   last_filing_nm=win[-1]["report_nm"].strip() if win else None,
                   last_filing_rcept_no=win[-1]["rcept_no"] if win else None)
        kd = kind_disclosures("A" + code)
        misc = kd[kd["공시제목"].str.contains(MISC)].sort_values("접수번호")
        items = [[r["시간"][:10], r["접수번호"], kind_misc_title(r["접수번호"])] for _, r in misc.iterrows()]
        kinds = Counter((_PERIOD.sub("", t).strip() or t) if t else "(제목 없음)" for _, _, t in items)
        groups = Counter(next(g for g, pat in MISC_GROUPS if re.search(pat, t or "")) for _, _, t in items)
        groups = {g: groups[g] for g, _ in MISC_GROUPS if groups[g]}
        rec.update(kind_n_disclosures_window=len(kd),
                   kind_titles_window=dict(Counter(kd["공시제목"].str.strip()).most_common()),
                   kind_misc_n=len(items), kind_misc_groups=groups, kind_misc_kinds=dict(kinds.most_common()),
                   kind_misc_items=items)
        listed_d = date.fromisoformat(listed) if listed else None
        since = [r for r in hist if listed_d and r["rcept_dt"] >= f"{listed_d:%Y%m%d}"]
        if in_win:
            code_, why = "report_in_window", f"조회기간 안에 사업보고서 {len(in_win)}건이 있는데 목록에 없음(수집 누락 의심)"
        elif listed_d and listed_d >= BGN and not since:
            fy_end, due = first_due(listed_d, acc) if acc else ("", "")
            code_ = "new_listing"
            why = f"조회기간 안 신규상장({listed}). 상장 뒤 낸 사업보고서 없음"
            if due:
                why += f" · 결산월 {acc}월 → 첫 사업보고서는 {fy_end[:4]}년 결산분, 기한 {due}"
            rec.update(first_fy_end=fy_end or None, first_report_due=due or None)
        elif not hist:
            code_, why = "no_annual_report", f"{grp}. DART 사업보고서 이력 없음({HIST_BGN.year}년 이후 0건)"
            if items:
                why += (f". 대신 분기·결산 보고를 KIND '{MISC}'으로 낸다. 조회기간 {len(items)}건: "
                        + " · ".join(f"{k} {v}" for k, v in groups.items()))
        else:
            code_ = "no_report_in_window"
            why = f"조회기간 안 사업보고서 없음 (마지막 {hist[-1]['rcept_dt']} {hist[-1]['report_nm']})"
        rec.update(reason_code=code_, reason=why)
        out.append(rec)
        print(f"  {code} {name} [{grp}] 사업보고서 전체 {len(hist)} · 기간 {len(in_win)} · 기간 DART 공시 {len(win)}"
              f" · KIND 공시 {len(kd)}(기타신고사항 {len(items)}) → {code_}")

    summ = kind_summary(snap)
    if summ:
        print(f"KIND 상장현황 요약 {summ['date']}: {MARKET} 회사 {summ['companies_with_dr']}사(DR 포함) · "
              f"종목 {summ['issues_with_dr']}개 · {summ['groups']}")
    write_json(KQ_INTERIM / "s02c_kosdaq_absent.json",
               {"market": MARKET, "snap_date": snap, "window": [str(BGN), str(AS_OF)], "kind_detail": detail,
                "kind_summary": summ, "absent": out})
    print("사유:", dict(Counter(r["reason_code"] for r in out)),
          "· 고유번호 찾은 방법:", dict(Counter(r.get("corp_code_match_by") or "-" for r in out)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="OpenDART 캐시(data/raw/opendart_absent_kosdaq)를 지우고 다시 받는다")
    main(ap.parse_args().refresh)
