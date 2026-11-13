"""s16 엑셀 재현본 통합문서 — DataGuide 시트(원래 틀 그대로, Refresh 가능) + 고정 시트(업종·DART·KIND·정답지·파이썬 결과).

1) 파이썬: 고정 시트를 data/excel/저PBR_재현_DataGuide.xlsx 로 쓴다.
2) 엑셀(COM, s16_excel_book.ps1): DataGuide 원본 파일의 시트를 셀째로 복사해 붙인다.
   DataGuide 설정(탭·기간·코드·아이템)은 시트 1~9행과 A·D열 셀에 있어, 옮긴 시트에서도 A1 Refresh 로 다시 받힌다(2026-11-12 시험).
   상태 시트는 기준일마다 한 장(B8=C8=기준일). 2026.05·2026.11 은 1년 기간 파일에서 그 날짜 열만 남긴다.

DataGuide 값과 GICS 매핑이 들어 있어 data/excel/ 은 git 에서 제외한다. DataGuide 구독자 사이에서만 공유한다.
실행: python scripts/s16_excel_book.py        (엑셀이 켜져 있으면 그 엑셀을, 아니면 새 엑셀을 쓴다)
     통합문서에 계산_ 시트(Claude for Excel)가 있으면 멈춘다. 덮어쓰려면 --force.
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).parent))
from _rules import ROOT  # noqa: E402

INTER, FINAL, OUT = ROOT / "data/interim", ROOT / "data/final", ROOT / "data/excel"
BOOK = OUT / "저PBR_재현_DataGuide.xlsx"

GUIDE = [
    ("저PBR기업 선정(2026.11.2 공표) 엑셀 재현본", "h1"),
    ("한국거래소가 2026.11.2 처음 공표한 저PBR기업 151사를, 파이썬 없이 이 통합문서 안의 자료만으로 다시 계산하기 위한 파일이다.", ""),
    ("주가·재무·상태는 DataGuide 6(FnGuide)에서 받은 시트이고, DataGuide에 없는 자료(업종·공시·정답지)는 고정 시트로 붙였다.", ""),
    ("", ""),
    ("1. 시트", "h2"),
    ("시트|원천|내용|다시 받기", "th"),
    ("회차|레포 rounds.csv|13개 회차 공표일·기준일·20거래일 구간(구간시작~구간끝)|고정", ""),
    ("종목|레포 excel_codes.csv|보통주 2,715 + 우선주 128. 우선주 → 보통주코드|고정", ""),
    ("DG_시총|DataGuide 달력기준|S410001250 시가총액(백만원), 종목 행 × 거래일 열, 2020-09-21~2026-10-22|A1 Refresh (약 10분)", ""),
    ("DG_자본|DataGuide 회계기준|자본총계(지배)[연결]·자본총계[연결]·자본총계[별도](천원), 코드·결산월·회계연도·분기 행|A1 Refresh", ""),
    ("DG_상태_기준일 (13장)|DataGuide 달력기준|시장구분·상장일·관리종목여부·지정사유·거래정지여부·정지사유, 종목·아이템 행|A1 Refresh (장당 26~36분)", ""),
    ("업종|KRX 지수 사이트(GICS)|회차 × 종목 GICS 섹터. 출처 KRX / WICS근사(목록에 없는 예전 상장사) / 없음|고정", ""),
    ("기준보고서_DART|DART|회차 × 종목 기준 보고서(재무년월·보고서명·접수일·DART 링크)|고정", ""),
    ("밸류업공시|KIND|기업가치 제고 계획 공시. 제목에 'PBR'이 있으면 면제 대상|고정", ""),
    ("관리사유_KIND|KIND|2026.11 회차 관리종목 지정사유(지정일·사유)|고정", ""),
    ("정답_*|보도자료·KIND|단계별 사수, 업종 기준 PBR, 공표 151사·PBR|고정", ""),
    ("파이썬_*|레포 s06 --src dg|이 통합문서와 같은 자료로 파이썬이 계산한 결과(회차·종목별 PBR·순위·기준선, 최종 판정)|고정", ""),
    ("", ""),
    ("2. DataGuide 시트 다시 받기", "h2"),
    ("DataGuide 6 엑셀 추가 기능에 로그인한 뒤, DG_ 시트의 A1 'Refresh'를 누른다. 설정(기간·코드·아이템)은 시트 1~9행에 그대로 남아 있다.", ""),
    ("상태 시트는 B8·C8(기간)이 그 기준일 하루다. 다른 날짜를 보려면 B8·C8을 바꾸고 Refresh.", ""),
    ("Refresh 하면 줄·열 수가 바뀔 수 있으므로, 계산 시트는 행 번호가 아니라 종목코드·날짜로 찾아 써야 한다(XLOOKUP/MATCH).", ""),
    ("단위: DG_시총 백만원(소수 둘째 자리), DG_자본 천원. PBR = 평균 시가총액(원) ÷ (자본 × 1,000).", ""),
    ("", ""),
    ("3. 계산 순서 (규칙 번호는 레포 docs/01-재현사양.md)", "h2"),
    ("단계|규칙", "th"),
    ("① 모집단|그 회차 DG_상태 시장구분이 KS(유가)·KQ(코스닥)인 보통주. 13개 기준일 모두 KIND 상장종목 명단과 100% 같다.", ""),
    ("② 산정 제외(2026.11 앞 12개 회차)|DG_상태 관리종목 = '관리'이고, 사유에 시가총액·주가·동전주·거래실적·거래량이 없거나 '종류주식'이 있으면 제외. 사유 빈칸은 남김. 거래정지 = '정지'이고, 사유에 병합·분할·시가총액·주가가 없으면 제외.", ""),
    ("② 산정 제외(2026.11)|관리사유_KIND에서 지정일 ≤ 2026-10-22이고, 사유가 '시가총액 미달'·'주가 미달(동전주)'뿐이 아닌 종목(종목명으로 맞춤)을 제외.", ""),
    ("② 산정 제외(모든 회차)|DG_시총이 20거래일 구간 내내(값 15일 이상) 한 번도 안 바뀐 종목 = 거래정지로 보고 제외.", ""),
    ("③ 시가총액|20거래일 구간(회차 시트 구간시작~구간끝) 일평균. 보통주 값이 있는 날마다 보통주 + 우선주(종목 시트로 묶음)를 더해 평균.", ""),
    ("④ 자본|기준보고서_DART의 재무년월로 DG_자본에서 찾는다. 재무년월 = 결산일(회계연도 + (결산월 ≤ 5 ? 1 : 0)년 결산월)에서 분기마다 3개월씩 앞(1st-Quarter 9, Semi-Annual 6, 3rd-Quarter 3, 결산 0개월). 연결 지배 → 없으면 별도 자본총계.", ""),
    ("⑤ PBR|TRUNC(평균 시가총액 ÷ (자본 × 1000), 2). 자본 ≤ 0이거나 없으면 제외.", ""),
    ("⑥ 업종|코스닥이고 상장일이 기준일 달 2개월 전 1일 이후면 '업종미분류', 아니면 업종 시트 GICS.", ""),
    ("⑦ 하위 컷|시장 × 업종 안에서 PBR 오름차순. 유가 25%·코스닥 10%: 기준선 = FLOOR(N × 비율)번째 PBR(최소 1번째). 업종 사수가 유가 4·코스닥 10 미만이면 1번째. PBR ≤ 기준선이면 해당. 업종미분류는 시장 전체 기준선.", ""),
    ("⑧ 선정|2026.11 해당 필수. 최근 6회(8~13회차) 모두 해당, 또는 6회 중 5회 + 7회차 해당. 업종미분류는 6회 모두.", ""),
    ("⑨ 면제|기준일(2026-10-22)까지 밸류업공시 제목에 'PBR'이 있으면 면제. 단 최근 12회(2~13회차) 모두 해당, 또는 11회 + 1회차 해당이면 면제 불가(공표).", ""),
    ("⑩ 대조|정답_보도자료(유가 779·코스닥 1,652, 업종 기준 PBR 22개), 정답_KIND(151사·PBR). 파이썬 결과: 22/22, 151사 일치, 재현에만 5사.", ""),
    ("", ""),
    ("4. 주의", "h2"),
    ("DataGuide 값과 GICS 매핑이 들어 있어 공개 배포하지 않는다. DataGuide 구독자 사이에서만 공유한다.", ""),
    ("만든 스크립트: 레포 scripts/s16_excel_book.py (+ s16_excel_book.ps1). 데이터 명세: docs/04-데이터가이드-명세.md.", ""),
]


def static_sheets() -> dict[str, pd.DataFrame]:
    rd = pd.read_csv(INTER / "rounds.csv", dtype=str).rename(columns={
        "round": "회차", "seq": "순번", "pub_date": "공표일", "base_date": "기준일", "win_start": "구간시작",
        "win_end": "구간끝", "report_kind": "보고서종류", "period_end": "기준결산기"})
    adm = pd.read_csv(INTER / "admin_flags.csv", dtype=str)
    return {
        "회차": rd,
        "종목": pd.read_csv(FINAL / "excel_codes.csv", dtype=str),
        "업종": pd.read_csv(INTER / "excel_gics.csv", dtype=str),
        "기준보고서_DART": pd.read_csv(FINAL / "excel_dart_filings.csv", dtype=str),
        "밸류업공시": pd.read_csv(FINAL / "kind_valueup_discl.csv", dtype=str),
        "관리사유_KIND": adm,
        "정답_보도자료_총계": pd.read_csv(FINAL / "press_totals.csv", dtype=str),
        "정답_보도자료_업종": pd.read_csv(FINAL / "press_sector.csv", dtype=str),
        "정답_보도자료_151": pd.read_csv(FINAL / "press_list151.csv", dtype=str),
        "정답_KIND": pd.read_csv(FINAL / "kind_lowpbr_20261102.csv", dtype=str),
        "파이썬_선정": pd.read_csv(FINAL / "replica_selection_dg.csv", dtype=str),
        "파이썬_업종": pd.read_csv(FINAL / "replica_sector_dg.csv", dtype=str),
        "파이썬_회차종목": pd.read_csv(FINAL / "replica_firm_round_dg.csv", dtype=str),
    }


def write_static():
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = static_sheets()
    with pd.ExcelWriter(BOOK, engine="openpyxl") as w:
        pd.DataFrame().to_excel(w, sheet_name="안내", index=False)
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
    wb = load_workbook(BOOK)
    ws = wb["안내"]
    ws.sheet_view.showGridLines = False
    head = PatternFill("solid", fgColor="DDE5F0")
    for i, (text, kind) in enumerate(GUIDE, 1):
        for j, part in enumerate(text.split("|") if "|" in text else [text], 1):
            c = ws.cell(row=i, column=j, value=part)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if kind == "h1":
                c.font = Font(bold=True, size=14)
            elif kind == "h2":
                c.font = Font(bold=True, size=12)
            elif kind == "th":
                c.font, c.fill = Font(bold=True), head
    for col, wd in zip("ABCD", (34, 24, 90, 30)):
        ws.column_dimensions[col].width = wd
    for name in sheets:
        s = wb[name]
        s.freeze_panes = "A2"
        for j, cell in enumerate(s[1], 1):
            cell.font = Font(bold=True)
            s.column_dimensions[get_column_letter(j)].width = max(10, min(40, len(str(cell.value)) * 2 + 2))
    wb.save(BOOK)
    print(f"고정 시트 {len(sheets) + 1}장 → {BOOK}")


def main():
    # 통합문서를 새로 쓰므로, Claude for Excel로 만든 계산_ 시트가 있으면 지우지 않도록 멈춘다.
    if BOOK.exists() and "--force" not in sys.argv:
        calc = [n for n in load_workbook(BOOK, read_only=True).sheetnames if n.startswith("계산_")]
        if calc:
            sys.exit(f"{BOOK} 에 계산 시트 {calc} 가 있다. 다시 만들면 지워진다 — 먼저 다른 이름으로 저장하거나 --force.")
    write_static()
    ps1 = Path(__file__).with_suffix(".ps1")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
                        "-Book", str(BOOK), "-Raw", str(ROOT / "data/raw/dataguide")])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
