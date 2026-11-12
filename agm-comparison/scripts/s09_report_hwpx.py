# HWPX 보고서 빌더(본문 3쪽 + 붙임 1쪽). 레퍼런스: 사내 검토자료 hwpx 서식(제목 상자·섹션 머리·□/ㅇ·표·각주)을 복제.
# 주의: 레퍼런스 패키지를 그대로 쓰므로 content.hpf 의 제목·description(문서보안 추적 ID)과 Preview/* 를 지우거나 바꾼 뒤 배포할 것.
# docs/ 의 최종 hwpx·pdf 는 이 빌드 결과를 한글에서 손본 판이다.
# 절차: unpack(ref) → python s09_report_hwpx.py ref_section.xml ref_header.xml out_section.xml out_header.xml data/final/agenda_code_names.json
#       (명조 계열 글꼴 → HY신명조) → pack → fix_namespaces → finalize → validate → rhwp export-pdf
"""레퍼런스(사내 검토자료) 서식 요소를 복제해 '주총 안건 데이터 기계판독성' 2쪽 보고서 section0.xml / header.xml 생성.
사용: python build_agm.py <ref_section.xml> <ref_header.xml> <out_section.xml> <out_header.xml>
"""
import copy
import sys

from lxml import etree

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HH = 'http://www.hancom.co.kr/hwpml/2011/head'
NS = {'hp': HP}
q = lambda t: '{%s}%s' % (HP, t)

ref_sec, ref_head, out_sec, out_head = sys.argv[1:5]  # argv[5] = 코드명 JSON
tree = etree.parse(ref_sec)
root = tree.getroot()
ps = root.findall('hp:p', NS)

# ---------- 템플릿 요소 ----------
P_LOGO = ps[0]            # secPr + 로고 + '검토자료'
P_TITLE = ps[1]           # 제목 상자
P_SECHEAD = ps[2]         # '1. ...' 섹션 머리 표
P_GAP_AFTER_HEAD = ps[3]  # 섹션 머리 뒤 간격(paraPr 42)
P_BOX = ps[46]            # □ (라벨) 본문
P_O = ps[48]              # ㅇ 본문 (paraPr 47)
P_DASH = ps[44]           # - 본문 (paraPr 53)
P_GAP = ps[28]            # 빈 줄(paraPr 3, charPr 8)
P_GAP_BEFORE_TBL = ps[34]  # 표 앞 작은 간격(paraPr 36)
P_GAP_AFTER_TBL = ps[36]   # 표 뒤 작은 간격(paraPr 50)
P_NOTE = ps[37]           # 각주 '* ...' (paraPr 56)
P_SIDETBL = ps[35]        # 왼쪽 진한 라벨(rowSpan) + 라벨 + 내용 3열 표

_tid = [1990000001]


def strip_lsa(el):
    for l in el.iter(q('linesegarray')):
        l.getparent().remove(l)


def runs_para(tpl, parts):
    """tpl 문단 서식(paraPr)을 유지하고 run 목록을 parts=[(charPr, text)]로 새로 만든다."""
    p = copy.deepcopy(tpl)
    for r in p.findall('hp:run', NS):
        p.remove(r)
    strip_lsa(p)
    for cp, text in parts:
        r = etree.SubElement(p, q('run'), charPrIDRef=str(cp))
        t = etree.SubElement(r, q('t'))
        t.text = text
    return p


def gap(tpl=None):
    p = copy.deepcopy(tpl if tpl is not None else P_GAP)
    strip_lsa(p)
    return p


def box(label, text, bold=None):
    parts = [(31, '□ '), (71, '('), (74, label), (71, ') ')]
    if bold:
        pre, b, post = text.partition(bold)
        parts += [(34, pre), (35, b), (34, post)]
    else:
        parts.append((34, text))
    return runs_para(P_BOX, [x for x in parts if x[1]])


def o(text, cp=43):
    return runs_para(P_O, [(34, ' ㅇ '), (cp, text)])


