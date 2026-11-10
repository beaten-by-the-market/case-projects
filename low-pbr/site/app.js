/* 저PBR 선정 재현 — 단계별 화면. data.js(window.DATA) 만 읽는다. 없는 데이터는 '수집 중'. */
(() => {
  const D = window.DATA;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const W = '<span class="wait">수집 중</span>';
  const dash = '<span class="wait">–</span>';
  const eok = (v) => (v == null || v === "" ? dash : Math.round(v / 1e8).toLocaleString("ko-KR"));
  const eok1 = (v) => (v == null || v === "" ? dash : Math.round(v).toLocaleString("ko-KR"));   // 이미 억 단위
  const won = (v) => (v == null ? dash : Number(v).toLocaleString("ko-KR"));
  const f2 = (v) => (v == null || v === "" ? dash : Number(v).toFixed(2));
  const ymd = (s) => (s ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : "");
  const mk = (m) => (m ? `<span class="mk ${m}">${m === "KOSPI" ? "유가" : "코스닥"}</span>` : "");
  const A = (url, t) => (url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(t)}</a>` : esc(t));
  const yes = (v) => v === true || v === "True";
  const same = (a, b) => a != null && b != null && Math.abs(Number(a) - Number(b)) < 1e-9;

  const rep = D.replica;
  const sel = rep ? Object.fromEntries(rep.selection.map((s) => [s.code, s])) : {};
  const grid = D.grid || {};
  const firms = D.firms || {};
  const kindBy = Object.fromEntries((D.kind || []).filter((k) => k.code).map((k) => [k.code, k]));
  const planBy = Object.fromEntries((D.plans || []).filter((p) => p.code).map((p) => [p.code, p]));
  const exclBy = Object.fromEntries((D.univ26?.excluded || []).map((x) => [x.code, x]));
  const keptBy = Object.fromEntries((D.univ26?.kept_admin || []).map((x) => [x.code, x]));
  const cov = D.coverage || {};
  const full = cov.equity >= cov.universe - 5;
  const partial = rep && !full;
  const g13 = (code) => grid[code]?.r?.["13"];
  const pbrOf = (code) => g13(code)?.[0] ?? firms[code]?.rounds?.at(-1)?.pbr_dart ?? null;
  const press = (m, item) => (D.press.totals.find((t) => t.market === m && t.item === item) || {}).value;
  const cnt = (arr, f) => ({ KOSPI: arr.filter((x) => x.market === "KOSPI" && f(x)).length, KOSDAQ: arr.filter((x) => x.market === "KOSDAQ" && f(x)).length });
  const vuBefore = (code) => ((D.valueup || {})[String(code).slice(0, 5)] || []).filter((v) => v.dt <= "2026-10-22 23:59");

  /* ---------- 공통 숫자 ---------- */
  const selArr = rep ? rep.selection : [];
  const univRep = { KOSPI: 0, KOSDAQ: 0 };
  Object.values(grid).forEach((g) => { if (g.r["13"]) univRep[g.m]++; });
  const R = rep ? { sel: cnt(selArr, (s) => yes(s.selected)), ex: cnt(selArr, (s) => yes(s.exempt)), pub: cnt(selArr, (s) => yes(s.published)) } : null;
  const kindCodes = new Set(Object.keys(kindBy));
  const pubCodes = new Set(selArr.filter((s) => yes(s.published)).map((s) => s.code));
  const matchN = [...kindCodes].filter((c) => pubCodes.has(c)).length;
  const kPairs = [...kindCodes].filter((c) => pbrOf(c) != null);
  const kOk = kPairs.filter((c) => same(pbrOf(c), kindBy[c].pbr)).length;
  const secRows = D.press.sector.filter((p) => p.cut_pbr !== "");
  const repSec = rep ? Object.fromEntries(rep.sector.map((s) => [`${s.market}|${s.gics}`, s])) : {};
  const cutOk = rep ? secRows.filter((p) => same(repSec[`${p.market}|${p.gics}`]?.cut, p.cut_pbr)).length : null;
  const pair = (a, b) => `${a}·${b}`;
  const markOf = (okv) => (okv == null ? '<span class="mark wait">대기</span>' : partial ? '<span class="mark wait">부분</span>' : okv ? '<span class="mark ok">일치</span>' : '<span class="mark bad">차이</span>');
  const eq2 = (x, m1, m2) => x && x.KOSPI === m1 && x.KOSDAQ === m2;

  /* ---------- 머리말 ---------- */
  $("#badge").textContent = `${full ? "판정 완료" : rep ? "부분 판정" : "수집 중"} · 순자산 ${(cov.equity || 0).toLocaleString()}/${(cov.universe || 0).toLocaleString()}사 · 생성 ${D.built}`;

  /* ---------- 단계 막대 ---------- */
  const STEPS = [
    ["p0", "", "한눈에", "", ""],
    ["p1", "1", "모집단", `보도 <b>2,431</b>`, `재현 ${pair(univRep.KOSPI, univRep.KOSDAQ)} ${markOf(rep ? eq2(univRep, 779, 1652) : null)}`],
    ["p2", "2", "PBR 계산", `KIND PBR 대조`, `<b>${kOk}</b>/${kPairs.length} ${markOf(kPairs.length ? kOk === kPairs.length : null)}`],
    ["p3", "3", "업종 기준선", `업종 22개`, `컷 일치 ${cutOk ?? "–"}/22 ${markOf(rep ? cutOk === 22 : null)}`],
    ["p4", "4", "6반기 지속", `보도 <b>185</b> (115·70)`, `재현 ${R ? pair(R.sel.KOSPI, R.sel.KOSDAQ) : "–"} ${markOf(R ? eq2(R.sel, 115, 70) : null)}`],
    ["p5", "5", "공표 면제", `보도 <b>−34</b> (19·15)`, `재현 ${R ? pair(R.ex.KOSPI, R.ex.KOSDAQ) : "–"} ${markOf(R ? eq2(R.ex, 19, 15) : null)}`],
    ["p6", "6", "공표 ↔ KIND", `보도 <b>151</b> (96·55)`, `KIND 일치 ${rep ? matchN : "–"}/151 ${markOf(rep ? matchN === 151 && pubCodes.size === 151 : null)}`],
  ];
  $("#stepper").innerHTML = `<div class="in">${STEPS.map(([id, n, t, a, b], i) =>
    `${i > 1 ? '<span class="arrow">→</span>' : ""}<button data-id="${id}" class="${id === "p0" ? "home" : ""}">
      <div class="n">${n ? `단계 ${n}` : "&nbsp;"}</div><div class="t">${t}</div>${a ? `<div class="v">${a}</div><div class="v">${b}</div>` : ""}</button>`).join("")}</div>`;
  const show = (id) => {
    document.querySelectorAll("section.pane").forEach((s) => s.classList.toggle("on", s.id === id));
    document.querySelectorAll("#stepper button").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
    try { localStorage.setItem("lowpbr-step", id); } catch (e) { /* 저장 불가 */ }
    window.scrollTo({ top: 0 });
  };
  $("#stepper").onclick = (e) => { const b = e.target.closest("button"); if (b) show(b.dataset.id); };

  const three = (rule, src, cards, body) => `<div class="three"><div class="rule"><h3>규칙</h3>${rule}<div class="src">${src}</div></div>
    <div><div class="cards">${cards}</div>${body || ""}</div></div>`;
  const card = (t, v, s) => `<div class="c1"><div class="t">${t}</div><div class="v">${v}</div><div class="s">${s || ""}</div></div>`;
  const strip = (flags, opts = {}) => {
    if (!flags) return dash;
    return `<span class="strip" title="1→13 회차 (오른쪽이 2026.11)">${[...flags].map((c, i) => {
      const s = i + 1;
      const cls = [c === "1" ? "y" : c === "·" ? "na" : "", s >= 8 && !opts.twelve ? "w6" : "", s === 7 && !opts.twelve ? "w7" : "", opts.twelve && s >= 2 ? "w6" : ""].join(" ");
      return `<i class="${cls}"></i>`;
    }).join("")}</span>`;
  };
  const flagsOf = (code) => {
    if (sel[code]?.flags_1_13) return sel[code].flags_1_13;
    const g = grid[code];
    if (!g) return null;
    return Array.from({ length: 13 }, (_, i) => { const r = g.r[String(i + 1)]; return !r ? "·" : r[0] == null ? "·" : r[4] ? "1" : "0"; }).join("");
  };
  const legend = `<div class="legend"><span><span class="strip"><i class="y"></i></span> 그 회차 업종 기준선 이하(저PBR)</span>
    <span><span class="strip"><i></i></span> 기준선 위</span><span><span class="strip"><i class="na"></i></span> 미상장·자료 없음</span>
    <span><span class="strip"><i class="w6"></i></span> 최근 6개 기준일(8~13)</span><span><span class="strip"><i class="w7"></i></span> 7번째(직전) 기준일</span></div>`;

  /* ========== 0. 한눈에 ========== */
  const plans = D.plans || [];
  const pubPlans = plans.filter((p) => p.published);
  $("#p0").innerHTML = `
    <h2>거래소가 공표한 151사를 공개 데이터로 다시 고르면 같은 151사가 나오는가</h2>
    <p class="lead">단계마다 보도자료 숫자와 재현 숫자를 나란히 놓았다. 위 막대에서 단계를 누르면 그 단계의 규칙, 결과, 빠지거나 남은 회사를 볼 수 있다.
      회사 하나가 어떤 관문을 지났는지는 오른쪽 위 <b>회사 추적</b>에서 이름을 입력하면 된다.</p>
    <div class="cards" style="margin-top:12px">
      ${card("① 모집단", "2,431", `유가 779 · 코스닥 1,652<br>재현 ${pair(univRep.KOSPI, univRep.KOSDAQ)}`)}
      ${card("④ 저PBR 요건 해당", "185", `115 · 70<br>재현 ${R ? pair(R.sel.KOSPI, R.sel.KOSDAQ) : W}`)}
      ${card("⑤ 공표 제외", "34", `19 · 15<br>재현 ${R ? pair(R.ex.KOSPI, R.ex.KOSDAQ) : W}`)}
      ${card("⑥ 공표", "151", `96 · 55<br>재현 ${R ? pair(R.pub.KOSPI, R.pub.KOSDAQ) : W} · KIND 일치 ${rep ? matchN : "–"}`)}
    </div>
    ${partial ? `<p class="notice">지금 판정은 <b>부분 판정</b>이다 — 순자산을 받은 ${cov.equity.toLocaleString()}/${cov.universe.toLocaleString()}사만으로 업종 순위를 매겨서 선정 수가 모자라다. 수집이 끝나면 저절로 바뀐다.</p>` : ""}
    <h2>지금까지 확인한 것</h2>
    <ul>
      <li><b>PBR 분모는 "자본총계"가 아니라 지배기업 소유주지분</b>(연결재무제표가 없으면 별도 자본총계)이다. 이 정의로 KIND 공표 PBR 과 <b>${kOk}/${kPairs.length}</b> 일치, 연결 자본총계로는 절반 정도만 맞는다(지주사가 크게 어긋남).</li>
      <li>KIND 공시 제목 "(PBR 개선 계획 제출 기업)"으로 찾은 10.22 까지 제출사 <b>${plans.length}사</b>(유가 ${plans.filter((p) => p.market === "KOSPI").length}·코스닥 ${plans.filter((p) => p.market === "KOSDAQ").length}) = 보도자료 62사(34·28).
        그중 공표된 <b>${pubPlans.length}사</b> = 보도자료 "공표 제외 불가 10·5".</li>
      <li>결산월이 12월이 아닌 회사(기신정기 3월·세원정공 6월 등)는 "기준일 전 마지막 정기보고서" 규칙에 따라 11월 회차에 <b>사업보고서</b>가 쓰인다 — KIND 값과 일치.</li>
      <li>시가총액·주가 미달로 8월에 관리종목이 된 SUN&L·한국전자홀딩스 등도 공표됐다 — 이 사유의 관리종목은 모집단에서 빼지 않았다.</li>
    </ul>
    <details class="more"><summary>수집·판정 진행 상황</summary>
      <div class="tbl-wrap"><table class="list"><thead><tr><th>단계</th><th>원천</th><th class="c">상태</th><th>내용</th><th>갱신</th></tr></thead><tbody>${
        D.status.map((s) => `<tr><td>${esc(s.step)}</td><td>${esc(s.src)}</td><td class="c"><span class="state ${s.state}">${{ done: "완료", running: "진행 중", waiting: "대기" }[s.state]}</span></td>
        <td>${esc(s.detail)}${s.pct != null ? `<div class="bar"><i style="width:${s.pct}%"></i></div>` : ""}</td><td class="small">${esc(s.updated)}</td></tr>`).join("")}</tbody></table></div>
    </details>`;

  /* ========== 1. 모집단 ========== */
  const U = D.univ26 || { listed: {}, excluded: [], kept_admin: [] };
  const exC = cnt(U.excluded, () => true);
  const uni = Object.fromEntries((D.universe || []).map((u) => [u.round, u]));
  $("#p1").innerHTML = `<h2>단계 1 · 모집단 — 누구의 PBR 을 계산하나</h2>` + three(
    `<p>기준일(10.22) 현재 상장된 주권 가운데 외국기업·스팩·투자회사·리츠 등 특수회사와 관리종목·환기종목·실질심사 중인 회사를 뺀다.</p>
     <p><b>실측:</b> 시가총액·주가 미달(2026년 신설 요건)로 지정된 관리종목은 빼지 않았다 — 그런 회사가 공표 목록에 있다.</p>`,
    "지침 해설(김앤장 2026.9.14) · KIND 상장종목현황(기준일 스냅샷) · KIND 관리종목",
    card("상장 주권(10.22)", pair(U.listed.KOSPI ?? "–", U.listed.KOSDAQ ?? "–"), "KIND 스냅샷, 스팩·외국·리츠 이미 제외") +
    card("관리종목 제외", `−${pair(exC.KOSPI, exC.KOSDAQ)}`, "시총·주가 미달 단독 사유는 남김") +
    card("재현 모집단", pair((U.listed.KOSPI ?? 0) - exC.KOSPI, (U.listed.KOSDAQ ?? 0) - exC.KOSDAQ), "") +
    card("보도자료", "779·1,652", `남은 차이 ${(U.listed.KOSPI ?? 0) - exC.KOSPI - 779}·${(U.listed.KOSDAQ ?? 0) - exC.KOSDAQ - 1652} — 거래정지·실질심사 등 확인 중`),
    `<h3>빠진 회사 (${U.excluded.length})</h3>
     <div class="tbl-wrap"><table class="list"><thead><tr><th>회사</th><th>지정일</th><th>지정사유</th></tr></thead><tbody>${
       U.excluded.map((x) => `<tr class="click" data-code="${x.code}"><td>${mk(x.market)}${esc(x.name)}</td><td>${esc(x.date)}</td><td class="reason">${esc(x.reason)}</td></tr>`).join("")}</tbody></table></div>
     <details class="more"><summary>관리종목이지만 남긴 회사 (${U.kept_admin.length}) — 시총·주가 미달 단독 사유</summary>
     <div class="tbl-wrap"><table class="list"><thead><tr><th>회사</th><th>지정일</th><th>지정사유</th><th>KIND 공표</th></tr></thead><tbody>${
       U.kept_admin.map((x) => `<tr class="click" data-code="${x.code}"><td>${mk(x.market)}${esc(x.name)}</td><td>${esc(x.date)}</td><td class="reason">${esc(x.reason)}</td><td>${kindBy[x.code] ? '<span class="ok">공표됨</span>' : ""}</td></tr>`).join("")}</tbody></table></div></details>
     <details class="more"><summary>13개 회차 일정과 회차별 상장 주권 수</summary>
     <div class="tbl-wrap"><table class="list"><thead><tr><th>회차</th><th>공표일</th><th>PBR 기준일</th><th>시가총액 구간(20거래일)</th><th>순자산 근거(12월 결산법인)</th><th class="num">유가</th><th class="num">코스닥</th><th>쓰임</th></tr></thead><tbody>${
       D.rounds.slice().reverse().map((r) => { const s = Number(r.seq); return `<tr><td>${r.round}</td><td>${ymd(r.pub_date)}</td><td>${ymd(r.base_date)}</td><td>${ymd(r.win_start)} ~ ${ymd(r.win_end)}</td>
         <td>${r.report_kind === "annual" ? "사업보고서" : "반기보고서"} (${r.period_end.slice(0, 7)})</td><td class="num">${uni[r.round]?.KOSPI ?? "–"}</td><td class="num">${uni[r.round]?.KOSDAQ ?? "–"}</td>
         <td class="small">${s >= 8 ? "선정: 최근 6" : s === 7 ? "선정: 7번째" : "면제 불가: 12·13"}</td></tr>`; }).join("")}</tbody></table>
     <p class="small">결산월이 다른 회사는 회차마다 "기준일 전에 제출된 마지막 사업·반기보고서"를 따로 고른다(예: 6월 결산 세원정공은 11월 회차에 사업보고서).</p></div></details>`);

  /* ========== 2. PBR 계산 ========== */
  const ex = D.example;
  let exHtml = "";
  if (ex) {
    const tot = ex.days.map((d) => d.common + d.pref);
    const avg = tot.reduce((a, b) => a + b, 0) / tot.length;
    const r = ex.round;
    const pbr = r.eq_base ? Math.floor((avg / r.eq_base) * 100 + 1e-9) / 100 : null;
    exHtml = `<h3>계산 예시 — ${esc(ex.name)} (2026.11 회차)</h3>
      <div class="three" style="grid-template-columns: 1fr 1fr">
        <div><table class="detail"><tbody>
          <tr><th>① 20거래일 평균 시가총액</th><td>${ymd(ex.days[0].date)} ~ ${ymd(ex.days.at(-1).date)} · <b>${won(Math.round(avg))}원</b> (${eok(avg)}억)<div class="small">CHECK /stock/m001/hist_info 시가총액(F15028), 종류주 ${ex.days.some((d) => d.pref) ? "포함" : "없음"}</div></td></tr>
          <tr><th>② 기준일 현재 최근 정기보고서</th><td>${A(r.main_url, r.report_nm)} <span class="small">접수 ${ymd(r.rcept_dt)}</span></td></tr>
          <tr><th>③ 지배기업 소유주지분</th><td><b>${won(r.eq_base)}원</b> (${eok(r.eq_base)}억)<div class="small">${A(r.viewer_url, r.toc_path || "재무상태표")} · 연결 자본총계 ${eok(r.con_total)}억(비지배지분 포함)은 쓰지 않는다</div></td></tr>
          <tr><th>④ PBR</th><td>① ÷ ③ = ${(avg / r.eq_base).toFixed(4)} → 소수 셋째 자리 절사 <b class="hl">${f2(pbr)}</b> · KIND ${kindBy[ex.code]?.pbr ?? ""} ${same(pbr, kindBy[ex.code]?.pbr) ? '<span class="ok">일치</span>' : ""}</td></tr>
        </tbody></table>
        <details class="more"><summary>20거래일 시가총액 보기</summary><table class="list"><thead><tr><th>날짜</th><th class="num">종가</th><th class="num">보통주(억)</th><th class="num">종류주(억)</th></tr></thead><tbody>${
          ex.days.map((d) => `<tr><td>${ymd(d.date)}</td><td class="num">${won(d.close)}</td><td class="num">${eok(d.common)}</td><td class="num">${eok(d.pref)}</td></tr>`).join("")}</tbody></table></details></div>
        <div>${r.capture ? `<a href="${esc(r.viewer_url)}" target="_blank" rel="noopener"><img src="${esc(r.capture)}" style="width:100%;border:1px solid var(--line-soft)" alt="재무상태표 캡처"></a><div class="small">DART 원문 재무상태표 — 누르면 원문 목차 위치로 간다</div>` : `<p class="desc">캡처 ${W}</p>`}</div>
      </div>`;
  }
  const pbrRows = Object.entries(grid).filter(([, g]) => g.r["13"]).map(([code, g]) => ({ code, g, r: g.r["13"], k: kindBy[code] }))
    .concat(Object.keys(kindBy).filter((c) => !grid[c]?.r?.["13"] && firms[c]).map((c) => ({ code: c, g: { n: firms[c].name, m: firms[c].market, g: kindBy[c].gics }, r: null, k: kindBy[c] })));
  const gicsList = [...new Set(D.press.sector.map((p) => p.gics))];
  $("#p2").innerHTML = `<h2>단계 2 · PBR 계산 — 기준일 PBR 을 어떻게 셌나</h2>` + three(
    `<p>PBR = <b>기준일 포함 20거래일 평균 시가총액</b>(보통주 + 상장 종류주) ÷ <b>기준일 현재 최근 정기보고서</b>(사업·반기, 분기 제외)의 <b>지배기업 소유주지분</b>.</p>
     <p>연결재무제표가 없으면 별도 자본총계. 소수 셋째 자리 이하 절사.</p>
     <p class="small">보도자료 주1은 "자본총계"라고 쓰지만 KIND 공표 PBR 과 맞는 것은 지배지분이다.</p>`,
    "보도자료 주1 · 시가총액 CHECK · 자본 CHECK IFRS 115020 / DART 원문",
    card("KIND PBR 대조", `${kOk}/${kPairs.length}`, "소수 둘째 자리까지") +
    card("PBR 산정", `${pbrRows.filter((x) => x.r && x.r[0] != null).length.toLocaleString()}사`, `2026.11 회차 · 모집단 ${(univRep.KOSPI + univRep.KOSDAQ).toLocaleString()}`),
    exHtml + `<h3>회사별 PBR (2026.11)</h3>
     <div class="search"><label>시장 <select id="f2-mk"><option value="">전체</option><option>KOSPI</option><option>KOSDAQ</option></select></label>
       <label>업종 <select id="f2-g"><option value="">전체</option>${gicsList.map((g) => `<option>${g}</option>`).join("")}</select></label>
       <label>범위 <select id="f2-k"><option value="kind">KIND 공표사</option><option value="">전체</option></select></label>
       <label>회사 <input id="f2-q" placeholder="이름·코드"></label><span class="cnt" id="f2-c"></span></div>
     <div class="tbl-wrap"><table class="list" id="t2"></table></div>`);
  const draw2 = () => {
    const m = $("#f2-mk").value, g = $("#f2-g").value, k = $("#f2-k").value, q = $("#f2-q").value.trim();
    let rows = pbrRows.filter((x) => (!m || x.g.m === m) && (!g || x.g.g === g) && (!k || x.k) && (!q || x.g.n.includes(q) || x.code.includes(q)));
    rows.sort((a, b) => (pbrOf(a.code) ?? 99) - (pbrOf(b.code) ?? 99));
    $("#f2-c").textContent = `${rows.length.toLocaleString()}사${rows.length > 300 ? " (앞 300사 표시)" : ""}`;
    rows = rows.slice(0, 300);
    $("#t2").innerHTML = `<thead><tr><th>회사</th><th>업종</th><th class="num">20일 평균 시총(억)</th><th class="num">지배지분 등(억)</th><th class="num">재현 PBR</th><th class="num">KIND PBR</th><th class="c">대조</th></tr></thead><tbody>${
      rows.map((x) => { const p = pbrOf(x.code); const fr = firms[x.code]?.rounds?.at(-1) || {};
        return `<tr class="click" data-code="${x.code}"><td>${mk(x.g.m)}${esc(x.g.n)} <span class="small">${x.code}</span></td><td>${esc(x.g.g)}</td>
        <td class="num">${x.r?.[5] != null ? eok1(x.r[5]) : fr.mktcap ? eok(fr.mktcap) : W}</td><td class="num">${x.r?.[6] != null ? eok1(x.r[6]) : fr.eq_base ? eok(fr.eq_base) : W}</td>
        <td class="num"><b>${f2(p)}</b></td><td class="num">${x.k?.pbr ?? ""}</td>
        <td class="c">${x.k ? (p == null ? dash : same(p, x.k.pbr) ? '<span class="ok">일치</span>' : '<span class="bad">불일치</span>') : ""}</td></tr>`; }).join("")}</tbody>`;
  };
  ["#f2-mk", "#f2-g", "#f2-k"].forEach((s) => ($(s).onchange = draw2));
  $("#f2-q").oninput = draw2;
  draw2();

  /* ========== 3. 업종 기준선 ========== */
  const dotPanel = (p) => {
    const pts = Object.entries(grid).filter(([, g]) => g.m === p.market && g.g === p.gics && g.r["13"]?.[0] != null).map(([c, g]) => ({ c, v: g.r["13"][0], low: g.r["13"][4] }));
    const rc = repSec[`${p.market}|${p.gics}`]?.cut;
    const pc = Number(p.cut_pbr);
    const xmax = Math.min(3, Math.max(1, pc * 3, (rc || 0) * 3));
    const X = (v) => 6 + (Math.min(v, xmax) / xmax) * 268;
    const dots = pts.map((d, i) => `<circle cx="${X(d.v).toFixed(1)}" cy="${(14 + ((i * 37) % 30)).toFixed(0)}" r="${kindBy[d.c] ? 3.2 : 2.4}"
      fill="${d.low ? "var(--accent)" : "#b9c1c7"}" ${kindBy[d.c] ? 'stroke="var(--navy)" stroke-width="1"' : ""}><title>${esc(grid[d.c].n)} ${d.v.toFixed(2)}</title></circle>`).join("");
    const ticks = [0, xmax / 2, xmax].map((t) => `<text x="${X(t)}" y="62" font-size="9" fill="#888" text-anchor="middle">${t.toFixed(1)}</text>`).join("");
    const ok = rc != null && same(rc, pc);
    return `<div class="d"><div class="h"><span>${mk(p.market)}<b>${p.gics}</b></span><span class="small">재현 ${pts.length}사 · 보도 ${p.n_univ}사</span></div>
      <div class="h small"><span>기준선 보도 <b>${pc.toFixed(2)}</b></span><span>재현 ${rc != null ? `<b class="${ok ? "ok" : "bad"}">${Number(rc).toFixed(2)}</b>` : "–"}</span></div>
      <svg viewBox="0 0 280 66"><line x1="6" x2="274" y1="48" y2="48" stroke="#ddd"/>${dots}
      <line x1="${X(pc)}" x2="${X(pc)}" y1="4" y2="50" stroke="var(--navy)" stroke-dasharray="3 2"/>
      ${rc != null ? `<line x1="${X(rc)}" x2="${X(rc)}" y1="4" y2="50" stroke="var(--accent)" stroke-width="1.5"/>` : ""}${ticks}</svg></div>`;
  };
  $("#p3").innerHTML = `<h2>단계 3 · 업종 기준선 — 같은 업종 안에서 얼마나 낮아야 하나</h2>` + three(
    `<p>시장(유가/코스닥) × GICS 11개 업종 안에서 PBR 하위 <b>25%(유가)</b>·<b>10%(코스닥)</b> 이내면 그 회차의 저PBR.</p>
     <p>업종 소속사가 유가 4사·코스닥 10사 미만이면 PBR 최저 1사. 업종미분류는 시장 전체가 비교집단.</p>
     <p class="small">점 하나 = 회사 하나(2026.11 PBR). 주황 = 기준선 이하, 진한 테두리 = KIND 공표사. 점선 = 보도자료 기준 PBR, 실선 = 재현 기준선.</p>`,
    "지침 해설 · 보도자료 붙임1 · 업종: CHECK WICS 를 GICS 로 근사 + KIND 151사 GICS 로 덮어씀",
    card("기준 PBR 일치", rep ? `${cutOk}/22` : W, "시장×업종") + card("업종 분류 원천", "WICS→GICS", "GICS 종목 매핑은 공개 데이터에 없음"),
    `<div class="dots" style="margin-top:12px">${secRows.map(dotPanel).join("")}</div>
     <details class="more"><summary>업종 표 (보도자료 붙임1 vs 재현)</summary><div class="tbl-wrap"><table class="list"><thead><tr><th>시장</th><th>업종</th><th class="num">기준 PBR</th><th class="num">산정대상</th><th class="num">선정</th><th class="num">제외</th><th class="num">공표</th>
       <th class="num">재현 기준</th><th class="num">재현 대상</th><th class="num">재현 선정</th><th class="num">재현 제외</th><th class="num">재현 공표</th></tr></thead><tbody>${
       D.press.sector.map((p) => { const r = repSec[`${p.market}|${p.gics}`] || {}; const c = (a, b) => (rep ? `<span class="${String(a) === String(b) ? "ok" : "bad"}">${b ?? 0}</span>` : dash);
         return `<tr><td>${mk(p.market)}</td><td>${p.gics}</td><td class="num">${p.cut_pbr === "" ? "–" : Number(p.cut_pbr).toFixed(2)}</td><td class="num">${p.n_univ}</td><td class="num">${p.n_sel}</td><td class="num">${p.n_exempt}</td><td class="num"><b>${p.n_pub}</b></td>
         <td class="num">${rep && r.cut !== "" && r.cut != null ? c(Number(p.cut_pbr).toFixed(2), Number(r.cut).toFixed(2)) : dash}</td><td class="num">${c(p.n_univ, r.n_univ)}</td><td class="num">${c(p.n_sel, r.n_sel)}</td><td class="num">${c(p.n_exempt, r.n_exempt)}</td><td class="num">${c(p.n_pub, r.n_pub)}</td></tr>`; }).join("")}</tbody></table></div></details>`);

  /* ========== 4. 6반기 지속 ========== */
  const selected = selArr.filter((s) => yes(s.selected));
  const near = selArr.filter((s) => !yes(s.selected) && s.flags_1_13 && s.flags_1_13[12] === "1" && Number(s.n_low_last6) >= 4);
  const ruleOf = (s) => (Number(s.n_low_last6) === 6 ? "최근 6 모두" : Number(s.n_low_last6) === 5 && s.flags_1_13?.[6] === "1" ? "6 중 5 + 7번째" : "");
  const listTbl = (arr, extra) => `<div class="tbl-wrap"><table class="list"><thead><tr><th>회사</th><th>업종</th><th>저PBR 이력 1 → 13</th><th class="num">2026.11 PBR</th><th>${extra}</th><th>KIND</th></tr></thead><tbody>${
    arr.map((s) => `<tr class="click" data-code="${s.code}"><td>${mk(s.market)}${esc(s.name)}</td><td>${esc(s.gics)}</td><td>${strip(s.flags_1_13)}</td><td class="num">${f2(s.pbr)}</td>
      <td class="small">${extra === "충족 규칙" ? ruleOf(s) : `최근 6 중 ${s.n_low_last6} · 7번째 ${s.flags_1_13?.[6] === "1" ? "해당" : "아님"}`}</td><td>${kindBy[s.code] ? '<span class="ok">공표</span>' : ""}</td></tr>`).join("") ||
      `<tr><td colspan="6" class="c wait">판정 대기</td></tr>`}</tbody></table></div>`;
  $("#p4").innerHTML = `<h2>단계 4 · 6반기 지속 — 한 번이 아니라 3년 내내 낮았나</h2>` + three(
    `<p>최근 6개 기준일(2024.05~2026.11) <b>모두</b> 저PBR, 또는 6개 중 5개 + 그 직전(7번째, 2023.11) 기준일이 저PBR.</p>
     <p>2026.11 최초 공표 특례: 10.22 PBR 이 기준선을 넘으면 제외 — 띠의 맨 오른쪽 칸이 반드시 주황이어야 한다.</p>`,
    "지침 해설 · 금융위 세부기준(안) 2026.7.28",
    card("재현 선정", R ? pair(R.sel.KOSPI, R.sel.KOSDAQ) : W, "보도 115·70") + card("최근 6 모두", selected.filter((s) => ruleOf(s) === "최근 6 모두").length, "") +
    card("6 중 5 + 7번째", selected.filter((s) => ruleOf(s) === "6 중 5 + 7번째").length, "") + card("아깝게 탈락", near.length, "2026.11 해당 · 최근 6 중 4~5"),
    legend + `<h3>선정 (${selected.length})</h3>${listTbl(selected, "충족 규칙")}<details class="more"><summary>아깝게 탈락 (${near.length}) — 10.22 기준선 이하인데 지속성이 모자란 회사</summary>${listTbl(near, "부족한 칸")}</details>`);

  /* ========== 5. 공표 면제 ========== */
  const sOf = (p) => sel[p.code];
  const bx1 = plans.filter((p) => !p.published && sOf(p) && yes(sOf(p).selected));
  const bx2 = pubPlans;
  const bx3 = plans.filter((p) => !p.published && sOf(p) && !yes(sOf(p).selected));
  const bx0 = plans.filter((p) => !p.published && !sOf(p));
  const li = (p, opt = {}) => `<li class="click" data-code="${p.code}"><span>${mk(p.market)}<a href="#" data-code="${p.code}" class="tr">${esc(p.name)}</a>
    <span class="small">· ${A(p.url, "공시 " + p.disc_dt.slice(0, 10))}</span></span>${opt.strip ? `<span>${strip(flagsOf(p.code), { twelve: true })}</span>` : ""}</li>`;
  $("#p5").innerHTML = `<h2>단계 5 · 공표 면제 — PBR 개선계획을 낸 회사는 빠진다</h2>` + three(
    `<p>기준일(10.22)까지 <b>PBR 개선계획이 담긴 기업가치 제고계획</b>을 공시하면 공표에서 빠진다(연속 2회).</p>
     <p>단 최근 <b>13개 기준일 중 12개 이상</b> 저PBR(장기)이면 공시해도 공표된다.</p>
     <p class="small">KIND 공시 제목에 "(PBR 개선 계획 제출 기업)"이 붙은 회사로 제출사를 정확히 찾았다.</p>`,
    "지침 해설 · KIND 밸류업 공시현황 · 보도자료 PBR 개선계획 제출기업 현황",
    card("PBR 개선계획 제출", plans.length, `보도 62 (34·28)`) + card("공표 제외", bx1.length || (rep ? 0 : "–"), "보도 34 (19·15)") +
    card("면제 불가 = 공표", bx2.length, "보도 15 (10·5)") + card("저PBR 미해당", bx3.length || (rep ? 0 : "–"), "보도 13 (5·8)"),
    `<div class="boxes">
      <div class="bx"><h3>공표 제외 ${bx1.length}</h3><p class="small">저PBR 요건에 해당했지만 계획을 내서 빠진 회사(재현)</p><ul>${bx1.map((p) => li(p, { strip: true })).join("") || `<li class="wait">판정 대기</li>`}</ul></div>
      <div class="bx"><h3>면제 불가 ${bx2.length}</h3><p class="small">계획을 냈지만 장기 저PBR 이라 공표(KIND 확인). 띠 = 13개 기준일, 테두리 = 최근 12</p><ul>${bx2.map((p) => li(p, { strip: true })).join("")}</ul></div>
      <div class="bx"><h3>저PBR 미해당 ${bx3.length}</h3><p class="small">애초에 저PBR 요건에 해당하지 않은 제출사(재현)</p><ul>${bx3.map((p) => li(p, { strip: true })).join("") || `<li class="wait">판정 대기</li>`}</ul></div>
    </div>${bx0.length ? `<p class="small">아직 판정 안 된 제출사 ${bx0.length}사: ${bx0.map((p) => esc(p.name)).join(", ")}</p>` : ""}`);

  /* ========== 6. 공표 ↔ KIND ========== */
  const why = (code) => {
    const s = sel[code], g = grid[code], k = kindBy[code];
    if (exclBy[code]) return `재현 모집단에서 빠짐 — 관리종목(${exclBy[code].reason})`;
    if (!g?.r?.["13"]) return "재현 모집단에 없음(상장 스냅샷 불일치)";
    if (g.r["13"][0] == null) return "PBR 미산정 — 순자산 자료 없음(수집 중일 수 있음)";
    if (!s) return "판정 없음";
    if (yes(s.published)) return k ? "" : (vuBefore(code).length ? "재현은 공표, KIND 에는 없음 — 기준일 전 밸류업 공시 있음(면제 인정 가능성)" : "재현은 공표, KIND 에는 없음 — 기준선·지속성 경계");
    if (yes(s.exempt)) return "재현은 PBR 개선계획 면제로 봄 — 그런데 KIND 는 공표(장기 저PBR 판정 차이)";
    if (s.flags_1_13?.[12] !== "1") return `10.22 PBR ${f2(s.pbr)} 가 재현 기준선 ${f2(s.cut)} 위 (업종 ${s.gics}, ${s.rank}/${s.n_grp}위)`;
    const miss = [...s.flags_1_13].map((c, i) => (i >= 7 && c !== "1" ? D.rounds[i].round : null)).filter(Boolean);
    return `지속성 부족 — 기준선 위였던 회차: ${miss.join(", ") || "7번째"}`;
  };
  const kindOnly = [...kindCodes].filter((c) => rep && !pubCodes.has(c));
  const repOnly = [...pubCodes].filter((c) => !kindCodes.has(c));
  const vuCell = (code) => { const l = vuBefore(code); return l.length ? `${A(l.at(-1).url, l.at(-1).title)} <span class="small">${esc(l.at(-1).dt)}${l.length > 1 ? ` 외 ${l.length - 1}` : ""}</span>` : '<span class="small">기준일까지 없음</span>'; };
  const diffRow = (code, side) => { const g = grid[code] || {}; const k = kindBy[code]; const nm = k?.name || g.n || firms[code]?.name || code;
    return `<tr class="click" data-code="${code}"><td>${mk(k?.market || g.m)}${esc(nm)}</td><td>${side}</td><td class="num">${f2(pbrOf(code))}</td><td class="num">${k?.pbr ?? ""}</td><td>${strip(flagsOf(code))}</td><td class="reason">${esc(why(code))}</td><td>${vuCell(code)}</td></tr>`; };
  $("#p6").innerHTML = `<h2>단계 6 · 공표 ↔ KIND — 최종 명단이 같은가</h2>` + three(
    `<p>재현한 공표 명단을 KIND 밸류업 페이지 저PBR 목록(공표일 2026-11-02)과 회사 단위로 맞춘다.</p>
     <p>다른 회사마다 <b>원인</b>을 단계별로 짚고, <b>기준일까지 낸 밸류업 공시</b>와 링크를 붙인다.</p>`,
    "KIND 밸류업 › 저PBR기업 · KIND 밸류업 › 공시현황",
    card("KIND 공표", "151", "96 · 55") + card("보도자료 명단과", `${(D.kind || []).filter((k) => k.same).length}/151`, "업종·PBR 까지 일치") +
    card("재현과 일치", rep ? matchN : W, "") + card("재현과 다름", rep ? `${kindOnly.length} + ${repOnly.length}` : W, "KIND에만 + 재현에만"),
    `<h3>재현과 다른 회사</h3>${partial ? `<p class="notice">부분 판정이라 "KIND에만"이 많다 — 대부분 "PBR 미산정"이거나 업종 순위가 덜 채워진 탓이다.</p>` : ""}
     <div class="tbl-wrap"><table class="list"><thead><tr><th>회사</th><th>구분</th><th class="num">재현 PBR</th><th class="num">KIND PBR</th><th>이력 1→13</th><th>원인</th><th>기준일까지 밸류업 공시</th></tr></thead><tbody>${
       rep ? (kindOnly.map((c) => diffRow(c, "KIND에만")).join("") + repOnly.map((c) => diffRow(c, "재현에만")).join("") || '<tr><td colspan="7" class="c ok">차이 없음</td></tr>') : `<tr><td colspan="7" class="c wait">판정 대기</td></tr>`}</tbody></table></div>
     <details class="more"><summary>KIND 공표 151사 전체</summary><div class="tbl-wrap"><table class="list"><thead><tr><th>회사(KIND)</th><th>보도자료 표기</th><th>GICS</th><th class="num">KIND PBR</th><th class="num">재현 PBR</th><th class="c">결산월</th><th>표시</th><th>재현</th></tr></thead><tbody>${
       (D.kind || []).map((k) => { const p = pbrOf(k.code); return `<tr class="click" data-code="${k.code}"><td>${mk(k.market)}${esc(k.name)}</td><td>${esc(k.press_name)}</td><td>${esc(k.gics)}</td><td class="num">${k.pbr}</td>
         <td class="num ${p == null ? "" : same(p, k.pbr) ? "ok" : "bad"}">${f2(p)}</td><td class="c">${k.fye}월</td>
         <td>${k.flags.split("|").filter((x) => !["저PBR", "KOSPI200", "KRX300"].includes(x)).map((x) => `<span class="tag warn">${esc(x)}</span>`).join("")}</td>
         <td>${pubCodes.has(k.code) ? '<span class="ok">공표</span>' : rep ? '<span class="bad">아님</span>' : dash}</td></tr>`; }).join("")}</tbody></table></div></details>`);

  /* ========== 회사 추적 ========== */
  const gate = (ic, k, v, cls = "") => `<div class="gate ${cls}"><div class="ic ${ic === "✓" ? "ok" : ic === "✗" ? "no" : "na"}">${ic}</div><div class="k">${k}</div><div>${v}</div></div>`;
  const trace = (code) => {
    const g = grid[code], f = firms[code], k = kindBy[code], s = sel[code], p = planBy[code];
    const name = k?.name || g?.n || f?.name || code, market = k?.market || g?.m || f?.market;
    $("#m-title").innerHTML = `${mk(market)}${esc(name)}`;
    $("#m-sub").textContent = `${code} · 업종 ${k?.gics || g?.g || "–"}${k ? ` · 결산 ${k.fye}월` : ""}`;
    const r13 = g?.r?.["13"], fr = f?.rounds?.at(-1) || {};
    const pbr = pbrOf(code);
    const G = [];
    if (exclBy[code]) G.push(gate("✗", "1 모집단", `빠짐 — 관리종목 ${esc(exclBy[code].date)} · ${esc(exclBy[code].reason)}`));
    else if (r13) G.push(gate("✓", "1 모집단", `포함${keptBy[code] ? ` <span class="tag warn">관리종목(${esc(keptBy[code].reason)}) — 시총·주가 미달은 제외 대상 아님</span>` : ""}`));
    else G.push(gate("–", "1 모집단", "2026.11 재현 모집단에 없음"));
    G.push(gate(pbr != null ? "✓" : "–", "2 PBR", pbr == null ? W :
      `<b>${f2(pbr)}</b> = 시총 ${r13?.[5] != null ? eok1(r13[5]) : eok(fr.mktcap)}억 ÷ 지배지분 등 ${r13?.[6] != null ? eok1(r13[6]) : eok(fr.eq_base)}억
       ${k ? ` · KIND ${k.pbr} ${same(pbr, k.pbr) ? '<span class="ok">일치</span>' : '<span class="bad">불일치</span>'}` : ""}
       ${fr.rcept_no ? `<div class="small">${A(fr.main_url, fr.report_nm)} · ${fr.toc_path ? A(fr.viewer_url, fr.toc_path) : ""}</div>` : ""}`));
    if (r13 && r13[0] != null) G.push(gate(r13[4] ? "✓" : "✗", "3 업종 기준선", `${esc(g.g)} ${r13[2] ?? "–"}사 중 ${r13[1] ?? "–"}위 · 기준선 ${f2(r13[3])} → ${r13[4] ? "이하(저PBR)" : "위"}`));
    else G.push(gate("–", "3 업종 기준선", dash));
    const fl = flagsOf(code);
    G.push(gate(s ? (yes(s.selected) ? "✓" : "✗") : "–", "4 6반기 지속", `${strip(fl)} ${s ? (yes(s.selected) ? ruleOf(s) : `최근 6 중 ${s.n_low_last6}`) : ""}`));
    G.push(gate(p ? (yes(s?.chronic) || p.published ? "✗" : "✓") : "–", "5 공표 면제",
      p ? `PBR 개선계획 공시 ${A(p.url, p.disc_dt)} · ${p.published || yes(s?.chronic) ? "장기 저PBR(13개 중 12개 이상)이라 면제 불가 " + strip(fl, { twelve: true }) : "면제 대상"}` :
        `PBR 개선계획 공시 없음${vuBefore(code).length ? ` · 일반 밸류업 공시 ${vuBefore(code).length}건(면제 요건 아님)` : ""}`));
    const pub = s && yes(s.published);
    G.push(gate(pub ? "✓" : "✗", "6 결과", `재현 <b>${s ? (pub ? "공표" : "공표 안 됨") : "판정 대기"}</b> · KIND <b>${k ? "공표" : "목록에 없음"}</b> ${s ? (pub === !!k ? '<span class="ok">같음</span>' : `<span class="bad">다름</span> <span class="reason">${esc(why(code))}</span>`) : ""}
      ${partial ? `<div class="small wait">부분 판정 — 순자산 ${cov.equity.toLocaleString()}/${cov.universe.toLocaleString()}사만으로 업종 순위를 매겨 기준선이 아직 낮게 나온다. 수집이 끝나면 바뀐다.</div>` : ""}`, "final"));
    let more = "";
    if (f) {
      const rows = f.rounds.slice().reverse().map((r) => { const gr = g?.r?.[String(D.rounds.findIndex((x) => x.round === r.round) + 1)];
        return `<tr><td>${r.round}<div class="small">기준 ${ymd(r.base)}</div></td><td class="num">${r.mktcap ? eok(r.mktcap) : r.listed ? W : '<span class="small">미상장</span>'}</td>
        <td>${r.rcept_no ? `${A(r.main_url, r.report_nm)}<div class="small">접수 ${ymd(r.rcept_dt)}${r.evidence !== r.rcept_no ? ` → 근거 ${A(r.evidence_url, r.evidence)}` : ""}</div>` : dash}</td>
        <td>${r.toc_path ? A(r.viewer_url, r.toc_path) : dash}</td><td class="num">${r.eq_base ? eok(r.eq_base) : r.eq_note ? '<span class="wait">재추출 대기</span>' : dash}</td>
        <td class="num"><b>${f2(gr?.[0] ?? r.pbr_dart)}</b></td><td class="num">${gr ? `${f2(gr[3])} ${gr[4] ? '<span class="tag warn">저PBR</span>' : ""}` : dash}</td></tr>`; }).join("");
      const caps = f.rounds.filter((r) => r.capture).map((r) => `<figure><a href="${esc(r.viewer_url)}" target="_blank" rel="noopener"><img src="${esc(r.capture)}" alt="${esc(name)} ${r.round} 재무상태표"></a><figcaption>${r.round} · ${esc(r.report_nm)}</figcaption></figure>`).join("");
      more = `<details class="more" open><summary>근거 자세히 — 13개 회차</summary><div class="tbl-wrap"><table class="list"><thead><tr><th>회차</th><th class="num">20일 평균 시총(억)</th><th>근거 정기보고서 (DART)</th><th>재무상태표 위치</th><th class="num">지배지분 등(억)</th><th class="num">PBR</th><th class="num">업종 기준선</th></tr></thead><tbody>${rows}</tbody></table></div>
        ${caps ? `<h3>재무상태표 캡처</h3><div class="caps">${caps}</div>` : ""}</details>`;
    } else if (g) {
      more = `<details class="more"><summary>13개 회차 (재현 격자)</summary><table class="list"><thead><tr><th>회차</th><th class="num">시총(억)</th><th class="num">분모(억)</th><th class="num">PBR</th><th class="num">기준선</th></tr></thead><tbody>${
        D.rounds.slice().reverse().map((r) => { const x = g.r[String(r.seq)]; return `<tr><td>${r.round}</td><td class="num">${x ? eok1(x[5]) : dash}</td><td class="num">${x ? eok1(x[6]) : dash}</td><td class="num">${x ? f2(x[0]) : dash}</td><td class="num">${x ? f2(x[3]) : dash}</td></tr>`; }).join("")}</tbody></table>
        <p class="small">DART 원문 위치·캡처는 캡처 범위(하위 약 20%)에 들어간 회사에만 붙는다.</p></details>`;
    }
    $("#m-body").innerHTML = `<div class="gates">${G.join("")}</div>${(vuBefore(code).length ? `<p class="small">기준일까지 밸류업 공시: ${vuBefore(code).map((v) => A(v.url, v.title + " " + v.dt.slice(0, 10))).join(" · ")}</p>` : "")}${more}`;
    $("#modal").classList.add("on");
  };

  /* ---------- 검색 · 클릭 ---------- */
  const index = Object.entries(grid).map(([c, g]) => [c, g.n, g.m]).concat(Object.keys(firms).filter((c) => !grid[c]).map((c) => [c, firms[c].name, firms[c].market]));
  $("#q").oninput = (e) => {
    const q = e.target.value.trim();
    const box = $("#qlist");
    if (!q) { box.style.display = "none"; return; }
    const hit = index.filter(([c, n]) => n.includes(q) || c.includes(q)).slice(0, 20);
    box.innerHTML = hit.map(([c, n, m]) => `<div data-code="${c}">${mk(m)}${esc(n)} <span class="small">${c}${kindBy[c] ? " · KIND 공표" : ""}</span></div>`).join("") || '<div class="wait">없음</div>';
    box.style.display = "block";
  };
  $("#qlist").onclick = (e) => { const d = e.target.closest("[data-code]"); if (d) { trace(d.dataset.code); $("#qlist").style.display = "none"; } };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a.tr");
    if (a) { e.preventDefault(); trace(a.dataset.code); return; }
    const tr = e.target.closest("tr.click, li.click");
    if (tr && !e.target.closest("a") && tr.dataset.code) trace(tr.dataset.code);
    if (!e.target.closest(".right")) $("#qlist").style.display = "none";
  });
  $("#m-close").onclick = () => $("#modal").classList.remove("on");
  $("#modal").onclick = (e) => e.target.id === "modal" && $("#modal").classList.remove("on");
  document.addEventListener("keydown", (e) => e.key === "Escape" && $("#modal").classList.remove("on"));

  let start = "p0";
  try { start = localStorage.getItem("lowpbr-step") || start; } catch (e) { /* */ }
  show(document.getElementById(start) ? start : "p0");
})();