def dash(text):
    return runs_para(P_DASH, [(34, '   - '), (30, text)])


def note(mark, text):
    return runs_para(P_NOTE, [(73, '     %s ' % mark), (80, text)])


def sechead(num, title):
    p = copy.deepcopy(P_SECHEAD)
    strip_lsa(p)
    tbl = p.find('.//hp:tbl', NS)
    _tid[0] += 1
    tbl.set('id', str(_tid[0]))
    tcs = tbl.findall('.//hp:tc', NS)
    tcs[0].find('.//hp:t', NS).text = num
    ts = tcs[2].findall('.//hp:t', NS)
    ts[0].text = ' ' + title
    tcs[2].set('borderFillIDRef', '9')   # 원형 그라데이션(10) → 번호 칸과 같은 단색 남색(9): 긴 제목의 흰 글씨가 밝은 쪽에 묻히지 않게
    return p


def set_cell(tc, lines, col, row, w, h, rowspan=1):
    sub = tc.find('hp:subList', NS)
    ptpl = sub.find('hp:p', NS)
    for p in sub.findall('hp:p', NS):
        sub.remove(p)
    for line in lines:
        p = copy.deepcopy(ptpl)
        strip_lsa(p)
        runs = p.findall('hp:run', NS)
        for r in runs[1:]:
            p.remove(r)
        t = runs[0].find('hp:t', NS)
        if t is None:
            t = etree.SubElement(runs[0], q('t'))
        for c in list(t):
            t.remove(c)
        t.text = line
        sub.append(p)
    tc.find('hp:cellAddr', NS).attrib.update({'colAddr': str(col), 'rowAddr': str(row)})
    tc.find('hp:cellSpan', NS).attrib.update({'colSpan': '1', 'rowSpan': str(rowspan)})
    tc.find('hp:cellSz', NS).attrib.update({'width': str(w), 'height': str(h)})


def side_table(side_lines, rows, widths=(6000, 9800, 30124), lh=1800):
    """rows=[(label, [content lines])]. 왼쪽 진한 칸이 전체 행을 rowSpan으로 덮는다."""
    p = copy.deepcopy(P_SIDETBL)
    strip_lsa(p)
    tbl = p.find('.//hp:tbl', NS)
    _tid[0] += 1
    tbl.set('id', str(_tid[0]))
    trs = tbl.findall('hp:tr', NS)
    tc_side = copy.deepcopy(trs[0].findall('hp:tc', NS)[0])
    tc_lab = copy.deepcopy(trs[0].findall('hp:tc', NS)[1])
    tc_con = copy.deepcopy(trs[0].findall('hp:tc', NS)[2])
    for tr in trs:
        tbl.remove(tr)
    heights = [max(len(c), 1) * lh + 600 for _, c in rows]
    total = sum(heights)
    for i, ((lab, con), h) in enumerate(zip(rows, heights)):
        tr = etree.SubElement(tbl, q('tr'))
        if i == 0:
            c = copy.deepcopy(tc_side)
            set_cell(c, side_lines, 0, 0, widths[0], total, rowspan=len(rows))
            tr.append(c)
        c = copy.deepcopy(tc_lab)
        set_cell(c, [lab], 1, i, widths[1], h)
        tr.append(c)
        c = copy.deepcopy(tc_con)
        set_cell(c, con, 2, i, widths[2], h)
        tr.append(c)
    tbl.set('rowCnt', str(len(rows)))
    tbl.find('hp:sz', NS).set('height', str(total))
    return p


def side_table_n(side_lines, rows, widths, center_cols=(1, 2), lh=1800):
    """rows=[(label, [col lines], [col lines], ...)]. 왼쪽 진한 칸 rowSpan + 라벨 + 여러 내용 열."""
    p = copy.deepcopy(P_SIDETBL)
    strip_lsa(p)
    tbl = p.find('.//hp:tbl', NS)
    _tid[0] += 1
    tbl.set('id', str(_tid[0]))
    trs = tbl.findall('hp:tr', NS)
    tc_side, tc_lab, tc_con = [copy.deepcopy(x) for x in trs[0].findall('hp:tc', NS)]
    for tr in trs:
        tbl.remove(tr)
    heights = [max(len(c) for c in r[1:]) * lh + 600 for r in rows]
    total = sum(heights)
    for i, (r, h) in enumerate(zip(rows, heights)):
        tr = etree.SubElement(tbl, q('tr'))
        if i == 0:
            c = copy.deepcopy(tc_side)
            set_cell(c, side_lines, 0, 0, widths[0], total, rowspan=len(rows))
            tr.append(c)
        c = copy.deepcopy(tc_lab)
        set_cell(c, [r[0]], 1, i, widths[1], h)
        tr.append(c)
        for j, lines in enumerate(r[1:], start=2):
            c = copy.deepcopy(tc_con)
            set_cell(c, lines, j, i, widths[j], h)
            if j in center_cols:
                for pp in c.iter(q('p')):
                    pp.set('paraPrIDRef', '4')
            tr.append(c)
    tbl.set('rowCnt', str(len(rows)))
    tbl.set('colCnt', str(len(widths)))
    tbl.find('hp:sz', NS).set('height', str(total))
    return p


def grid_table(header, rows, widths, center_cols=(0,), lh=1500):
    """header=[...], rows=[[cell lines list,...],...]. 머리행은 진한 칸, 첫 열은 음영 칸."""
    p = copy.deepcopy(P_SIDETBL)
    strip_lsa(p)
    tbl = p.find('.//hp:tbl', NS)
    _tid[0] += 1
    tbl.set('id', str(_tid[0]))
    trs = tbl.findall('hp:tr', NS)
    tc_dark = copy.deepcopy(trs[0].findall('hp:tc', NS)[0])
    tc_lab = copy.deepcopy(trs[0].findall('hp:tc', NS)[1])
    tc_con = copy.deepcopy(trs[0].findall('hp:tc', NS)[2])
    for tr in trs:
        tbl.remove(tr)
    total = 0
    allrows = [[[h] for h in header]] + rows
    for i, row in enumerate(allrows):
        est = [1, -(-len(''.join(row[1])) // 14), -(-len(''.join(row[2])) // 45)] if i else [1]
        h = max(est) * lh + (450 if max(est) == 1 else 450 + 250 * max(est))
        total += h
        tr = etree.SubElement(tbl, q('tr'))
        for j, lines in enumerate(row):
            proto = tc_dark if i == 0 else (tc_lab if j == 0 else tc_con)
            c = copy.deepcopy(proto)
            set_cell(c, lines, j, i, widths[j], h)
            for rr in c.iter(q('run')):
                rr.set('charPrIDRef', '66' if i == 0 else '61')
            if i > 0 and j not in center_cols:
                for pp in c.iter(q('p')):
                    pp.set('paraPrIDRef', '3')
            tr.append(c)
    tbl.set('rowCnt', str(len(allrows)))
    tbl.set('colCnt', str(len(header)))
    tbl.find('hp:sz', NS).attrib.update({'height': str(total), 'width': str(sum(widths))})
    return p


def free_table(rows, widths, lh=1350, extra=250, gap_h=400):
    """rows=[[(lines, kind, charPr, align)]]. kind: dark(진한 머리)·lab(음영)·con(흰 칸)·none(테두리 없음).
    align: 'c' 가운데(paraPr 4), 'l' 왼쪽(paraPr 3). 행 높이는 열 폭 대비 글자 수로 줄 수를 어림한다."""
    p = copy.deepcopy(P_SIDETBL)
    strip_lsa(p)
    tbl = p.find('.//hp:tbl', NS)
    _tid[0] += 1
    tbl.set('id', str(_tid[0]))
    trs = tbl.findall('hp:tr', NS)
    proto = dict(zip(('dark', 'lab', 'con'), [copy.deepcopy(x) for x in trs[0].findall('hp:tc', NS)]))
    for tr in trs:
        tbl.remove(tr)
    total = 0
    for i, row in enumerate(rows):
        if row == 'GAP':
            tr = etree.SubElement(tbl, q('tr'))
            for j, w in enumerate(widths):
                c = copy.deepcopy(proto['con'])
                c.set('borderFillIDRef', '3')
                set_cell(c, [''], j, i, w, gap_h)
                for rr in c.iter(q('run')):
                    rr.set('charPrIDRef', '61')
                tr.append(c)
            total += gap_h
            continue
        n = 1
        for (lines, kind, cp, al), w in zip(row, widths):
            per = max((w - 800) // 850, 1)
            n = max(n, sum(max(-(-len(s) // per), 1) for s in lines))
        h = n * lh + 450 + (extra * n if n > 1 else 0)
        total += h
        tr = etree.SubElement(tbl, q('tr'))
        for j, ((lines, kind, cp, al), w) in enumerate(zip(row, widths)):
            c = copy.deepcopy(proto['con' if kind == 'none' else kind])
            if kind == 'none':
                c.set('borderFillIDRef', '3')
            set_cell(c, lines, j, i, w, h)
            for rr in c.iter(q('run')):
                rr.set('charPrIDRef', str(cp))
            for pp in c.iter(q('p')):
                pp.set('paraPrIDRef', '4' if al == 'c' else '3')
            tr.append(c)
    tbl.set('rowCnt', str(len(rows)))
    tbl.set('colCnt', str(len(widths)))
    tbl.find('hp:sz', NS).attrib.update({'height': str(total), 'width': str(sum(widths))})
    return p


# ---------- 내용 ----------
body = []
A = body.append


def sect(num, title):
    A(sechead(num, title))
    A(gap(P_GAP_AFTER_HEAD))


def para(x):
    A(x)
    A(gap())


def table(x):
    A(gap(P_GAP_BEFORE_TBL))
    A(x)
    A(gap(P_GAP_AFTER_TBL))


sect('1.', '배경 및 결론 요약')
para(box('배경', '주총 안건을 대량으로 모아 비교하려면 안건 유형을 공시에서 바로 식별할 수 있어야 함'))
para(box('결론 요약', '한국은 발행회사 소집공고에 안건유형 표준코드가 있어 기계판독 가능, 미국 발행회사 공시에는 없음',
         bold='안건유형 표준코드'))
para(o('단, 한국도 코드는 ‘유형’ 단위까지이며, 가장 먼저 나오는 거래소 소집결의 공시에는 코드가 없음'))

sect('2.', '한국: 소집공고의 안건유형 표준코드')
para(box('코드 체계', '소집공고 XML의 안건 절마다 코드(L0-0-2-N-0)가 붙고, N은 증권발행공시규정 제3-15조③의 호 번호와 일치',
         bold='호 번호와 일치'))
table(side_table(['안건유형', '코드 20종'], [
    ('1 ~ 5호', ['재무제표 승인, 정관 변경, 이사·감사위원·감사 선임']),
    ('6 ~ 10호', ['이사·감사위원·감사 해임, 이사·감사 보수한도']),
    ('11 ~ 15호', ['주식매수선택권, 합병, 분할, 영업양수도, 주식교환']),
    ('16 ~ 20호', ['준비금 자본전입, 제3자 신주인수권, 액면미달 발행,', '자본 감소, 기타']),
]))
A(note('*', '코드별 한글·영문 명칭은 붙임 참조'))
A(gap())

sect('3.', '미국 SEC 정기주총 서식과 비교')
body[-2].set('pageBreak', '1')
table(side_table_n(['발행사가', '제출하는', '정기주총', '공시서식'], [
    ('PRE 14A', ['HTML'], ['예비 위임장설명서(일상 외 안건 시)']),
    ('DEF 14A', ['HTML(iXBRL)'], ['확정 위임장설명서', '(표지·임원보수 항목만 iXBRL 태깅)']),
    ('ARS', ['PDF'], ['주주용 연차보고서']),
    ('8-K 5.07', ['HTML(iXBRL)'], ['표결 결과', '(발행사 식별정보만 iXBRL 태깅)']),
], widths=(6000, 7800, 12400, 19724)))
A(note('*', '정기주총 서식 모두 안건유형 코드 없음'))
A(gap())
para(o('안건은 회사마다 제목·순서가 다른 서술형이라, 안건 유형을 알려면 문서마다 텍스트를 읽어 해석해야 함'))
para(runs_para(P_O, [(34, ' ⇒ '), (43, '정기주총 서식에 안건 분류조차 없는 미국과 비교하면, 안건유형이라도 표준코드로 분류해 둔 한국 공시는 '), (35, '데이터 활용 면에서 분명한 장점')]))

sect('4.', '한국 공시의 한계')
body[-2].set('pageBreak', '1')
A(box('유형 단위', '코드는 유형별 절 제목에 1개만 붙고, 해당 유형의 안건이 여러 개 있더라도 안건 개수만큼 태그가 붙지 않음'))
para(dash('해당 유형의 안건이 몇 건 있었는지 알 수 없음'))
para(o('또한 안건 유형 외의 안건 설명자료(후보자명·보수한도 금액·정관 내용 등)는 태그 없는 줄글·표'))
A(o('예: 현대비앤지스틸 ’25 정기주총 소집공고 — 의안 8건에 코드 4개'))
H, L, C = (lambda s: ([s], 'dark', 66, 'c')), (lambda *s: (list(s), 'lab', 61, 'c')), (lambda *s: (list(s), 'none', 61, 'l'))
CC = (lambda s: ([s], 'none', 61, 'c'))
table(free_table([
    [H('안건유형 코드(태그 ○)'), H('그 아래 줄글로 적힌 의안(태그 ✕)'), H('의안 수')],
    [L('1호 재무제표의 승인'), C('── 제1호 재무제표 승인'), CC('1건')],
    [L('3호 이사의 선임'), C('┬─ 제2-1호 사내이사 선임', '├─ 제2-2호 사내이사 선임', '├─ 제2-3호 사외이사 선임',
                             '└─ 제3호 감사위원이 되는 사외이사 선임'), CC('4건')],
    [L('4호 감사위원회 위원의 선임'), C('── 제4호 감사위원 선임'), CC('1건')],
    [L('9호 이사의 보수한도 승인'), C('┬─ 제5-1호 이사 보수한도 50억원', '└─ 제5-2호 임원 퇴임위로금 규정 개정 ← 별개 안건'), CC('2건')],
], widths=(15000, 25924, 5000), lh=1150, extra=50, gap_h=200))
para(dash('코드만으로는 선임 인원이나 퇴임위로금 규정 개정 여부를 알 수 없음'))
para(box('회사 선택', '코드를 회사가 직접 골라 오분류 사례가 있고, ‘기타’(20호)가 공고의 15%를 차지'))
A(box('공시 시점', '거래소 소집결의는 소집공고보다 열흘가량 먼저, 주총결과는 당일 나오지만 모두 금감원 안건코드가 없는 HTML 양식',
         bold='금감원 안건코드가 없는 HTML 양식'))
N = ([''], 'none', 61, 'c')
AR = (['▶'], 'none', 61, 'c')
S = (lambda *s: (list(s), 'lab', 61, 'c'))
K = (lambda s, cp=61: ([s], 'con', cp, 'c'))
table(free_table([
    [H('D-28일'), N, H('D-15일'), N, H('D (주총 당일)')],
    [S('거래소', '주주총회소집결의'), AR, S('금감원', '주주총회소집공고'), AR, S('거래소', '주주총회결과')],
    [K('HTML(KIND 양식)'), N, K('XML(DART 양식)'), N, K('HTML(KIND 양식)')],
    [K('금감원 안건코드 ✕'), N, K('금감원 안건코드 ○', 16), N, K('금감원 안건코드 ✕')],
], widths=(12500, 4212, 12500, 4212, 12500)))
A(note('*', 'D-일수는 ’21년 이후 상장사 공고 131건의 주총일 기준 중앙값'))

# ---------- 붙임 ----------
import json as _json
NAMES = _json.load(open(sys.argv[5], encoding='utf-8'))
LAW = {7: '감사위원회 위원의 해임', 16: '준비금의 자본전입 또는 이에 따른 신주 발행',
       17: '주주 외의 자에게 신주의 인수권 부여'}
hd = runs_para(P_BOX, [(35, '[붙임] 주주총회 소집공고 안건유형 코드 목록')])
hd.set('pageBreak', '1')
A(hd)
A(gap())
para(o('코드명은 별도 목록 없이 절 제목이 대신(’25년 서식부터 영문 병기)'))


def wrap(text, n):
    out, line = [], ''
    for w in text.split(' '):
        if line and len(line) + 1 + len(w) > n:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    return out + ([line] if line else [])


# 영문 제목이 실제 공고에 없는 호(영문 병기 서식 ’25.2~ 이후 사용 공고 0건) — 기존 ENG 문체에 맞춘 임의 번역
TRANS = {17: 'Grant of pre-emptive rights to persons other than shareholders',
         18: 'Issuance of shares below par value'}
rows = []
for n in range(1, 21):
    for sub in (0,):
        code = 'L0-0-2-%d-%d' % (n, sub)
        nm = NAMES.get(code)
        ko = nm['ko'] if nm else LAW[n] + '*'
        en = (nm['en'] if nm and nm['en'] else TRANS[n] + '*')
        rows.append([[code], [ko], [en]])
table(grid_table(['코드번호', '한글 코드명', '영문 코드명'], rows, (7000, 15000, 23924), lh=1350))
A(note('*', '17·18호는 영문 제목을 쓴 공고가 없어 임의 번역(금감원 확인 필요)'))


# ---------- 조립 ----------
for p in ps[1:]:
    root.remove(p)
t1 = copy.deepcopy(P_TITLE)
strip_lsa(t1)
for p in list(t1.iter(q('p'))):
    for r in p.findall('hp:run', NS):
        if r.get('charPrIDRef') == '59':      # 부제 줄은 지운다
            p.getparent().remove(p)
            break
        elif r.get('charPrIDRef') == '27':
            r.find('hp:t', NS).text = '주총 안건 데이터 기계판독성 한·미 비교'
# 제목 칸(두 줄 → 한 줄) 높이 줄이기
_tt = t1.find('.//hp:tbl', NS)
_cs = _tt.findall('hp:tr', NS)[1].find('.//hp:cellSz', NS)
_d = int(_cs.get('height')) - 3400
_cs.set('height', '3400')
_tt.find('hp:sz', NS).set('height', str(int(_tt.find('hp:sz', NS).get('height')) - _d))
# 맨 앞 '검토자료' 상자(로고 포함 표) 제거 — secPr·쪽번호 ctrl 은 남긴다
for _tb in ps[0].findall('.//hp:tbl', NS):
    _tb.getparent().remove(_tb)
strip_lsa(ps[0])
root.append(t1)
for x in body:
    root.append(x)
tree.write(out_sec, xml_declaration=True, encoding='UTF-8', standalone=True)

# ---------- 글꼴: 명조 계열 → HY신명조 ----------
ht = etree.parse(ref_head)
n = 0
for f in ht.getroot().iter('{%s}font' % HH):
    if f.get('face') in ('휴먼명조', '한양신명조', '명조'):
        f.set('face', 'HY신명조')
        f.set('type', 'TTF')
        n += 1
ht.write(out_head, xml_declaration=True, encoding='UTF-8', standalone=True)
print('body paragraphs', len(body), 'fonts renamed', n)
