/* 코스피 정관 · 사업보고서 목록. data.js(window.DATA) 만 읽는다. 없는 표·열은 비워 두고 '수집 중'으로 보인다.
   표: DATA.tables[이름] = {cols, rows(배열)} → 화면에서 레코드로 펼친다.
   정관 txt·정관의변경.txt 미리보기는 fetch('../' + 경로)로 읽고, http 로 열 때만 된다 (file:// 이면 안내 + 링크).
   화면에 쓰는 영어 표기: 정관 = Articles of Incorporation (코드 식별자는 charter 그대로). */
(() => {
  "use strict";
  const D = window.DATA;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const IS_FILE = location.protocol === "file:";
  const NA = '<span class="na">–</span>';
  const AOI = "Articles of Incorporation";

  if (!D || typeof D !== "object") {
    $("#tabs").hidden = true;
    $("#panes").innerHTML = `<div class="notice warn"><b>site/data.js 가 없습니다.</b> 케이스 폴더에서
      <code>python -X utf8 scripts/s08_site.py</code> 를 실행하면 <code>data/final/*.json</code> 으로 만듭니다.
      수집이 끝나지 않았으면 결과 파일이 아직 없을 수 있습니다.</div>`;
    return;
  }

  /* ---------- 값 다루기 ---------- */
  const arr = (v) => (Array.isArray(v) ? v : v == null || v === "" ? [] : String(v).split(";").map((s) => s.trim()));
  const list = (v) => arr(v).filter((x) => x != null && x !== "");
  const yes = (v) => v === true || v === 1 || v === "True" || v === "true";
  const ymd = (s) => { const t = String(s ?? ""); return /^\d{8}$/.test(t) ? `${t.slice(0, 4)}.${t.slice(4, 6)}.${t.slice(6, 8)}` : t; };
  const num = (v) => (v == null || v === "" || Number.isNaN(Number(v)) ? NA : Number(v).toLocaleString("ko-KR"));
  const fmtN = (v) => Number(v || 0).toLocaleString("ko-KR");
  const e = (v) => (v == null || v === "" ? "" : esc(v));
  const href = (p) => "../" + String(p).replace(/\\/g, "/").replace(/^(\.\/|\/)+/, "").split("/").map(encodeURIComponent).join("/");
  const ext = (url, html, title) => (url ? `<a class="ext" href="${esc(url)}" target="_blank" rel="noopener"${title ? ` title="${esc(title)}"` : ""}>${html}</a>` : NA);
  const loc = (path, html) => (path ? `<a class="loc" href="${esc(href(path))}" target="_blank" rel="noopener" title="${esc(path)}">${html}</a>` : NA);
  // GitHub Pages 에는 img/·소집공고 XML 이 없고(git 제외) 폴더 목록도 안 나온다 → 그 링크는 Pages 에서 숨긴다
  const IS_PAGES = /\.github\.io$/i.test(location.hostname);
  const dartUrl = (rno) => (rno ? `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${encodeURIComponent(rno)}` : "");
  const tagOf = (s) => ((String(s ?? "").match(/^\s*((?:\[[^\]]*\]\s*)+)/) || [])[1] || "").trim();
  const stripTag = (s) => String(s ?? "").replace(/^\s*(\[[^\]]*\]\s*)+/, "");
  const dateOfRno = (rno) => (/^\d{8}/.test(String(rno ?? "")) ? String(rno).slice(0, 8) : "");

  const MKT = ["코스피", "코스닥", "코넥스", "기타"];
  const MKT_CLS = { 코스피: "kospi", 코스닥: "kosdaq", 코넥스: "konex", 기타: "etc" };
  const CLS = { Y: "유가", K: "코스닥", N: "코넥스", E: "기타" };
  const CT = { text: "텍스트", image: "이미지", mixed: "혼합", pdf: "PDF", empty: "빈 문서" };
  const ST = { ok: "정관 있음", no_charter_attachment: "첨부에 정관 없음", main_page_missing: "공시 화면 없음",
    download_failed: "내려받기 실패", not_processed: "미처리" };
  const NEW_ST = { family_first: "DART 본문 목록(family) 첫 본문", fallback_no_family: "본문 목록 없음, rcept_no 그대로",
    fallback_not_fetched: "공시 화면 미수집, rcept_no 그대로" };
  const DETECT = { code: "서식 코드", title: "제목" };
  const NO_TEXT = '<span class="st bad" title="PDF 정관을 받지 못했다(DART 미서비스 또는 DRM). 받은 파일·DART 주소에는 안내 문구만 있다">원문 없음</span>';
  const mk = (m) => (m ? `<span class="mk ${MKT_CLS[m] || "etc"}">${esc(m)}</span>` : NA);
  const ctB = (c) => (c ? `<span class="ct ${esc(c)}">${esc(CT[c] || c)}</span>` : NA);
  const tagB = (t) => (t ? `<span class="tag">${esc(String(t).replace(/[[\]]/g, ""))}</span>` : "");
  const stB = (s) => (s ? `<span class="st${s === "ok" ? "" : " bad"}">${esc(ST[s] || s)}</span>` : NA);
  const newSt = (s) => {
    if (!s) return "";
    const after = /_after_amend$/.test(s), base = s.replace(/_after_amend$/, "");
    return `${esc(NEW_ST[base] || base)}${after ? " · 정정 뒤 본문" : ""} <span class="small">(${esc(s)})</span>`;
  };

  /* ---------- 표 ---------- */
  const T = {};
  // dividend.js(window.DATA_DIV, s10_dividend_site.py) 의 배당기준일 표도 같은 방식으로 읽는다
  for (const [name, t] of Object.entries({ ...(D.tables || {}), ...((window.DATA_DIV || {}).tables || {}) })) {
    if (!t || !Array.isArray(t.cols) || !Array.isArray(t.rows)) continue;
    const cols = t.cols;
    T[name] = { cols, file: t.file, updated: t.updated,
      rows: t.rows.map((r) => { const o = {}; for (let i = 0; i < cols.length; i++) o[cols[i]] = r[i]; return o; }) };
  }
  const rowsOf = (n) => (T[n] ? T[n].rows : []);
  // 정관 태그 화면 표기 (사용자 지시 2026-11-17): 정관no → N · 정관yes → Y · 정관yesorno → YorN. 데이터 값은 그대로 두고 화면·CSV 만 바꾼다.
  // 판단 이유 같은 글 속 낱말은 '정관 N' 처럼 (어느 칸의 값인지 보이게)
  const TAG_YN = { 정관no: "N", 정관yes: "Y", 정관yesorno: "YorN" };
  const TL = (t) => TAG_YN[t] || t || "";
  const tagWords = (x) => (typeof x === "string" ? x.replace(/정관(yesorno|yes|no)/g, (w) => `정관 ${TAG_YN[w]}`) : x);
  for (const [name, keys] of [["dividend", ["note", "attached_note", "reviewed_why", "agm_note", "basis_note"]], ["dividend_notes", ["text", "kind"]], ["dividend_changes", ["text"]]])
    for (const r of rowsOf(name)) for (const k of keys) r[k] = tagWords(r[k]);
  const has = (n, col) => !!T[n] && T[n].cols.includes(col);
  const M = D.manifest || {};
  /* 정관을 모은 시장, 시장마다 정관·소집공고·정관 문서·빠진 회사 표와 manifest (코스닥 = kosdaq_* 표 · data.js 의 manifest_kosdaq).
     표 이름은 data/final 파일 이름 그대로이고, 화면에서 사업보고서 표에 rcept_no 로 붙인다. 표가 없는 시장은 빠진다. */
  const MARKETS = [
    { m: "코스피", charter: "kospi_charter", agm: "agm_notices", docs: "charter_docs", absent: "kospi_absent", man: M, kind: "kind_kospi",
      xlsx: "kospi_charter.xlsx", step: "s02b_kospi_absent.py", kindName: "유가증권시장" },
    { m: "코스닥", charter: "kosdaq_charter", agm: "kosdaq_agm_notices", docs: "kosdaq_charter_docs", absent: "kosdaq_absent", man: D.manifest_kosdaq || {}, kind: "kind_kosdaq",
      xlsx: "kosdaq_charter.xlsx", step: "s02c_kosdaq_absent.py", kindName: "코스닥시장" },
  ].filter((x) => T[x.charter]);
  const CM = MARKETS.length ? MARKETS.map((x) => x.m) : ["코스피"];      // 정관을 모은 시장 이름
  const CMS = CM.join("·");
  const KC = MARKETS.flatMap((x) => rowsOf(x.charter)), AR = rowsOf("annual_reports"), AG = MARKETS.flatMap((x) => rowsOf(x.agm));
  const kcBy = new Map(KC.map((r) => [r.rcept_no, r]));
  const arBy = new Map(AR.map((r) => [r.rcept_no, r]));
  const agBy = new Map(AG.map((r) => [r.rcept_no, r]));
  const CNT = M.counts || {};
  const WIN = Array.isArray(M.window) ? M.window : [];

  // 한계 문구의 수집시점: manifest.fetched.dart_main = [처음, 마지막] (ISO 시각), 시장마다
  {
    const f = (s) => String(s).replace("T", " ").slice(0, 16);
    const one = (span) => { const [a, b] = span.map(f); return a.slice(0, 10) === b.slice(0, 10) ? `${a} ~ ${b.slice(11)}` : `${a} ~ ${b}`; };
    const spans = (MARKETS.length ? MARKETS : [{ m: "코스피", man: M }]).map((x) => [x.m, (x.man.fetched || {}).dart_main])
      .filter(([, sp]) => Array.isArray(sp) && sp.length === 2);
    const el = document.getElementById("fetched-dart");
    if (el && spans.length) el.textContent = spans.map(([m, sp]) => (spans.length > 1 ? `${m} ${one(sp)}` : one(sp))).join(" · ");
  }
  // 머리말·푸터의 '정관을 모은 시장' 이름 (index.html 의 data-cm)
  $$("[data-cm]").forEach((el) => { el.textContent = CMS; });
  document.title = `${CMS} 정관 목록`;

  const agmN = (r) => r.agm_count ?? list(r.agm_rcept_nos).length;
  const amN = (r) => r.agm_charter_amend_count ?? list(r.agm_charter_amend_rcept_nos).length;
  const newDiff = (r) => !!r.rcept_no_new && r.rcept_no_new !== r.rcept_no;
  const charterBase = (r) => r.charter_dir || String(r.charter_img_dir || "").replace(/\/img\/?$/, "") || String(r.charter_txt || "").replace(/\/[^/]*$/, "");
  const xmlPath = (n) => (!n.main_xml ? "" : String(n.main_xml).includes("/") || !n.folder ? n.main_xml : `${n.folder}/${n.main_xml}`);
  const coll = new Intl.Collator("ko", { numeric: true });
  // 종목코드는 글자 순서 그대로 (= 표준코드 순). 숫자 인식 정렬은 '0030R0' 을 30 으로 읽어 000020 과 000040 사이에 넣는다
  const cmpRaw = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  /* 정관 본문 파일 하나: 스캔 쪽은 Opus OCR, PDF 는 글자층(스캔 쪽은 Opus), 그 밖은 charter.txt.
     Windows OCR 결과(charter_ocr.txt)는 데이터 폴더에만 두고 화면에는 걸지 않는다 (사용자 결정 2026-11-16). */
  const noText = (r) => "charter_fulltext_txt" in r && !r.charter_fulltext_txt && r.charter_status === "ok";
  const bestTxt = (r) => {
    if (noText(r)) return null;
    const ft = r.charter_fulltext_txt && !/charter_ocr\.txt$/.test(r.charter_fulltext_txt) ? r.charter_fulltext_txt
      : r.charter_llm_txt || r.charter_pdf_txt || r.charter_txt;
    if (!ft) return null;
    const pdf = r.charter_content_type === "pdf";
    if (ft === r.charter_llm_txt) return { p: ft, n: r.charter_llm_chars, l: pdf ? "PDF글" : "Opus", f: "charter_llm.txt",
      why: pdf ? "PDF 글자층 · 글자층이 없는 쪽은 Claude Opus 5.5 로 OCR 한 글" : "Claude Opus 5.5 로 스캔 이미지를 OCR 한 글" };
    if (ft === r.charter_pdf_txt) return { p: ft, n: r.charter_pdf_chars, l: "PDF글", f: "charter_pdf.txt", why: "PDF 글자층" };
    return { p: ft, n: r.charter_text_chars, l: "txt", f: "charter.txt", why: "DART 정관 원문 화면의 글" };
  };

  /* ---------- 사업보고서 + 정관 + 소집공고 = 표 하나 ----------
     annual_reports 1행(사업보고서 최종본)에 kospi_charter 행을 rcept_no 로 붙인다. 소집공고·정관 문서 표는 상세 창과 결과 파일로 본다.
     _chr = 정관 원문 (종류 또는 상태, 정관을 모으지 않은 행은 빈 값) · _agm = 소집공고 (amend · plain · none, 모으지 않은 행은 빈 값) */
  const CD = MARKETS.flatMap((x) => rowsOf(x.docs));
  const cdBy = new Map(CD.map((d) => [`${d.rcpNo}|${d.dcmNo}`, d]));
  const CHR_ORDER = ["text", "image", "pdf", "mixed", "empty", ...Object.keys(ST).filter((k) => k !== "ok")];
  const AGM_L = { amend: "정관변경 안건 있음", plain: "공고만 (정관변경 안건 없음)", none: "기간 안 공고 없음" };
  // 사업보고서가 없는 상장회사의 정관 (absent_charter, e6 s08): 근거문서 = 증권신고서 · 분할계획서 · 기타신고사항 · 홈페이지
  const AC = rowsOf("absent_charter");
  const SRC_REP = "사업보고서";
  const SRC_ORDER = [SRC_REP, "증권신고서", "분할계획서", "기타신고사항", "홈페이지"];
  const chrOf = (k) => (!k ? "" : k.charter_status === "ok" ? k.charter_content_type || "empty" : k.charter_status || "not_processed");
  const agmOf = (k) => (!k || !("agm_count" in k || "agm_rcept_nos" in k) ? "" : amN(k) > 0 ? "amend" : agmN(k) > 0 ? "plain" : "none");
  {
    const base = AR.length ? AR : KC;
    const src = T.annual_reports || T[(MARKETS[0] || {}).charter];
    if (src) {
      const rows = base.map((a) => {
        const k = kcBy.get(a.rcept_no);
        const r = k ? { ...a, ...k } : { ...a };
        r._src = SRC_REP;
        r._chr = chrOf(k);
        r._agm = agmOf(k);
        return r;
      }).concat(AC.map((a) => ({ ...a, _abs: true, _src: a.charter_source_doc || "그 밖", _chr: chrOf(a), _agm: agmOf(a) })))
        .sort((x, y) => cmpRaw(String(x.stock_code || "~"), String(y.stock_code || "~")) || coll.compare(String(x.rcept_no || x.charter_source_rcept_no || ""), String(y.rcept_no || y.charter_source_rcept_no || "")));
      T.reports = { cols: [...new Set([...src.cols, ...MARKETS.flatMap((x) => T[x.charter].cols), ...(T.absent_charter ? T.absent_charter.cols : []), "_src", "_chr", "_agm"])], rows,
        file: T.annual_reports ? ["annual_reports", ...MARKETS.map((x) => x.charter), ...(AC.length ? ["absent_charter"] : [])].join(" + ") : src.file, updated: src.updated };
    }
  }
  const srcB = (v) => (v ? `<span class="srcd${v === SRC_REP ? "" : " alt"}">${esc(v)}</span>` : NA);

  /* ---------- 머리말 ---------- */
  $("#hinfo").innerHTML = [
    M.as_of ? `<span class="asof">기준일 <b>${esc(M.as_of)}</b></span>` : "",
    `<span>페이지 데이터 ${esc(D.built || "")}</span>`,
  ].join("");
  $("#hbar").innerHTML = [
    // 사업보고서와 주주총회 소집공고의 조회기간이 다르다 (사용자 지시 2026-11-20 — 한 줄이면 소집공고도 1년치로 오해)
    WIN.length === 2 ? `사업보고서 조회기간 <b>${esc(WIN[0])} ~ ${esc(WIN[1])}</b>` : "",
    Array.isArray((window.DATA_DIV || {}).agm_window) ? `주주총회 소집공고 조회기간 <b>${esc(window.DATA_DIV.agm_window[0])} ~ ${esc(window.DATA_DIV.agm_window[1])}</b>` : "",
    M.as_of ? `소속시장 = KIND ${esc(M.as_of)} 현재` : "",
    M.generated_at ? `결과 파일 생성 ${esc(String(M.generated_at).replace("T", " ").slice(0, 16))}` : "",
    `data.js 생성 ${esc(D.built || "")}`,
  ].filter(Boolean).map((s) => `<span>${s}</span>`).join("");

  const notes = [];
  if (M.fixture) notes.push(`<div class="notice warn"><b>테스트용 fixture 데이터</b>: ${esc(M.note || "실제 값이 아닙니다")}</div>`);
  const miss = Array.isArray(D.missing) ? D.missing : [];
  if (miss.length) {
    notes.push(`<div class="notice">아직 없는 결과 파일: ${miss.map((f) => `<code>data/final/${esc(f)}</code>`).join(" ")}
      · 수집이 끝난 뒤 <code>python -X utf8 scripts/s08_site.py</code> 를 다시 실행하면 채워집니다.</div>`);
  }
  $("#notices").innerHTML = notes.join("");

  /* ---------- 조회조건 정의 ---------- */
  const norm = (s) => String(s ?? "").replace(/\s+/g, "").toLowerCase();
  const Q = (ph = "회사명·종목코드·고유번호·접수번호") => ({ id: "q", type: "text", label: "회사명/종목코드", ph,
    test: (r, v) => { const s = norm(v); return [r.corp_name, r.stock_code, r.corp_code, r.rcept_no, r.rcept_no_new, r.rcpNo].some((x) => x != null && norm(x).includes(s)); } });
  const SEL = (id, label, key, o = {}) => ({ id, type: "select", label, key, ...o });
  const CHK = (id, label, text, test, need, title) => ({ id, type: "check", label, text, test, need, title });
  const F_MONTH = SEL("settle_month", "결산월", "settle_month", { fmt: (v) => `${v}월`, numeric: true });
  const F_YEAR = SEL("fiscal_year", "사업연도", "fiscal_year", { numeric: true, desc: true });
  const F_AMEND = SEL("amend_tag", "정정구분", "amend_tag", { empty: "정정 없음" });
  const F_NEW = CHK("new_diff", "접수번호", "rcept_no ≠ rcept_no_new", newDiff, ["rcept_no_new"], "[첨부정정] 행 중 본문 접수번호가 다른 것");
  // 근거 필터, extra 는 값 하나가 아니라 묶음으로 고르는 선택지 (test 로 거른다)
  const NOT_COLLECTED = `모으지 않음 (${CMS} 아님)`;
  const F_CHR = SEL("chr", "근거 · 정관", "_chr", { fmt: (v) => CT[v] || ST[v] || v, empty: NOT_COLLECTED, order: CHR_ORDER,
    extra: [{ v: "@any", label: "정관 원문 있음 (종류 전체)", test: (r) => r.charter_status === "ok" }] });
  const F_AGM = SEL("agm", "근거 · 소집공고", "_agm", { fmt: (v) => AGM_L[v] || v, empty: NOT_COLLECTED, order: Object.keys(AGM_L),
    extra: [{ v: "@any", label: "기간 안 공고 있음 (전체)", test: (r) => !!r._agm && agmN(r) > 0 }] });

  /* ---------- 열 정의 ---------- */
  const C_NO = { t: "No", c: "c no", no: true, need: [] };
  const C_CODE = { k: "stock_code", t: "종목코드", c: "c mono", raw: true };
  const C_NAME = { k: "corp_name", t: "회사명", c: "nm stick" };
  const C_RNM = { k: "report_nm", t: "보고서명", h: (r) => `${esc(stripTag(r.report_nm))}${tagB(r.amend_tag ?? tagOf(r.report_nm))}` };
  const C_DT = (k, t) => ({ k, t, c: "c mono", h: (r) => (r[k] ? ymd(r[k]) : NA) });
  /* 접수번호 칸 = DART 공시 링크 (dart_url, 없으면 rcpNo 로 만든 주소) */
  const C_RNO = (diff) => ({ k: "rcept_no", t: "접수번호", c: "c mono", title: "접수번호를 누르면 DART 공시 화면 (dart_url)",
    h: (r) => (r.rcept_no ? ext(r.dart_url || dartUrl(r.rcept_no), esc(r.rcept_no), "DART 공시") : NA) +
      (diff && newDiff(r) ? `<span class="diff" title="rcept_no_new (본문) ${esc(r.rcept_no_new)}">≠new</span>` : "") });

  const agmChips = (r) => {
    const ids = list(r.agm_rcept_nos), kinds = arr(r.agm_kinds), am = new Set(list(r.agm_charter_amend_rcept_nos));
    const n = agmN(r);
    if (!ids.length) return n ? `<span class="cnt">${fmtN(n)}</span>` : '<span class="zero">0</span>';
    return `<span class="cnt">${fmtN(n)}</span>` + ids.map((id, i) => {
      const x = agBy.get(id) || {};
      const kind = x.agm_kind || kinds[i] || "공고";
      const tip = `${ymd(x.rcept_dt || dateOfRno(id))} ${id}${am.has(id) ? " · 정관변경 안건" : ""} · DART 공시`;
      return `<a class="chip${am.has(id) ? " am" : ""}" href="${esc(x.dart_url || dartUrl(id))}" target="_blank" rel="noopener" title="${esc(tip)}">${esc(kind)}</a>`;
    }).join("");
  };
  const amTxtChips = (r) => {
    const t = arr(r.agm_charter_amend_txt), ids = arr(r.agm_charter_amend_rcept_nos);
    const items = t.map((p, i) => [p, ids[i]]).filter(([p]) => p);
    if (!items.length) return NA;
    return items.map(([p, id], i) => {
      const x = agBy.get(id) || {};
      return `<a class="chip loc" href="${esc(href(p))}" target="_blank" rel="noopener" title="${esc(`${ymd(x.rcept_dt || dateOfRno(id))} ${id || ""}\n${p}`)}">txt${items.length > 1 ? i + 1 : ""}</a>`;
    }).join("");
  };

  /* ---------- KIND 상장회사인데 목록에 없는 회사 (kospi_absent · kosdaq_absent · manifest 의 kind_kospi · kind_kosdaq) ---------- */
  const RS = { new_listing: "신규상장", no_annual_report: "사업보고서 이력 없음", no_report_in_window: "기간 안 사업보고서 없음",
    report_in_window: "수집 누락 의심", no_corp_code: "고유번호 없음" };
  const GRP_ORDER = ["주권", "부동산투자회사", "투자회사", "기업인수목적회사", "외국주권", "주식예탁증권"];
  const ABS = MARKETS.map((x) => ({ ...x, kk: x.man[x.kind], rows: rowsOf(x.absent).map((r) => ({ ...r, _m: x.m })) })).filter((x) => x.kk && x.kk.detail);
  const kindUrl = (n) => `https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=${encodeURIComponent(n)}`;
  const acBy = new Map(AC.map((r) => [`${r.market}|${r.stock_code}`, r]));
  const absentBox = () => {
    if (!ABS.length) return "";
    const acOf = (r) => acBy.get(`${r._m}|${r.stock_code}`);
    const KA = ABS.flatMap((x) => x.rows);
    const many = ABS.length > 1;
    // 빠진 회사 이름: 적으면 다, 많으면 이유별 수 (3사 이하인 이유만 이름)
    const who = (rows) => {
      if (rows.length <= 6) return rows.map((r) => `<b>${esc(r.corp_name)}</b>(${esc(r.reason_code === "new_listing" ? "신규상장" : r.sec_group || RS[r.reason_code] || "")})`).join(" · ");
      const by = new Map();
      for (const r of rows) { if (!by.has(r.reason_code)) by.set(r.reason_code, []); by.get(r.reason_code).push(r); }
      return [...by].map(([k, rs]) => `${esc(RS[k] || k)} ${fmtN(rs.length)}사${rs.length <= 3 ? `(${rs.map((r) => `<b>${esc(r.corp_name)}</b>`).join(" · ")})` : ""}`).join(" · ");
    };
    const para = (x) => {
      const d = x.kk.detail;
      const inv = x.rows.some((r) => r.reason_code === "no_annual_report" && r.kind_misc_n);
      const found = x.rows.filter(acOf), miss = x.rows.filter((r) => !acOf(r));
      const docs = Object.entries(found.reduce((o, r) => { const k = acOf(r).charter_source_doc || "그 밖"; o[k] = (o[k] || 0) + 1; return o; }, {})).map(([k, n]) => `${k} ${fmtN(n)}`).join(" · ");
      if (!found.length) {
        return `<p><b>KIND ${esc(d.date)} 현재 ${esc(x.m)} 상장회사 ${fmtN(d.companies)}사 중 ${fmtN(d.in_list)}사가 이 표에 있습니다</b> (시장 = ${esc(x.m)} 행).
          ${d.absent ? `나머지 ${fmtN(d.absent)}사는 조회기간(${esc(WIN.join(" ~ "))})에 사업보고서를 내지 않아 이 목록에 들어올 수 없습니다: ${who(x.rows)}.` : ""}
          ${inv ? " 투자회사는 DART 사업보고서 대신 KIND '기타신고사항'으로 분기·결산 보고(영업보고서·자산운용보고서 게시, 감사보고서 제출 등)를 낸다." : ""}</p>`;
      }
      return `<p><b>KIND ${esc(d.date)} 현재 ${esc(x.m)} 상장회사 ${fmtN(d.companies)}사 중 ${fmtN(d.in_list)}사는 사업보고서로, ${fmtN(found.length)}사는 다른 근거문서(${esc(docs)})로 이 표에 있습니다</b> (시장 = ${esc(x.m)} 행).
        사업보고서가 없는 ${fmtN(d.absent)}사는 조회기간(${esc(WIN.join(" ~ "))})에 사업보고서를 내지 않았다: ${who(x.rows)}.
        ${miss.length ? `그중 정관을 찾지 못한 ${fmtN(miss.length)}사(${miss.map((r) => `<b>${esc(r.corp_name)}</b>`).join(" · ")})는 이 표에 없다.` : ""}
        ${inv ? " 투자회사는 DART 사업보고서 대신 KIND '기타신고사항'으로 분기·결산 보고(영업보고서·자산운용보고서 게시, 감사보고서 제출 등)를 낸다." : ""}</p>`;
    };
    const cnt = (x) => {
      const d = x.kk.detail, s = x.kk.summary;
      const grp = GRP_ORDER.filter((g) => d.groups && d.groups[g]).concat(Object.keys(d.groups || {}).filter((g) => !GRP_ORDER.includes(g)))
        .map((g) => `${g} ${fmtN(d.groups[g])}`).join(" · ");
      const dr = s && (s.groups["주식예탁증권(DR)"] || {}).companies;
      return `${many ? `${esc(x.m)}: ` : ""}상장회사 수는 회사 기준이다 (${esc(grp)}).${s ? ` KIND 상장현황 요약(${esc(s.date)})으로는 ${x.kindName} 회사가 ${fmtN(s.companies_with_dr)}사(소계 ${fmtN((s.groups["소계"] || {}).companies)}${dr ? ` + 주식예탁증권 ${fmtN(dr)}` : ""})이고, 종목으로 세면 우선주 등을 더해 ${fmtN(s.issues_with_dr)}개다.` : ""}${
        s && s.companies_with_dr !== d.companies ? gap(x, d, s) : ""}`;
    };
    // 요약일과 상세 목록 날짜 사이의 회사 수 차이, 그 사이 상장일인 빠진 회사로 다 설명되면 이름을 적는다
    const gap = (x, d, s) => {
      const diff = d.companies - s.companies_with_dr;
      const nl = x.rows.filter((r) => r.listed_date && String(r.listed_date) > String(s.date) && String(r.listed_date) <= String(d.date));
      return diff > 0 && nl.length === diff
        ? ` 상세 목록(${esc(d.date)})과 ${fmtN(diff)}사 다른 것은 요약일 뒤에 신규상장한 ${nl.map((r) => `<b>${esc(r.corp_name)}</b>(${esc(r.listed_date)})`).join(" · ")} 때문이다.`
        : ` 요약(${esc(s.date)})과 상세 목록(${esc(d.date)})의 날짜가 달라 ${fmtN(Math.abs(diff))}사 차이가 난다.`;
    };
    const forms = (r) => {
      const o = r.filing_forms_window && typeof r.filing_forms_window === "object" ? Object.entries(r.filing_forms_window) : [];
      const all = o.map(([k, v]) => `${k} ${v}건`).join("\n");
      const last = r.last_filing_rcept_no ? `<br><span class="small">마지막</span> ${ext(r.dart_url || dartUrl(r.last_filing_rcept_no), `${ymd(r.last_filing_dt)} ${esc(r.last_filing_nm || "")}`, "DART 공시")}` : "";
      return `<span class="tip" title="${esc(all)}">${fmtN(r.n_filings_window)}건</span>${last}`;
    };
    const misc = KA.filter((r) => Array.isArray(r.kind_misc_items) && r.kind_misc_items.length).map((r) => `<details class="misc">
        <summary>${esc(r.corp_name)} · KIND 기타신고사항 ${fmtN(r.kind_misc_items.length)}건 제목</summary>
        <ul>${r.kind_misc_items.map(([dt, n, t]) => `<li><span class="mono">${esc(dt)}</span> ${ext(kindUrl(n), esc(t || "(제목 없음)"), "KIND 공시 원문")}</li>`).join("")}</ul></details>`).join("");
    const body = KA.map((r) => `<tr>${many ? `<td class="c">${mk(r._m)}</td>` : ""}
        <td class="c mono">${e(r.stock_code)}</td><td class="nm">${e(r.corp_name)}</td><td class="c">${e(r.sec_group)}</td>
        <td class="c mono">${e(r.listed_date)}</td>
        <td class="c" title="DART 사업보고서 전체 이력(1999년~) · 조회기간 안">${fmtN(r.n_annual_reports_all)}건 · ${fmtN(r.n_annual_reports_window)}건</td>
        <td class="rs mid">${forms(r)}</td>
        <td class="c" title="${esc(Object.entries(r.kind_misc_groups || {}).map(([k, v]) => `${k} ${v}건`).join(" · "))}">${r.kind_n_disclosures_window != null ? `${fmtN(r.kind_n_disclosures_window)}건${r.kind_misc_n ? ` <span class="small">· 기타신고사항 ${fmtN(r.kind_misc_n)}</span>` : ""}` : NA}</td>
        <td class="rs"><span class="st${r.reason_code === "report_in_window" ? " bad" : ""}">${esc(RS[r.reason_code] || r.reason_code || "")}</span> ${e(r.reason)}</td>
        ${AC.length ? `<td class="c">${acOf(r) ? `${srcB(acOf(r).charter_source_doc)}<br>${ext(acOf(r).charter_source_url, `${esc(ymd(String(acOf(r).charter_source_dt || "").replace(/-/g, "")))} ${esc(acOf(r).charter_source_nm || "")}`, "정관을 찾은 근거문서")}` : '<span class="st bad">못 찾음</span>'}</td>` : ""}</tr>`).join("");
    const nAbs = ABS.reduce((a, x) => a + (x.kk.detail.absent || 0), 0);
    return `<div class="notice absent">
      ${ABS.map(para).join("")}
      ${nAbs ? `<details><summary>${AC.length ? `사업보고서가 없는 ${fmtN(nAbs)}사와 근거 보기` : `빠진 ${fmtN(nAbs)}사와 근거 보기`}</summary>
        <div class="grid static"><table><thead><tr>${many ? "<th>시장</th>" : ""}<th>종목코드</th><th>회사명</th><th>증권구분</th><th>상장일</th>
          <th title="DART 사업보고서 전체 이력(1999년~) · 조회기간 안">사업보고서 전체 · 기간</th><th title="조회기간 안 DART 최종본 공시, 서식별 건수는 건수에 마우스를 올리면 보인다">기간 안 DART 공시</th><th title="조회기간 안 KIND 공시(최종본) · 그중 기타신고사항">기간 안 KIND 공시</th><th>사업보고서가 없는 이유</th>${AC.length ? '<th title="정관을 찾은 문서 (이 표의 근거문서 칸)">정관 근거문서</th>' : ""}</tr></thead>
          <tbody>${body}</tbody></table></div>
        ${misc}
        <p class="small">근거: OpenDART <code>list.json</code> 에 회사 고유번호를 넣어 ① 사업보고서(A001) 전체 이력(1999-01-01 ~ 기준일), ② 조회기간의 모든 공시(최종본)를 조회했고, 결산월은 <code>company.json</code> 으로 확인했다.
          KIND 는 ③ 공시 상세검색(회사·조회기간·최종본), ④ 제목이 '기타신고사항'인 공시는 본문의 '제목' 칸을 읽어 영업보고서·자산운용보고서·결산·감사·정관 변경·투자설명서 갱신·그 밖으로 묶었다.
          사업보고서 기한은 사업연도 경과 후 90일(자본시장법 제159조). 표: ${ABS.map((x) => loc(`data/final/${x.absent}.csv`, `${x.absent}.csv`)).join(" · ")} · 만드는 단계 ${ABS.map((x) => `<code>scripts/${x.step}</code>`).join(" · ")}</p>
      </details>` : ""}
      ${ABS.map((x) => `<p class="small">${cnt(x)}</p>`).join("")}
    </div>`;
  };

  // 합친 표 위에 원래 표(결과 파일)로 가는 줄, 소집공고·정관 문서 단위로 보려면 이 파일을 연다
  const filesLine = () => {
    const f = (n, l) => (T[n] ? `${l} ${fmtN(T[n].rows.length)}건 ${loc(`data/final/${n}.csv`, `${n}.csv`)}` : "");
    const parts = [[f("annual_reports", "사업보고서"), f("absent_charter", "사업보고서 없는 회사 정관")].filter(Boolean).join(" · "), ...MARKETS.map((x) => [f(x.charter, `${x.m} 정관`), f(x.agm, `${x.m} 소집공고`), f(x.docs, `${x.m} 정관 문서`),
      loc(`data/final/${x.xlsx}`, x.xlsx)].filter(Boolean).join(" · "))].filter(Boolean);
    if (!parts.length) return "";
    return `<p class="small files">결과 파일: ${parts.join("<br>")} <span class="na">· 아래 '다운로드(CSV)' 는 조회된 합친 행</span></p>`;
  };

  /* ---------- 배당기준일 (s09 태그 → s10 → dividend.js) ---------- */
  const DV = window.DATA_DIV || {};
  const DVS = DV.stats || {};
  const DVL = DV.links || {};
  const DORD = ["정관no", "정관yesorno", "정관yes", "확인필요"];
  const DTAG = { 정관no: "no", 정관yes: "yes", 정관yesorno: "yesorno", 확인필요: "chk" };
  const DTAG_TIP = { 정관no: "이사회로 정하는 때: 정관이 결산배당 기준일을 날짜로 고정하지 않는다",
    정관yes: "정관상 결산일: 결산기말(또는 정관이 박아 둔 날) 현재 주주", 정관yesorno: "정관상 결산일 원칙, 단 이사회로 정하는 때에도 할 수 있다",
    확인필요: "원문 없음·결손" };
  const dtag = (t) => (t ? `<span class="dtag ${DTAG[t] || "chk"}" title="${esc(TAG_YN[t] ? `${TL(t)}: ${DTAG_TIP[t]}` : DTAG_TIP[t] || "")}"><i></i>${esc(TL(t))}</span>` : NA);
  const DORD_OPT = { 정관no: "N (이사회가 정함)", 정관yesorno: "YorN (결산일, 이사회도 가능)", 정관yes: "Y (결산일 고정)" };
  // 상장공시시스템 신고 (s02e 엑셀 → s10 filed*, 코스피 · 코스닥): 정관 태그와 같은 색. 정관과 불일치면 칸 바탕 빨강, 미입력은 회색
  const FORD = ["Y", "N", "YorN", "미입력"];
  const FTAG = { N: "no", Y: "yes", YorN: "yesorno", 미입력: "chk" };
  const FTIP = { N: "신고 N: 이사회 결의로 정한 날", Y: "신고 Y: 특정일", YorN: "신고 YorN: 특정일 또는 이사회 결의로 정한 날", 미입력: "상장공시시스템에 배당기준일 신고가 없다" };
  const ftag = (v) => (v ? `<span class="dtag ${FTAG[v] || "chk"}" title="${esc(FTIP[v] || "")}"><i></i>${esc(v)}</span>` : NA);
  const FCMP_TD = { 불일치: "fmis", 미입력: "fnone" };
  const fcmpB = (r) => (r.filed_cmp === "불일치" ? `<b class="bad">불일치</b>` : r.filed_cmp === "미입력" ? '<span class="small">미입력</span>' : r.filed_cmp ? '<span class="ok small">일치</span>' : "");
  const BKC = { 사업보고서: "rep", "전년도 사업보고서": "prev", 주총소집공고: "agm", "주총소집공고+사업보고서 본문": "agm", "사업보고서 본문": "rep" };
  const bkB = (k) => (k ? `<span class="bk ${BKC[k] || ""}">${esc(k)}</span>` : NA);
  const reRx = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // 근거 글에서 인용(marks)을 <mark> 로, 띄어쓰기 차이는 \s* 로 느슨하게
  const markText = (text, marks) => {
    let h = esc(text);
    for (const m of marks || []) {
      const w = String(m).trim().split(/\s+/).filter(Boolean).map((x) => reRx(esc(x)));
      if (!w.length || w.join("").length > 1500) continue;
      try { h = h.replace(new RegExp(w.join("\\s*")), (x) => `<mark>${x}</mark>`); } catch (_) { /* 패턴 오류는 강조만 건너뜀 */ }
    }
    return h;
  };
  // 정관의변경.txt 대비표 1행 ('정관조항 | 변경전 | 변경후 | 목적', 칸 안 줄바꿈은 ' / ')
  const amendRow = (row) => {
    const cells = String(row.l || "").split(" | ");
    const hd = String(row.h || "").split(" | ").map((x) => x.replace(/\s/g, ""));
    const at = (k) => hd.findIndex((x) => x.includes(k));
    let iA = at("정관조항"), iB = at("변경전"), iC = at("변경후"), iD = at("목적");
    if (iB < 0 || iC < 0) { iA = cells.length >= 4 ? 0 : -1; iB = iA + 1; iC = iA + 2; iD = iA + 3; }
    const g = (i) => (i >= 0 && i < cells.length ? cells[i] : "");
    // '정관조항' 칸이 없는 3칸 대비표는 변경 후(없으면 전) 글 맨 앞의 '제N조(제목)'이 조항명
    const head = (s) => ((String(s).match(/^\s*((?:제\s*\d+\s*조|第\s*\d+\s*條)(?:\s*의\s*\d+)?\s*[(（【\[][^)）】\]\n]{1,25}[)）】\]])/) || [])[1] || "");
    const art = g(iA) || head(g(iC)) || head(g(iB));
    return { art, before: g(iB), after: g(iC), why: g(iD) };
  };
  const slash = (s) => esc(s).replace(/ \/ /g, "<br>");
  // 인용이 가리키는 다른 조항 (예: '제17조 제2항에서 정한 날'), 근거 글(ev.arts)에 그 조가 있으면 해당 항을 함께 보인다. 법령 조문(상법 제462조 등)은 뺀다.
  const CIRC = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";
  // 조 번호: '제N조' · '第N條' 에 섞인 '第N조' · '제N條'(스캔 정관 전사)도 (2026-11-19)
  const artNo = (t) => { const m = String(t || "").match(/(?:제|第)\s*(\d+)\s*(?:조|條)(?:\s*의\s*(\d+))?/); return m ? `${m[1]}${m[2] ? `-${m[2]}` : ""}` : ""; };
  const refsIn = (s) => {
    const out = [], re = /(?:제|第)\s*(\d+)\s*(?:조|條)(?:\s*의\s*(\d+))?(?:\s*(?:(?:제|第)\s*(\d+)\s*(?:항|項)|([①-⑳])))?/g;
    let m;
    while ((m = re.exec(s))) {
      if (/(법|령|규정|법률|시행령)\s*$/.test(s.slice(Math.max(0, m.index - 12), m.index))) continue;
      out.push({ no: `${m[1]}${m[2] ? `-${m[2]}` : ""}`, hang: m[3] ? Number(m[3]) : m[4] ? CIRC.indexOf(m[4]) + 1 : 0, label: m[0].replace(/\s+/g, " ").trim() });
    }
    return out;
  };
  const hangText = (text, n) => {                     // 조 글에서 n번째 항(① …)만
    const c = CIRC[n - 1], t = String(text || "");
    const i = c ? t.indexOf(c) : -1;
    if (i < 0) return "";
    const rest = t.slice(i), j = rest.slice(1).search(/[①-⑳]/);
    return (j < 0 ? rest : rest.slice(0, j + 1)).replace(/\s+/g, " ").trim();
  };
  const refArts = (q, art, arts, quotes) => {
    const sq = (x) => String(x || "").replace(/\s+/g, "");
    const self = artNo(art.title), seen = new Set(), out = [];
    for (const f of refsIn(String(q || ""))) {
      if (f.no === self || seen.has(f.no + ":" + f.hang)) continue;
      const a = arts.find((x) => x !== art && artNo(x.title) === f.no);
      if (!a) continue;
      seen.add(f.no + ":" + f.hang);
      const qq = (quotes || []).find((x) => x !== q && sq(x).length > 8 && sq(a.text).includes(sq(x).slice(0, 30)));
      const text = (f.hang && hangText(a.text, f.hang)) || qq || (a.marks || [])[0] || String(a.text || "").replace(/\s+/g, " ").slice(0, 160);
      out.push({ label: f.label, name: (String(a.title || "").match(/[(（]([^)）]{1,20})[)）]/) || [])[1] || "", text: text.length > 260 ? `${text.slice(0, 260)}…` : text });
    }
    return out;
  };
  // 첨부 정관을 읽을 수 없어 다른 자료로 정한 행(첨부 태그 확인필요): 쓴 자료 이름을 짙은 보라 라벨로(주총 안건은 크림슨), 이유는 작은 글씨 (사용자 결정 2026-11-17)
  const unreadWhy = (r) => {
    const k = (rowsOf("dividend_notes").find((n) => n.stock_code === r.stock_code && (!n.market || n.market === r.market) && /암호화|서비스하지|끊겨/.test(n.kind || "")) || {}).kind || "";
    return /암호화/.test(k) ? "암호화된 PDF" : /서비스하지/.test(k) ? "DART 가 PDF 를 제공하지 않음" : /끊겨/.test(k) ? "정관 이미지가 중간에 끊겨 배당 조항이 없음" : "";
  };
  const altWhy = (r, tail) => {
    const w = unreadWhy(r);
    return `<span class="evwhy">(${r.basis_kind === "전년도 사업보고서" ? "올해 " : ""}첨부 정관을 읽을 수 없음${w ? `: ${esc(w)}` : ""}${tail ? `, ${tail}` : ""})</span>`;
  };
  // 기준일을 바꾸는 안건이 부결·미결(또는 주총이 기준일 뒤)이라 반영하지 않은 회사: 근거 문구 맨 위 회색 라벨 (사용자 지시 2026-11-17)
  const failLabel = (r) => (r.basis_failed || []).map((f) => {
    const mtg = String(f.result_title || "주주총회").replace(/\s*결과.*$/, "");
    const why = /정족수/.test(f.why || "") ? " (정족수 미달)" : "";
    const body = f.result === "기준일 뒤 주총" ? `${esc(f.agm_date || "")} 주총이 기준일 뒤라 아직 반영하지 않음`
      : `${esc(f.agm_date || "")} ${esc(mtg)}에서 기준일 조항 변경 안건이 ${esc(f.result)}${why} → 사업보고서 첨부 정관 기준`;
    return `<b class="evt evfail">주주총회 안건 ${esc(f.result === "기준일 뒤 주총" ? "예정" : f.result)}</b><span class="evwhy">(${body})</span>`;
  }).join("");
  const evSnippet = (r) => failLabel(r) + evSnippetCore(r);
  const evSnippetCore = (r) => {
    const ev = r.ev || {};
    if (ev.notices && ev.notices.length && ev.notices[0].rows.length) {
      const a = amendRow(ev.notices[0].rows[0]);
      // 주총 안건으로 정한 행: 굵은 크림슨 '주주총회 안건' + 작은 글씨 까닭 (사용자 지시 2026-11-17, 정관 칸에는 태그만)
      // 첨부 정관이 1~2년 앞선 주총 개정 전 옛 판(s09j, 2026-11-19 — 한세엠케이 · 한국쉘석유)
      const stale = r.basis_stale_charter ? `(사업보고서 첨부 정관은 ${esc((r.basis_agm_date || "").slice(0, 7).replace("-", "."))} 주주총회 개정 전 옛 판 · 그 주주총회 안건으로 이미 변경됨` : "";
      const why = r.tag === "확인필요" ? altWhy(r, "주주총회 안건으로 정함")
        : stale ? `<span class="evwhy">${stale}${r.basis_unconfirmed ? ' · <b class="bad">KIND 주총 결과로 가결은 확인하지 못함</b>' : ""})</span>`
        : r.basis_unconfirmed ? '<span class="evwhy">(사업보고서 첨부 정관이 이후 주주총회를 통해 변경된 것으로 봄 · <b class="bad">KIND 주총 결과로 가결은 확인하지 못함</b>)</span>'
        : '<span class="evwhy">(사업보고서 첨부 정관이 이후 주주총회를 통해 변경됨)</span>';
      return `<b class="evt evagm">주주총회 안건</b>${why}<b class="evt">${esc(a.art || "")}</b><span class="evq">${a.after ? `<i class="small">변경 후</i> ${esc(a.after.replace(/ \/ /g, " "))}`
        : `<i class="small">대비표 원문 (칸 구분 없음)</i> ${esc(String(ev.notices[0].rows[0].l || "").replace(/ \/ /g, " "))}`}</span>`;
    }
    const arts = ev.arts || [];
    if (!arts.length) return ev.report ? `<b class="evt${r.tag === "확인필요" ? " evalt" : ""}">사업보고서 본문</b>${r.tag === "확인필요" ? altWhy(r) : ""}<span class="evq">${esc(ev.report.slice(0, 200))}</span>` : NA;
    // 첫 인용(LLM 이 결정 문장부터 낸다)이 든 조를 보인다, 참조형이면 배당 조와 기준일 조가 둘 다 있다
    const sq = (s) => String(s || "").replace(/\s+/g, "");
    const q0 = sq((r.quotes || [])[0]).slice(0, 30);
    const body = arts.filter((a) => !a.fiscal);
    const art = (q0 && body.find((a) => (a.marks || []).some((m) => sq(m).includes(q0)) || sq(a.text).includes(q0))) || body[0] || arts[0];
    const q = (r.quotes || [])[0] || (art.marks || [])[0] || art.text.slice(0, 140);
    const im = (art.imgs || []).find((x) => x.crop && x.quote) || (art.imgs || []).find((x) => x.crop);     // 인용이 든 쪽의 그림을 앞세운다
    const refs = refArts(q, art, arts, r.quotes).map((x) => `<span class="evref"><b class="evt">→ ${esc(x.label)}${x.name ? ` (${esc(x.name)})` : ""}</b><span class="evq">${esc(x.text)}</span></span>`).join("")
      // 결산기말 인용이면 사업연도 조(결산기 = 사업연도 끝)를 참고로 (2026-11-19 피드백)
      + arts.filter((a) => a.fiscal).map((a) => `<span class="evref"><b class="evt">→ ${esc(a.title || "사업연도")} <span class="small">(결산기)</span></b><span class="evq">${esc(String(a.text || "").replace(/^\s*\S+\s*[(（【\[]?[^)）】\]]*[)）】\]]?\s*/, "").replace(/\s+/g, " ").slice(0, 120))}</span></span>`).join("");
    const alt = r.basis_kind === "전년도 사업보고서" ? `<b class="evt evalt">전년도 정관</b>${altWhy(r)}` : "";
    return `${alt}<b class="evt">${esc(art.title || "")}</b><span class="evq">${esc(q)}</span>${refs}${im ? `<img class="evthumb" src="${esc(href(im.crop))}" alt="${esc(`${art.title || ""} 스캔 ${im.page}쪽 해당 부분`)}" loading="lazy">` : ""}`;
  };
  // 사업보고서가 없는 상장회사(absent)는 정관을 찾은 문서가 근거: 증권신고서 · 분할계획서 · 기타신고사항 · 홈페이지
  const SRC_DOCS = ["증권신고서", "분할계획서", "기타신고사항", "홈페이지"];
  const isSrcDoc = (r) => SRC_DOCS.includes(r.basis_kind);
  // 근거문서 안의 '그 회사 정관' 이름: 분할계획서면 분할신설회사 정관(안)(계획서 쪽), 합병 증권신고서의 존속회사 부분이면 그렇게 (모회사·스팩 정관과 헷갈리지 않게)
  const srcCharterName = (r) => {
    const ac = acBy.get(`${r.market}|${r.stock_code}`) || {};
    const t = String(ac.charter_title || "");
    const pg = t.match(/\((\d+)~(\d+)쪽\)/);
    if (r.basis_kind === "분할계획서") return `분할신설회사 정관(안)${pg ? ` (계획서 ${pg[1]}~${pg[2]}쪽)` : ""}`;
    if (t.includes("존속회사 정관 부분")) return "정관 (존속회사 부분)";
    return "정관";
  };
  const srcDocTitle = (r) => (r.basis_kind === "분할계획서" ? `분할계획서 안 ${srcCharterName(r)}` : `${r.basis_kind} ${srcCharterName(r)}`);
  const basisLinks = (r, short) => {
    const sep = short ? "<br>" : " · ";
    const nd = r.basis_notice_rcept_no ? ymd(dateOfRno(r.basis_notice_rcept_no)) : "";
    const parts = [];
    if (r.basis_notice_url) {
      parts.push(ext(r.basis_notice_url, short ? `소집공고 ${nd}` : `주주총회소집공고 ${nd} · ${esc(r.basis_notice_rcept_no)}`, "DART 주주총회소집공고"));
      parts.push(ext(r.basis_result_url, short ? `결과공시 ${esc(r.basis_agm_date || "")}` : `${esc(r.basis_result_title || "주주총회결과")} ${esc(r.basis_agm_date || "")} · ${esc(r.basis_result_acptno || "")}`, "KIND 주주총회결과 공시"));
      if (!short && r.basis_kind === "주총소집공고+사업보고서 본문") parts.push(ext(r.report_url, `사업보고서 본문 ${esc(r.rcept_no)}`, "DART 사업보고서, 6. 배당에 관한 사항"));
      if (!short && r.basis_kind === "주총소집공고") parts.push(`<span class="small">안건 전 정관:</span> ${ext(r.basis_doc_url, `${r.basis_prev_report_nm ? esc(r.basis_prev_report_nm) : "사업보고서"} ${esc(r.basis_rcept_no)}`, "DART 사업보고서")}`);
    } else if (isSrcDoc(r)) {
      const d = ymd(dateOfRno(r.basis_rcept_no));
      parts.push(ext(r.basis_doc_url, short ? `원문${d ? ` ${d}` : ""}` : `${esc(r.basis_kind)}${r.basis_rcept_no ? ` ${esc(r.basis_rcept_no)}` : ""}`, "정관을 찾은 근거문서 (사업보고서가 없는 회사)"));
      if (!short && r.basis_charter_url && r.basis_charter_url !== r.basis_doc_url) parts.push(ext(r.basis_charter_url, esc(srcCharterName(r)), `${srcCharterName(r)} (${AOI})`));
    } else {
      parts.push(ext(r.basis_doc_url, short ? (r.basis_prev_report_nm ? esc(r.basis_prev_report_nm).replace("사업보고서 ", "사업보고서<br>") : `사업보고서 ${ymd(dateOfRno(r.basis_rcept_no))}`)
        : `${esc(r.basis_prev_report_nm || "사업보고서")} ${esc(r.basis_rcept_no)}`, "DART 사업보고서"));
      if (!short && r.basis_charter_url) parts.push(ext(r.basis_charter_url, "정관 첨부", `DART 정관 첨부 (${AOI})`));
    }
    for (const f of r.basis_failed || []) {      // 반영하지 않은 기준일 변경 안건의 소집공고 · 결과공시
      const word = f.result === "기준일 뒤 주총" ? "주총 예정" : f.result;
      parts.push(ext(f.url, short ? `소집공고 ${ymd(dateOfRno(f.rcept_no))} (${esc(word)})` : `주주총회소집공고 ${ymd(dateOfRno(f.rcept_no))} · ${esc(f.rcept_no)} (기준일 변경 안건 ${esc(word)})`, "DART 주주총회소집공고"));
      if (f.result_url) parts.push(ext(f.result_url, short ? `결과공시 ${esc(f.agm_date || "")}` : `${esc(f.result_title || "주주총회결과")} ${esc(f.agm_date || "")} · ${esc(f.result_acptno || "")}`, "KIND 주주총회결과 공시"));
    }
    return parts.filter((x) => x && x !== NA).join(sep);
  };

  // 결산월: 사업보고서 기준. 지금(KIND 상장법인목록, s02d) 결산월이 다르면 빨간 글씨, 결산기가 여럿인 리츠는 그 달들을 작게
  const settleCell = (r) => {
    if (!r.settle_month) return NA;
    const now = r.settle_month_now;
    if (r.settle_changed) return `${esc(r.settle_month)}월<br><span class="bad small chg" title="KIND 상장법인목록 지금 결산월 ${esc(now)}월">(사업보고서 제출 이후 결산월 변경)</span>`;
    if (Array.isArray(r.settle_months) && r.settle_months.length > 1) return `${esc(r.settle_month)}월<br><span class="small" title="리츠: 결산기가 ${12 / r.settle_months.length}개월이라 결산월이 여럿 (KIND 상장법인목록에는 ${esc(now)}월)">결산기 ${r.settle_months.join("·")}월</span>`;
    return `${esc(r.settle_month)}월`;
  };

  function detailDiv(r) {
    const ev = r.ev || {};
    const byNotice = !!r.basis_notice_rcept_no;
    let h = sec("분류", kv([
      ["회사명", `<b>${e(r.corp_name)}</b>`], ["종목코드", mono(r.stock_code)],
      ["결산월", settleCell(r)], ["증권구분", e(r.sec_group)],
      ["결산배당 기준일", e(r.final_record)], ["지금 결산월 (KIND)", r.settle_month_now ? `${esc(r.settle_month_now)}월` : ""],
      ["정관 태그 (지금)", dtag(r.tag_current), { hl: r.changed }],
      [isSrcDoc(r) ? esc(srcDocTitle(r)) : "사업보고서 첨부 정관", `${dtag(r.tag)}${r.prev_tag ? ` <span class="small">· 전년도 정관 ${esc(TL(r.prev_tag))}</span>` : ""}`],
      r.filed ? ["상장공시시스템 신고", `${ftag(r.filed)}${r.filed_date ? ` ${mono(r.filed_date)}` : ""} ${fcmpB(r)}${r.filed_why ? `<br><span class="small">${esc(r.filed_why)}</span>` : ""}`,
        { wide: true, hl: r.filed_cmp === "불일치" }] : null,
      ["근거 조·항", e(r.basis_article)], ["정관이 고정한 시점", e(r.fixed_point)],
      ["중간배당 기준일", e(r.interim)], ["분기배당 기준일", e(r.quarterly)],
      ["판단 이유", e(r.note), { wide: true }],
      r.attached_note ? ["첨부 정관 판단", `<span class="small">${e(r.attached_note)}</span>`, { wide: true }] : null,
      r.basis_note ? ["근거 메모", e(r.basis_note), { wide: true, hl: true }] : null,
      r.reviewed_why ? ["재검토 (Claude 원문 대조)", `${e(r.reviewed_why)}${r.llm_tag !== r.tag ? ` <span class="small">(LLM ${esc(TL(r.llm_tag))})</span>` : ""}`, { wide: true }] : null,
    ]));
    h += sec("분류 근거의 종류", kv([
      ["종류", bkB(r.basis_kind), { wide: true }],
      ["근거 문서", basisLinks(r, false), { wide: true }],
      ["해당 문구 URL", ext(r.ev_url, esc(r.ev_label || r.ev_url)), { wide: true }],
    ]));
    const notices = (ev.notices || []).map((n) => `<p class="small">소집공고 ${ymd(n.rcept_dt)} · ${ext(r.basis_notice_url || dartUrl(n.rcept_no), esc(n.rcept_no), "DART")} · ${loc(n.txt, "정관의변경.txt")}</p>
      <div class="grid static"><table class="amend"><thead><tr><th>정관 조항</th><th>변경 전</th><th>변경 후</th><th>변경의 목적</th></tr></thead><tbody>${
        n.rows.map((row) => {
          const a = amendRow(row);
          // 칸 구분(' | ')이 없는 공고는 변경 전·후를 나눌 수 없다, 대비표 원문을 한 칸에
          if (!a.after && !a.why) return `<tr><td class="c">${slash(a.art)}</td><td colspan="3"><span class="small">대비표 원문 (칸 구분 없음, 변경 전·후가 이어져 있다)</span><br>${slash(row.l).replace(/\n/g, "<br>")}</td></tr>`;
          return `<tr><td class="c">${slash(a.art)}</td><td>${slash(a.before)}</td><td class="after">${slash(a.after)}</td><td>${slash(a.why)}</td></tr>`;
        }).join("")}</tbody></table></div>`).join("");
    const result = (r.basis_result_rows || []).length ? `<div class="grid static"><table><thead><tr><th>번호</th><th>안건</th><th>결과</th></tr></thead><tbody>${
      r.basis_result_rows.map(([no, it, res]) => `<tr><td class="c mono">${esc(no)}</td><td>${esc(it)}</td><td class="c">${res === "가결" ? `<b class="ok">${esc(res)}</b>` : `<b class="bad">${esc(res)}</b>`}</td></tr>`).join("")}</tbody></table></div>
      <p class="small">KIND ${ext(r.basis_result_url, esc(r.basis_result_title || "주주총회결과"))} · 주총 ${esc(r.basis_agm_date || "")}. 배당·기준일 세부 안건이 있으면 그 행, 없으면 정관 안건 전체로 판정</p>` : "";
    const arts = (ev.arts || []).map((a) => {
      const imgs = (a.imgs || []).map((im) => {
        const src = im.crop ? href(im.crop) : im.src;
        if (!src) return "";
        return `<figure class="crop"><a href="${esc(im.src || src)}" target="_blank" rel="noopener" title="DART 원본 ${im.page}쪽 전체"><img src="${esc(src)}" data-alt="${esc(im.src || "")}" alt="${esc(`${a.title || ""}, 스캔 ${im.page}쪽`)}" loading="lazy"></a>
          <figcaption>${im.src_page ? `분할계획서 ${im.src_page}쪽` : `스캔 ${im.page}쪽`}${im.how === "lines" ? " · 해당 줄만 잘라 냄" : im.crop ? " · 쪽 전체" : " · DART 원본"} · ${ext(im.src, "DART 원본 쪽")}</figcaption></figure>`;
      }).join("");
      const pdfs = (a.pdf || []).map((p) => ext(p.src ? `${p.src}#page=${p.page}` : "", `PDF ${p.page}쪽${p.scanned ? " (스캔)" : ""}`, "DART PDF")).join(" · ");
      return `<div class="art"><div class="arthead">${esc(a.title || "")}${a.how === "window" ? ' <span class="small">(조 머리를 못 찾아 인용 앞뒤를 잘라 보임)</span>' : ""}${pdfs ? ` <span class="small">${pdfs}</span>` : ""}</div>
        ${imgs ? `<div class="crops">${imgs}</div><details class="artx"><summary>OCR 글 보기</summary><pre class="arttext">${markText(a.text, a.marks)}</pre></details>` : `<pre class="arttext">${markText(a.text, a.marks)}</pre>`}</div>`;
    }).join("");
    if (byNotice) {
      h += sec("근거 문구: 정관의 변경 안건", notices || '<p class="small">대비표 행을 찾지 못했습니다. 소집공고 원문을 보세요.</p>', "변경 후 칸이 지금 정관 문구");
      if (result) h += sec("주주총회 결과 (KIND)", result);
      if (ev.report) h += sec("사업보고서 본문: 배당관련 예측가능성", `<pre class="arttext">${esc(ev.report)}</pre>`, ext(r.report_url, "DART 사업보고서"));
      if (arts) h += sec(r.prev_tag ? "안건 전 정관: 전년도 사업보고서 첨부" : "안건 전 정관: 사업보고서 첨부", arts, "인용 문장은 노란색");
    } else {
      h += sec(r.basis_kind === "전년도 사업보고서" ? "근거 문구: 전년도 사업보고서 첨부 정관" : isSrcDoc(r) ? `근거 문구: ${esc(srcDocTitle(r))}` : "근거 문구: 사업보고서 첨부 정관", arts || NA, "조항 단위 · 판별에 쓴 문장은 노란색");
    }
    return { title: r.corp_name, sub: `${r.stock_code || ""} · 결산배당 기준일 ${TL(r.tag_current)}${r.filed ? ` · 신고 ${r.filed}${r.filed_cmp === "불일치" ? " (불일치)" : ""}` : ""}`, html: h };
  }

  // 시장 고르기, 라디오 + CSS(:checked ~) 로만 바꾼다 (custom 탭은 필터 줄이 없다)
  function statHtml() {
    if (!DVS.n) return `<div class="notice">site/dividend.js 가 없습니다. <code>python -X utf8 scripts/s10_dividend_site.py</code> 로 만듭니다.</div>`;
    const BM = DV.stats_by_market || { 전체: DVS };
    const ks = Object.keys(BM).filter((k) => BM[k] && BM[k].n);
    if (ks.length <= 2) return statOne(DVS, ks.find((k) => k !== "전체") || "코스피");
    const id = (k) => `dvm-${ks.indexOf(k)}`;
    return `${ks.map((k, i) => `<input type="radio" name="dvm" id="${id(k)}" class="dvm-r"${i ? "" : " checked"}>`).join("")}
      <div class="dvm-bar" role="group" aria-label="시장">${ks.map((k) => `<label for="${id(k)}">${esc(k)}<span class="n">${fmtN(BM[k].n)}사</span></label>`).join("")}</div>
      ${ks.map((k) => `<div class="dvm-p ${id(k)}">${statOne(BM[k], k)}</div>`).join("")}`;
  }

  function statOne(s, m) {
    const mq = m && m !== "전체" ? `&market=${m}` : "";
    const who = m && m !== "전체" ? m : Object.keys(s.markets || {}).join("·") || "코스피";
    const pct = (n, d) => (d ? ((100 * n) / d).toFixed(1) : "0.0");
    const present = DORD.filter((t) => (s.tag_current[t] || 0) > 0);
    const tiles = DORD.filter((t) => t !== "확인필요").map((t) => `<div class="stile"><div class="t">${dtag(t)}</div>
      <div class="v">${fmtN(s.tag_current[t] || 0)}<span class="u">사</span> <span class="p">${pct(s.tag_current[t] || 0, s.n)}%</span></div></div>`).join("");
    const bar = (label, c, sub) => {
      const tot = present.reduce((a, t) => a + (c[t] || 0), 0);
      const on = present.filter((t) => c[t]);
      return `<div class="sbrow"><div class="sbl">${label}<span class="small">${sub}</span></div><div>
        <div class="sb" role="img" aria-label="${esc(`${label}: ${present.map((t) => `${TL(t)} ${c[t] || 0}사`).join(", ")}`)}">${
          on.map((t) => `<span class="seg ${DTAG[t]}" style="flex:${c[t]}" title="${esc(`${label} · ${TL(t)} ${fmtN(c[t])}사 (${pct(c[t], tot)}%)`)}"></span>`).join("")}</div>
        <div class="sbv">${on.map((t) => `<span style="flex:${c[t]}">${c[t] / tot >= 0.05 ? `<b>${fmtN(c[t])}</b> <span class="small">${pct(c[t], tot)}%</span>` : ""}</span>`).join("")}</div></div></div>`;
    };
    const legend = `<div class="lgd">${present.map((t) => `<span><i class="sw ${DTAG[t]}"></i>${esc(TL(t))}</span>`).join("")}<span class="small">막대 아래 숫자 = 회사 수와 비율 · 막대에 마우스를 올리면 태그별 값</span></div>`;
    const xt = (title, data, opt = {}) => {
      const rowsK = opt.rows || [...new Set(data.map((d) => String(d[1] ?? "")))];
      const cols = DORD.filter((t) => data.some((d) => d[0] === t && d[2]));
      const get = (t, b) => (data.find((d) => d[0] === t && String(d[1] ?? "") === b) || [0, 0, 0])[2];
      const ttl = (t) => rowsK.reduce((a, b) => a + get(t, b), 0);
      const body = rowsK.map((b) => {
        const sum = cols.reduce((a, t) => a + get(t, b), 0);
        return `<tr><th class="rh">${esc(opt.fmt ? opt.fmt(b) : b || "(빈 값)")}</th>${cols.map((t) => {
          const n = get(t, b), hi = opt.hi && opt.hi[0] === t && opt.hi[1] === b;
          return `<td class="num${hi ? " hi" : ""}"${hi ? ` title="${esc(opt.hiTip || "")}"` : ""}>${n ? fmtN(n) : '<span class="zero">0</span>'}<span class="small"> ${n ? `${pct(n, ttl(t))}%` : ""}</span></td>`;
        }).join("")}<td class="num"><b>${fmtN(sum)}</b></td></tr>`;
      }).join("");
      return `<div class="xtbox"><h4 class="sec">${title}</h4><div class="grid static"><table class="xt"><thead><tr><th></th>${cols.map((t) => `<th>${dtag(t)}</th>`).join("")}<th>계</th></tr></thead>
        <tbody>${body}</tbody><tfoot><tr><th class="rh">계</th>${cols.map((t) => `<td class="num"><b>${fmtN(ttl(t))}</b></td>`).join("")}<td class="num"><b>${fmtN(cols.reduce((a, t) => a + ttl(t), 0))}</b></td></tr></tfoot></table></div>
        ${opt.note ? `<p class="small">${opt.note}</p>` : ""}</div>`;
    };
    const SUBO = ["고정", "이사회결정", "혼합", "없음", "확인필요"];
    const qn = (s.no_but_q_fixed || []).length, inn = (s.no_but_i_fixed || []).length;
    const ay = (s.amend_year_no || []).map(([y, n]) => `<tr><th class="rh">${esc(y)}</th><td class="num">${fmtN(n)}</td></tr>`).join("");
    const bk = Object.entries(s.basis_kind || {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<tr><th class="rh">${bkB(k)}</th><td class="num">${fmtN(n)}</td></tr>`).join("");
    const klca = (s.klca || []).map((x) => `<tr>${x.map((v, i) => (i ? `<td>${esc(v)}</td>` : `<th class="rh">${esc(v)}</th>`)).join("")}</tr>`).join("");
    return `<p class="desc">${esc(who)} 사업보고서 ${fmtN(s.n)}사의 정관에서 <b>결산배당</b>을 받을 주주를 정하는 기준일 조항을 분류한 결과의 집계다. 분류는 사업보고서 첨부 정관을 기본으로,
        제출 뒤 주주총회에서 가결된 정관 변경(KIND 주주총회결과로 확인)과 첨부 정관을 읽을 수 없던 회사의 대체 자료(전년도 정관·소집공고)를 반영했다.
        자세한 방법은 ${loc(DVL.doc, "docs/04")}, 규제 연혁은 ${loc(DVL.history, "regulation-history")}.</p>
      <div class="stiles">${tiles}</div>
      <h4 class="sec">태그 구성</h4>${legend}
      <div class="sbars">${bar(esc(who), s.tag_current, `${fmtN(s.n)}사`)}</div>
      <div class="xtgrid">
      ${xt("결산배당 × 분기배당 기준일", s.x_quarterly, { rows: SUBO, hi: ["정관no", "고정"], hiTip: "결산배당은 이사회가 정하는데 분기배당은 3·6·9월 말 등으로 고정",
        note: `<b class="hl">결산배당은 정관 N 인데 분기배당 기준일은 고정(대개 3·6·9월 말)인 회사가 ${fmtN(qn)}사</b>다 (<a href="#div" data-go="div:qfix${esc(mq)}">배당기준일 탭에서 보기</a>). 결산배당 표준정관은 2023.2.8 에 바뀌었지만,
          분기배당은 자본시장법 제165조의12 가 2025.1.21 에야 기준일을 풀었고 표준정관 분기배당 조는 2025.1.24 에 바뀌어 정비가 늦다. '없음'은 발췌에 분기배당 조가 보이지 않음.` })}
      ${xt("결산배당 × 중간배당 기준일", s.x_interim, { rows: SUBO, hi: ["정관no", "고정"], hiTip: "결산배당은 이사회가 정하는데 중간배당은 6월 30일 등으로 고정",
        note: `결산배당 정관 N 이면서 중간배당 기준일을 고정(대개 6월 30일)한 회사 ${fmtN(inn)}사. 중간배당(상법 제462조의3)은 법문이 원래 '이사회 결의로 일정한 날'이다.` })}
      ${xt("증권구분 × 결산배당", s.x_sec_group, { note: "리츠(부동산투자회사)는 결산기가 6개월·3개월인 곳이 많아도 '매 결산기말 현재'면 정관 Y." })}
      ${xt("결산월 × 결산배당", s.x_settle, { rows: ["12월", "12월 아님"] })}
      ${xt("근거가 온 자리 × 첨부 정관 태그", s.x_route, { rows: ["배당조항", "배당조항→기준일조항 참조", "기준일조항(배당 명시)", "기준일조항(배당 명시 없음)", "없음"],
        note: "참조형('제1항의 배당은 제13조 제1항에서 정한 날 현재…')은 2021~2023 표준정관 판이다. 참조된 조가 '이사회의 결의로 정한 날'뿐이면 정관 N(HD현대 계열 등)." })}
      ${xt("정관 원문 종류 × 결산배당", s.x_ctype, { fmt: (v) => CT[v] || v })}
      ${(s.x_filed || []).length ? xt("상장공시시스템 신고 × 정관", s.x_filed, { rows: FORD.filter((v) => s.x_filed.some((d) => d[1] === v)), fmt: (v) => `신고 ${v}`,
        note: `정관 N 은 신고 N, 정관 Y 는 신고 Y 면 맞다(신고 Y 는 신고 기준일도 정관 날짜와 대조). 정관 YorN 은 상장공시시스템에 YorN 이 없어 어느 쪽으로 신고했든 불일치로 센다.
          <b class="hl">불일치 ${fmtN((s.filed_cmp || {}).불일치 || 0)}사 · 미입력 ${fmtN((s.filed_cmp || {}).미입력 || 0)}사</b> (<a href="#div" data-go="div:fcmp=@diff${esc(mq)}">배당기준일 탭에서 보기</a>).` }) : ""}
      <div class="xtbox"><h4 class="sec">정관 N 근거 조항의 개정 표시 연도</h4><div class="grid static"><table class="xt"><thead><tr><th></th><th>회사 수</th></tr></thead><tbody>${ay}</tbody></table></div>
        <p class="small">근거 조항에 '&lt;개정 2024.3.22&gt;' 같은 표시가 붙은 경우만 연도가 있다. 표시 없는 정관이 많아 개정 시기 분포로 읽지 않는다.</p></div>
      <div class="xtbox"><h4 class="sec">분류 근거의 종류</h4><div class="grid static"><table class="xt"><thead><tr><th></th><th>회사 수</th></tr></thead><tbody>${bk}</tbody></table></div></div>
      </div>
      ${klca ? `<div class="xtbox wide"><h4 class="sec">참고: 상장협·코스닥협 집계 (배당절차 개선 정관 정비, 유가증권시장)</h4><div class="grid static"><table class="xt"><thead><tr><th>발표</th><th>모집단</th><th>전체</th><th>유가증권시장</th></tr></thead><tbody>${klca}</tbody></table></div>
        <p class="small">12월 결산 상장사 기준, 리츠·스팩·외국사 등 제외, '기존 정관으로 가능한 회사'를 포함한 집계라 이 페이지의 ${esc(who)} ${fmtN(s.n)}사 태그와 모집단·기준이 다르므로 그대로 비교하지 않는다.</p></div>` : ""}`;
  }

  /* ---------- 확인그룹 (s02e: 사용자가 준 엑셀의 코스피 종목별 그룹 번호, data.js check_group) ---------- */
  const CG = D.check_group || {};
  const CG_NONE = "-";                                   // 코스닥·코넥스 등 확인그룹이 없는 시장
  for (const name of ["dividend", "dividend_notes", "reports"]) {
    if (!T[name]) continue;
    for (const r of T[name].rows) r._cg = r.market === "코스피" ? (CG[r.stock_code] != null ? String(CG[r.stock_code]) : "") : CG_NONE;
    if (!T[name].cols.includes("_cg")) T[name].cols.push("_cg");
  }
  const F_CG = SEL("cg", "확인그룹", "_cg", { order: ["1", "2", "3", "4", "5", CG_NONE], fmt: (v) => (v === CG_NONE ? "- (코스피 아님)" : `${v}그룹`) });

  const CHG_KEYS = new Set(rowsOf("dividend_changes").map((n) => `${n.market}|${n.stock_code}`));   // 배포 뒤 판정이 바뀐 회사 (s10c)

  /* ---------- 탭 ---------- */
  const TABS = [
    {
      id: "div", label: "배당기준일", table: "dividend", title: "배당기준일 (정관의 결산배당 기준일)",
      tip: `정관 (${AOI}) 의 결산배당을 받을 주주를 정하는 기준일 조항 분류`,
      desc: `${esc(Object.keys(DVS.markets || { 코스피: 1 }).join("·"))} 회사마다 정관(${AOI})에서 결산배당을 받을 주주를 정하는 기준일 조항을 읽어 분류했다. '정관' 칸: N = 이사회로 정하는 때 · Y = 정관상 결산일(정관이 박은 날) · YorN = 정관상 결산일, 단 이사회로 정하는 때에도 할 수 있음. ` +
        "코스피 · 코스닥은 회사가 상장공시시스템에 신고한 배당기준일('신고' · '신고 기준일')을 나란히 두었다. 정관과 다르면 빨간 바탕, 미입력은 회색 바탕이고 '신고 대조' 필터로 골라 본다. " +
        "근거는 사업보고서 첨부 정관이고, 제출 뒤 주주총회에서 기준일 조항을 바꾼 회사는 그 소집공고와 KIND 주주총회결과(가결)로, 첨부 정관을 읽을 수 없던 회사는 전년도 정관·소집공고로 정했다. 근거 문구는 조항 단위이고 스캔 정관은 그 쪽의 해당 부분을 잘라 보인다. " +
        "판별은 코스피는 Claude API(Opus 5.5), 코스닥은 같은 지침·발췌로 Claude Code 서브에이전트(Opus 5.5)가 했다. 행을 누르면 조항 전문과 근거 링크가 열린다.",
      filters: [
        [Q("회사명·종목코드"), SEL("market", "시장", "market", { order: MKT }), SEL("tag_current", "정관", "tag_current", { order: DORD, fmt: (v) => DORD_OPT[v] || v }),
          SEL("filed", "신고", "filed", { order: FORD, empty: "- (신고 자료 없음)" }),
          SEL("fcmp", "신고 대조", "filed_cmp", { order: ["일치", "불일치", "미입력"], empty: "- (신고 자료 없음)",
            extra: [{ v: "@diff", label: "불일치 + 미입력", test: (r) => r.filed_cmp === "불일치" || r.filed_cmp === "미입력" }] })],
        [F_MONTH, SEL("quarterly", "분기배당", "quarterly", { order: ["고정", "이사회결정", "혼합", "없음", "확인필요"] }),
          SEL("interim", "중간배당", "interim", { order: ["고정", "이사회결정", "혼합", "없음", "확인필요"] }), F_CG],
        [SEL("basis_kind", "근거 종류", "basis_kind", { order: Object.keys(BKC) }), SEL("sec_group", "증권구분", "sec_group"),
          CHK("changed", "첨부 정관 대비", "지금 태그가 다른 회사", (r) => !!r.changed, ["changed"], "제출 뒤 주총에서 바뀌었거나 대체 자료로 정한 회사"),
          CHK("qfix", "분기배당", "결산 N · 분기 고정", (r) => r.tag_current === "정관no" && r.quarterly === "고정", ["quarterly"], "결산배당은 이사회가 정하는데 분기배당은 고정"),
          CHK("chg", "변경 이력", "배포 뒤 바뀐 회사", (r) => CHG_KEYS.has(`${r.market}|${r.stock_code}`), ["stock_code"], "이미 배포한 판과 견주어 판정이 바뀐 회사 ('변경 이력' 탭)")],
      ],
      sort: ["market", 1],
      cols: [
        C_NO, { k: "market", t: "시장", c: "c", raw: true, h: (r) => mk(r.market), v: (r) => { const i = MKT.indexOf(r.market); return `${i < 0 ? 9 : i}${r.stock_code || ""}`; } },
        C_CODE, C_NAME,
        { k: "settle_month", t: "결산월", c: "c", title: "사업보고서의 결산월 · 지금(KIND 상장법인목록) 결산월과 다르면 빨간 글씨", h: settleCell },
        { k: "tag_current", t: "정관", c: "c", v: (r) => DORD.indexOf(r.tag_current),
          title: "정관의 결산배당 기준일 태그 (지금 유효) · N = 이사회가 정함 · Y = 정관상 결산일 고정 · YorN = 결산일 원칙, 이사회도 정할 수 있음 · 주총에서 바뀐 회사는 근거 문구 칸에 '주주총회 안건'",
          h: (r) => dtag(r.tag_current) },
        { k: "filed", t: "신고", c: "c", td: (r) => FCMP_TD[r.filed_cmp] || "",
          v: (r) => (r.filed ? `${["불일치", "미입력", "일치"].indexOf(r.filed_cmp)}${FORD.indexOf(r.filed)}` : null),
          title: "회사가 상장공시시스템에 신고한 배당기준일 조건 (Y = 특정일 · N = 이사회 결의로 정한 날) · 빨간 바탕 = 정관과 불일치 · 회색 바탕 = 미입력",
          h: (r) => (!r.filed ? NA : `${ftag(r.filed)}${r.filed_cmp === "불일치" ? `<br><span class="bad small" title="${esc(r.filed_why || "")}">불일치</span>`
            : r.filed_cmp === "일치" && r.filed_why ? `<br><span class="small na" title="${esc(r.filed_why)}">참고</span>` : ""}`) },
        { k: "filed_date", t: "신고 기준일", c: "c mono", td: (r) => (r.filed_cmp === "불일치" && /^신고 기준일/.test(r.filed_why || "") ? "fmis" : ""),
          title: "상장공시시스템에 신고한 배당기준일 (신고 Y 만) · 빨간 바탕 = 정관 날짜와 다름", h: (r) => (r.filed_date ? esc(r.filed_date) : NA) },
        { t: "근거 문구 (조항)", c: "ev", need: ["ev"], title: "분류 근거가 된 조항 · 스캔 정관은 그 쪽의 해당 부분 그림 · 소집공고면 '정관의 변경' 대비표의 변경 후 문구. 행을 누르면 전문", h: evSnippet },
        { k: "ev_url", t: "해당 문구 URL", c: "c", title: "스캔 = 그 쪽 DART 원본 그림 · PDF = DART PDF 쪽 · 텍스트 = DART 정관 원문 · 소집공고 = DART 공고",
          h: (r) => ext(r.ev_url, esc((r.ev_label || "열기").replace(/ \(DART.*\)$/, "")), r.ev_label) },
        { k: "basis_kind", t: "근거 종류 · 문서", title: "분류 근거의 종류와 근거 문서 URL (소집공고면 KIND 결과공시도)", v: (r) => r.basis_kind,
          h: (r) => `${bkB(r.basis_kind)}<br><span class="small">${basisLinks(r, true)}</span>` },
        { k: "final_record", t: "결산", c: "c", title: "결산배당 기준일: N = 이사회결정, Y = 정관이 고정한 날(결산기말이면 결산월 말일), YorN = 그 날 또는 이사회결정",
          h: (r) => (!r.final_record ? NA : esc(r.final_record).replace(/ 또는 이사회결정$/, '<br><span class="small">또는 이사회결정</span>')) },
        { k: "quarterly", t: "분기", c: "c", title: "분기배당 기준일 (고정·이사회결정·혼합·없음)", h: (r) => (r.quarterly === "고정" && r.tag_current === "정관no" ? `<b class="hl">${esc(r.quarterly)}</b>` : e(r.quarterly) || NA) },
        { k: "interim", t: "중간", c: "c", title: "중간배당 기준일" },
      ],
      detail: (r) => detailDiv(r),
    },
    {
      id: "divstat", label: "배당기준일 취합", title: "배당기준일 전체 취합결과", custom: statHtml,
      badge: DVS.n ? `${fmtN(DVS.n)}사` : "", tip: "태그 분포와 분기·중간배당 등 교차표",
    },
    {
      id: "divnote", label: "배당 특이사항", table: "dividend_notes", title: "배당기준일 특이사항",
      desc: "분류하면서 따로 적어 둘 회사들. 확인필요였던 회사는 전년도 사업보고서 정관·그 사이 소집공고·사업보고서 본문으로 데이터를 채웠고, 제출 뒤 주총에서 기준일 조항을 바꾼 회사는 KIND 주주총회결과로 가결을 확인했다. 행을 누르면 그 회사의 근거가 열린다.",
      filters: [[Q("회사명·종목코드"), SEL("market", "시장", "market", { order: MKT }), SEL("kind", "분류", "kind"), F_CG]],
      sort: ["kind", 1],
      cols: [
        C_NO, { k: "market", t: "시장", c: "c", h: (n) => mk(n.market) },
        { k: "kind", t: "분류", c: "nm", v: (n) => (MKT.indexOf(n.market) + 1) * 1e5 + n.order * 1000 },
        C_CODE, { k: "corp_name", t: "회사명", c: "nm" },
        { k: "tag", t: "첨부 정관", c: "c", h: (n) => (n.tag ? dtag(n.tag) : NA) },
        { k: "tag_current", t: "지금", c: "c", h: (n) => (n.tag_current ? dtag(n.tag_current) : NA) },
        { k: "text", t: "내용", c: "wrap" },
      ],
      detail: (n) => { const r = rowsOf("dividend").find((x) => x.stock_code === n.stock_code && (!n.market || x.market === n.market)); return r ? detailDiv(r) : { title: n.corp_name || "", sub: n.kind, html: `<p>${esc(n.text)}</p>` }; },
    },
    {
      // 배포한 판 대비 판정이 바뀐 회사 (s10c → dividend_changes, 사용자 지시 2026-11-19 — 배포 뒤 변화 관리)
      id: "divchg", label: "변경 이력", table: "dividend_changes", title: "배당기준일 변경 이력 (배포 뒤 판정이 바뀐 회사)",
      badge: rowsOf("dividend_changes").length ? `${fmtN(rowsOf("dividend_changes").length)}건` : "",
      tip: "이미 배포한 판과 견주어 정관 태그 · 근거 · 신고 대조가 바뀐 회사",
      desc: "이미 배포한 페이지와 견주어 판정이 바뀐 회사를 반영일마다 모았다. '이전'은 바로 앞 배포본의 값, '지금'은 이 페이지의 값이다. " +
        "2026-11-19 반영: 2024 · 2025년 주주총회 소집공고와 KIND 주주총회결과를 더 모아, 사업보고서(2025 결산)에 그 주총 개정 전의 옛 정관을 붙여 둔 회사를 찾아 바로잡았다. " +
        "1~2년 앞선 안건은 대개 첨부 정관에 이미 반영돼 있어서, 안건의 '변경 전' · '변경 후' 문구를 첨부 정관과 대조해 옛 판일 때만 바꿨다. " +
        "2026-11-20 반영: 소집공고에 '정관의 변경'을 서식 절이 아닌 다른 절 안 글이나 본문 끝 별첨으로 적은 경우를 찾도록 절 추출을 보완해, 놓쳤던 2026년 정기주총 안건(KIND 가결)을 반영했다. 행을 누르면 그 회사의 근거가 열린다.",
      filters: [[Q("회사명·종목코드"), SEL("market", "시장", "market", { order: MKT }), SEL("date", "반영일", "date"), SEL("kind", "까닭", "kind")]],
      sort: ["date", -1],
      cols: [
        C_NO, { k: "date", t: "반영일", c: "c", raw: true, title: "반영일과 이번 반영의 이름",
          h: (n) => `<span class="mono">${esc(n.date)}</span>${n.label ? `<br><span class="small">${esc(n.label)}</span>` : ""}` },
        { k: "market", t: "시장", c: "c", h: (n) => mk(n.market) },
        C_CODE, { k: "corp_name", t: "회사명", c: "nm" },
        { k: "tag_before", t: "이전", c: "c", title: "바로 앞 배포본의 정관 태그", h: (n) => (n.tag_before ? dtag(n.tag_before) : NA) },
        { k: "tag_after", t: "지금", c: "c", title: "이 페이지의 정관 태그", h: (n) => (n.tag_after ? dtag(n.tag_after) : NA) },
        { k: "filed_cmp_after", t: "신고 대조", c: "c", title: "상장공시시스템 신고와의 대조: 이전 → 지금",
          h: (n) => (n.filed ? `${ftag(n.filed)}<br><span class="small">${esc(n.filed_cmp_before || "-")} → ${n.filed_cmp_after === "불일치" ? `<b class="bad">불일치</b>` : esc(n.filed_cmp_after || "-")}</span>` : NA) },
        { k: "kind", t: "까닭", c: "nm" },
        { k: "text", t: "내용", c: "wrap" },
        { k: "notice_url", t: "근거 공시", title: "그 주총의 소집공고 (DART) · 주주총회결과 (KIND)",
          h: (n) => [n.notice_url ? ext(n.notice_url, `소집공고 ${ymd(dateOfRno(n.notice_rcept_no))}`, "DART 주주총회소집공고") : "", n.result_url ? ext(n.result_url, `결과공시 ${esc(n.agm_date || "")}`) : ""].filter(Boolean).join("<br>") || NA },
      ],
      detail: (n) => { const r = rowsOf("dividend").find((x) => x.stock_code === n.stock_code && x.market === n.market); return r ? detailDiv(r) : { title: n.corp_name || "", sub: n.kind, html: `<p>${esc(n.text)}</p>` }; },
    },
    {
      id: "list", label: "근거문서", table: "reports", csv: "charter_sources", title: "근거문서 · 정관",
      tip: `정관 (${AOI}) 을 찾은 근거문서 1건 = 1행 · 사업보고서가 기본, 사업보고서가 없는 상장회사는 증권신고서 등`,
      desc: `조회기간 안 사업보고서 최종본 전체(모든 시장), 1건 = 1행이다. ${CMS} 행에는 첨부 목록에서 찾은 정관(${AOI}) 원문과, 근거문서 원본 최초 접수일부터 기준일까지 접수된 주주총회 소집공고(최종본)를 붙였다. ` +
        (AC.length ? `사업보고서가 없는 ${CMS} 상장회사(신규상장·투자회사) ${fmtN(AC.length)}사는 정관을 찾은 다른 문서(증권신고서·분할공시·기타신고사항·홈페이지)를 근거문서로 1행씩 더했다. '근거문서' 칸과 필터로 구분한다. ` : "") +
        "셋째 줄 근거 필터로 정관 원문 종류(텍스트·스캔 이미지·PDF)와 소집공고의 '정관의 변경' 안건 여부를 골라 본다. 시장은 기준일 현재 KIND 상장 목록 기준이다(제출 당시 아님). 행을 누르면 정관 본문 미리보기·스캔 이미지·소집공고 목록이 열린다.",
      filters: [
        [Q(), SEL("market", "시장", "market", { order: MKT, empty: "(빈 값)" }), SEL("src", "근거문서", "_src", { order: SRC_ORDER }), F_CG],
        [SEL("sec_group", "증권구분", "sec_group", { empty: "목록에 없음" }), F_MONTH, F_YEAR, F_AMEND],
        [F_CHR, F_AGM, F_NEW],
      ],
      extra: () => filesLine() + absentBox(),
      sort: ["market", 1],
      cols: [
        C_NO, { k: "market", t: "시장", c: "c", h: (r) => mk(r.market), v: (r) => { const i = MKT.indexOf(r.market); return i < 0 ? 9 : i; } },
        C_CODE, C_NAME,
        { k: "_src", t: "근거문서", c: "c", title: "정관을 찾은 문서: 사업보고서, 사업보고서가 없는 회사는 증권신고서·분할계획서·기타신고사항·홈페이지", v: (r) => { const i = SRC_ORDER.indexOf(r._src); return i < 0 ? 9 : i; }, h: (r) => srcB(r._src) },
        { k: "report_period", t: "결산기", c: "c mono", need: ["report_period", "report_nm"], title: "사업보고서 (결산기) · 정정구분, 근거문서가 사업보고서가 아니면 그 문서 이름",
          h: (r) => (r._abs ? `<span class="small">${e(r.charter_source_nm) || NA}</span>` : `${e(r.report_period) || e(stripTag(r.report_nm)) || NA}${tagB(r.amend_tag ?? tagOf(r.report_nm))}`) },
        { k: "rcept_dt", t: "접수일", c: "c mono", v: (r) => (r._abs ? String(r.charter_source_dt || "").replace(/-/g, "") : r.rcept_dt),
          h: (r) => { const d = r._abs ? String(r.charter_source_dt || "").replace(/-/g, "") : r.rcept_dt; return d ? ymd(d) : NA; } },
        { ...C_RNO(true), v: (r) => (r._abs ? r.charter_source_rcept_no : r.rcept_no),
          h: (r) => (r._abs ? (r.charter_source_url ? ext(r.charter_source_url, esc(r.charter_source_rcept_no || "원문"), `${r._src} 원문`) : e(r.charter_source_rcept_no) || NA) : C_RNO(true).h(r)) },
        { k: "charter_title", t: "정관 첨부", title: `정관 (${AOI}) DART 첨부 문서 URL · – = 정관을 모으지 않은 시장`, need: ["charter_title", "charter_url", "charter_status"],
          h: (r) => (!r._chr ? NA : r.charter_url ? ext(r.charter_url, esc(r.charter_title || "정관"), `정관 URL (${AOI}), DART 첨부`) + (r.charter_status && r.charter_status !== "ok" ? ` ${stB(r.charter_status)}` : "") : stB(r.charter_status)) },
        { k: "charter_content_type", t: "종류", c: "c", h: (r) => ctB(r.charter_content_type) },
        { k: "charter_text_chars", t: "글자 수", c: "num", title: "정관 본문 글자 수 (스캔은 Opus OCR, PDF 는 PDF 글자층과 스캔 쪽 Opus OCR 기준)",
          v: (r) => { const b = r._chr && bestTxt(r); return b ? b.n : null; },
          h: (r) => { const b = r._chr && bestTxt(r); return !b ? num(r.charter_text_chars) : `${num(b.n)}${b.l !== "txt" ? ` <span class="small">${b.l === "Opus" ? "Opus" : "PDF"}</span>` : ""}`; } },
        { k: "charter_n_images", t: "이미지", c: "num" },
        { k: "charter_txt", t: "원문 파일", c: "c", need: ["charter_txt", "charter_img_dir"], title: "정관 본문 txt(스캔은 Opus OCR) · PDF 원본 · 이미지 폴더(로컬)",
          h: (r) => { const b = bestTxt(r); return b || r.charter_img_dir ? [b && `<a class="loc" href="${esc(href(b.p))}" target="_blank" rel="noopener" title="${esc(`${b.f}: ${b.why}\n${b.p}`)}">${b.l}</a>`,
            pdfLinks(r, true), !IS_PAGES && r.charter_img_dir && loc(r.charter_img_dir, "img/")].filter(Boolean).join(" · ")
            : noText(r) ? NO_TEXT : NA; } },
        { k: "agm_count", t: "소집공고", need: ["agm_count", "agm_rcept_nos"], v: (r) => (r._agm ? agmN(r) : null), h: (r) => (r._agm ? agmChips(r) : NA),
          title: "기간 안 소집공고 수 · 칩 = 각 공고 DART (주황 = 정관변경 안건)" },
        { k: "agm_charter_amend_count", t: "정관변경 · txt", need: ["agm_charter_amend_count", "agm_charter_amend_rcept_nos"], v: (r) => (r._agm ? amN(r) : null),
          title: "정관의 변경 (Changes to articles of incorporation) 안건이 있는 소집공고 수 · txt = 정관의변경.txt (정관개정안건 본문, 로컬)",
          h: (r) => (!r._agm ? NA : amN(r) > 0 ? `<b class="hl cnt">${fmtN(amN(r))}</b>${list(r.agm_charter_amend_txt).length ? amTxtChips(r) : ""}` : '<span class="zero cnt">0</span>') },
      ],
      detail: (r) => detailReport(r),
    },
  ];

  /* ---------- 탭 화면 만들기 ---------- */
  const S = {};
  const visCol = (c, cols) => (c.need ? c.need.length === 0 || c.need.some((x) => cols.includes(x)) : !c.k || cols.includes(c.k));
  const visFilter = (f, cols) => (f.type === "text" ? true : f.type === "select" ? cols.includes(f.key) : !f.need || f.need.some((x) => cols.includes(x)));

  function options(f, rows) {
    const c = new Map();
    for (const r of rows) { const v = r[f.key]; const k = v == null ? "" : String(v); c.set(k, (c.get(k) || 0) + 1); }
    const ord = f.order || [];
    const keys = [...c.keys()].sort((a, b) => {
      if (a === "" || b === "") return a === b ? 0 : a === "" ? 1 : -1;
      const ia = ord.indexOf(a), ib = ord.indexOf(b);
      if (ia !== -1 || ib !== -1) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
      if (f.numeric) return (Number(a) - Number(b)) * (f.desc ? -1 : 1);
      return coll.compare(a, b) * (f.desc ? -1 : 1);
    });
    return keys.map((k) => ({ v: k === "" ? "@empty" : k, label: k === "" ? f.empty || "(빈 값)" : f.fmt ? f.fmt(k) : k, n: c.get(k) }));
  }

  function fieldHtml(tab, f, rows) {
    const id = `${tab.id}-${f.id}`;
    if (f.type === "text") return `<div class="fld"><label class="lbl" for="${id}">${f.label}</label><input type="text" id="${id}" data-f="${f.id}" placeholder="${esc(f.ph)}" autocomplete="off"></div>`;
    if (f.type === "select") {
      const ex = (f.extra || []).map((o) => ({ v: o.v, label: o.label, n: rows.filter(o.test).length }));
      return `<div class="fld"><label class="lbl" for="${id}">${f.label}</label><select id="${id}" data-f="${f.id}"><option value="">전체</option>${
        [...ex, ...options(f, rows)].map((o) => `<option value="${esc(o.v)}">${esc(o.label)} (${fmtN(o.n)})</option>`).join("")}</select></div>`;
    }
    return `<div class="fld"><span class="lbl">${f.label}</span><label class="chk"${f.title ? ` title="${esc(f.title)}"` : ""}><input type="checkbox" id="${id}" data-f="${f.id}"> ${esc(f.text)}</label></div>`;
  }

  const DL_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0L4.8 6.8M8 10l3.2-3.2M2.5 11.5v2h11v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function buildTab(tab) {
    const pane = document.createElement("section");
    pane.className = "pane";
    pane.id = `pane-${tab.id}`;
    pane.setAttribute("role", "tabpanel");
    pane.hidden = true;
    $("#panes").appendChild(pane);
    if (tab.custom) {                      // 표 없는 탭 (배당기준일 전체 취합), html 을 그대로
      pane.innerHTML = tab.custom();
      S[tab.id] = { tab, pane, rows: [], custom: true };
      return;
    }
    const t = T[tab.table];
    if (!t) {
      pane.innerHTML = `<p class="desc">${esc(tab.desc)}</p><div class="notice">결과 파일 <code>data/final/${esc(tab.table)}.json</code> 이 아직 없습니다 (수집 중).
        파일이 생기면 <code>python -X utf8 scripts/s08_site.py</code> 를 다시 실행하세요.</div>`;
      S[tab.id] = { tab, pane, rows: [], missing: true };
      return;
    }
    const allCols = tab.cols.filter((c) => visCol(c, t.cols));
    const filters = tab.filters.map((row) => row.filter((f) => visFilter(f, t.cols))).filter((row) => row.length);
    const sortKey = allCols.some((c) => c.k === tab.sort[0]) ? tab.sort : [allCols.find((c) => c.k)?.k, 1];
    pane.innerHTML = `
      <p class="desc">${esc(tab.desc)}</p>
      ${tab.extra ? tab.extra() : ""}
      <form class="search_tb" autocomplete="off" onsubmit="return false">
        <div class="rows">${filters.map((row) => `<div class="srow">${row.map((f) => fieldHtml(tab, f, t.rows)).join("")}</div>`).join("")}</div>
        <div class="btns"><button type="submit" class="btn_black" data-act="search">조회</button><button type="button" class="btn_white" data-act="reset">초기화</button></div>
      </form>
      <div class="toolbar">
        <span class="total" aria-live="polite"></span>
        <span class="right">
          <details class="colpick"><summary title="보일 칸 고르기 · 끌어서 순서 바꾸기">칸 선택</summary><div class="cpbox"></div></details>
          <label class="small">쪽당 <select data-act="size">${[20, 50, 100, 300].map((n) => `<option value="${n}"${n === 50 ? " selected" : ""}>${n}행</option>`).join("")}</select></label>
          <button type="button" class="btn_down" data-act="csv" title="조회된 행 전체를 CSV(UTF-8 BOM)로 받기">${DL_ICON}다운로드(CSV)</button>
        </span>
      </div>
      <div class="grid rows"><table>
        <thead></thead>
        <tbody></tbody>
      </table></div>
      <div class="paging" role="navigation" aria-label="쪽 번호"></div>`;
    const st = S[tab.id] = { tab, pane, rows: t.rows, allCols, cols: allCols, filters: filters.flat(), sort: sortKey, page: 1, size: 50, filtered: t.rows.slice(), sel: null,
      tbody: $(".grid.rows tbody", pane), thead: $(".grid.rows thead", pane), total: $(".total", pane), paging: $(".paging", pane), colBox: $(".cpbox", pane) };
    colState(st);
    wireCols(st);

    const form = $("form", pane);
    form.addEventListener("submit", (ev) => { ev.preventDefault(); apply(tab.id); });
    form.addEventListener("change", (ev) => { if (ev.target.matches("select, input[type=checkbox]")) apply(tab.id); });
    $('[data-act="reset"]', pane).addEventListener("click", () => { reset(tab.id); apply(tab.id); });
    $('[data-act="size"]', pane).addEventListener("change", (ev) => { st.size = Number(ev.target.value) || 50; st.page = 1; draw(tab.id); });
    $('[data-act="csv"]', pane).addEventListener("click", () => downloadCsv(tab.id));
    st.thead.addEventListener("click", (ev) => {
      const th = ev.target.closest("th[data-k]");
      if (!th) return;
      const k = th.dataset.k;
      st.sort = st.sort[0] === k ? [k, -st.sort[1]] : [k, 1];
      sortRows(tab.id);
      st.page = 1;
      draw(tab.id);
    });
    st.tbody.addEventListener("click", (ev) => {
      if (ev.target.closest("a, button")) return;
      const tr = ev.target.closest("tr[data-i]");
      if (tr) openRow(tab.id, Number(tr.dataset.i));
    });
    st.tbody.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" || ev.target.tagName !== "TR") return;
      openRow(tab.id, Number(ev.target.dataset.i));
    });
    st.paging.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-p]");
      if (!b || b.disabled) return;
      ev.preventDefault();
      st.page = Number(b.dataset.p);
      draw(tab.id);
      const top = $(".toolbar", pane).getBoundingClientRect().top;
      if (top < 0) $(".toolbar", pane).scrollIntoView({ block: "start" });
    });
    sortRows(tab.id);
    draw(tab.id);
  }

  function reset(id) {
    const st = S[id];
    $$("[data-f]", st.pane).forEach((el) => { if (el.type === "checkbox") el.checked = false; else el.value = ""; });
  }

  function apply(id) {
    const st = S[id];
    if (!st || st.missing || st.custom) return;
    const vals = {};
    for (const f of st.filters) {
      const el = $(`[data-f="${f.id}"]`, st.pane);
      vals[f.id] = !el ? "" : f.type === "check" ? el.checked : el.value.trim();
    }
    st.filtered = st.rows.filter((r) => st.filters.every((f) => {
      const v = vals[f.id];
      if (!v) return true;
      if (f.type === "text") return f.test(r, v);
      if (f.type === "select") {
        const xo = f.extra && f.extra.find((o) => o.v === v);
        if (xo) return xo.test(r);
        const x = r[f.key];
        return v === "@empty" ? x == null || x === "" : String(x) === v;
      }
      return f.test(r);
    }));
    sortRows(id);
    st.page = 1;
    draw(id);
  }

  function sortCol(st) {
    const k = st.sort[0];
    return st.allCols.find((c) => (c.k && c.k === k) || (!c.k && `@${c.t}` === k));
  }

  function sortRows(id) {
    const st = S[id];
    const [k, dir] = st.sort;
    if (!k) return;
    const c = sortCol(st);
    const val = c && c.v ? c.v : (r) => r[k];
    st.filtered.sort((a, b) => {
      const x = val(a), y = val(b);
      const xe = x == null || x === "", ye = y == null || y === "";
      if (xe || ye) return xe && ye ? 0 : xe ? 1 : -1;             // 빈 값은 늘 뒤로
      if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
      if (typeof x === "boolean" || typeof y === "boolean") return (Number(x) - Number(y)) * dir;
      if (c && c.raw) return cmpRaw(String(x), String(y)) * dir;
      return coll.compare(String(x), String(y)) * dir;
    });
  }

  const cell = (c, r) => {
    if (c.h) return c.h(r);
    const v = r[c.k];
    if (v == null || v === "") return NA;
    if (Array.isArray(v)) return esc(v.join("; "));
    return c.c && c.c.includes("num") ? num(v) : esc(v);
  };

  function draw(id) {
    const st = S[id];
    const n = st.filtered.length, pages = Math.max(1, Math.ceil(n / st.size));
    st.page = Math.min(Math.max(1, st.page), pages);
    const from = (st.page - 1) * st.size;
    const part = st.filtered.slice(from, from + st.size);
    st.tbody.innerHTML = part.length
      ? part.map((r, i) => `<tr data-i="${from + i}" tabindex="0"${st.sel === r ? ' class="sel"' : ""}>${st.cols.map((c) => { const k = [c.c, c.td && c.td(r)].filter(Boolean).join(" "); return `<td${k ? ` class="${k}"` : ""}>${c.no ? from + i + 1 : cell(c, r)}</td>`; }).join("")}</tr>`).join("")
      : `<tr class="empty"><td colspan="${st.cols.length}">조회 결과가 없습니다.</td></tr>`;
    st.total.innerHTML = `조회 결과 <b>${fmtN(n)}</b>건 <span class="small">/ 전체 ${fmtN(st.rows.length)}건 · ${fmtN(st.page)}/${fmtN(pages)}쪽</span>`;
    st.paging.innerHTML = pagingHtml(st.page, pages);
    $$("th[data-k]", st.thead).forEach((th) => {
      const on = th.dataset.k === st.sort[0];
      th.classList.toggle("asc", on && st.sort[1] === 1);
      th.classList.toggle("desc", on && st.sort[1] === -1);
      th.setAttribute("aria-sort", on ? (st.sort[1] === 1 ? "ascending" : "descending") : "none");
    });
  }

  /* ---------- 칸 고르기 · 순서 (사용자 지시 2026-11-17) ----------
     '칸 선택' 체크로 숨기고, 표 머리글이나 그 목록을 끌어 순서를 바꾼다. 설정은 이 브라우저에만 저장(localStorage), '기본값으로'로 되돌린다.
     No 칸은 늘 맨 앞. CSV 내려받기는 화면 설정과 관계없이 모든 열. */
  const colKey = (c) => (c.no ? "@no" : c.k || `@${c.t}`);
  const colsLs = (id) => `kc-cols:${id}`;
  const lsGet = (k) => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (_) { return null; } };
  const lsSet = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* 저장 못 하면 이번 화면에만 */ } };
  const headHtml = (cols) => `<tr>${cols.map((c) => {
    const cls = [c.k || c.v ? "sort" : "", c.c && c.c.includes("num") ? "num" : "", c.c && c.c.includes("stick") ? "stick" : ""].filter(Boolean).join(" ");
    const key = c.k ? c.k : c.v ? `@${c.t}` : "";
    return `<th${cls ? ` class="${cls}"` : ""}${key && !c.no ? ` data-k="${esc(key)}" aria-sort="none"` : ""} data-ck="${esc(colKey(c))}"${c.no ? "" : ' draggable="true"'}${
      c.title ? ` title="${esc(`${c.title}\n(머리글을 끌어 순서를 바꿀 수 있다)`)}"` : ""}>${esc(c.t)}</th>`;
  }).join("")}</tr>`;
  const colBoxHtml = (st) => {
    const by = new Map(st.allCols.map((c) => [colKey(c), c]));
    return `<p class="small">체크 = 보이기 · 끌어서 순서 바꾸기(표 머리글을 끌어도 된다). 이 브라우저에만 저장된다.</p>
      <ul class="cplist">${st.colOrder.filter((k) => k !== "@no").map((k) => `<li draggable="true" data-ck="${esc(k)}"><span class="grip" aria-hidden="true">⠿</span><label><input type="checkbox" data-ck="${esc(k)}"${st.colHidden.has(k) ? "" : " checked"}> ${esc(by.get(k).t)}</label></li>`).join("")}</ul>
      <div class="cpbtns"><button type="button" class="btn_white" data-act="colall">모두 보이기</button><button type="button" class="btn_white" data-act="coldef">기본값으로</button></div>`;
  };
  function applyCols(st, save = true) {
    const by = new Map(st.allCols.map((c) => [colKey(c), c]));
    st.cols = st.colOrder.filter((k) => !st.colHidden.has(k)).map((k) => by.get(k));
    if (save) {
      const def = st.allCols.map(colKey);
      lsSet(colsLs(st.tab.id), !st.colHidden.size && st.colOrder.join("|") === def.join("|") ? null : { order: st.colOrder, hidden: [...st.colHidden] });
    }
    st.thead.innerHTML = headHtml(st.cols);
    st.colBox.innerHTML = colBoxHtml(st);
  }
  function colState(st) {
    const def = st.allCols.map(colKey);
    const saved = lsGet(colsLs(st.tab.id)) || {};
    const order = (Array.isArray(saved.order) ? saved.order : []).filter((k) => def.includes(k));
    def.forEach((k, i) => {                                   // 저장 뒤 새로 생긴 칸은 기본 순서의 앞 칸 뒤에
      if (order.includes(k)) return;
      const prev = def.slice(0, i).reverse().find((x) => order.includes(x));
      order.splice(prev ? order.indexOf(prev) + 1 : 0, 0, k);
    });
    st.colOrder = def.includes("@no") ? ["@no", ...order.filter((k) => k !== "@no")] : order;
    st.colHidden = new Set((Array.isArray(saved.hidden) ? saved.hidden : []).filter((k) => def.includes(k) && k !== "@no"));
    applyCols(st, false);
  }
  function wireCols(st) {
    let drag = null;
    const target = (ev) => ev.target.closest("li[data-ck], th[data-ck]");
    const after = (ev, el) => { const b = el.getBoundingClientRect(); return el.tagName === "TH" ? ev.clientX > b.left + b.width / 2 : ev.clientY > b.top + b.height / 2; };
    const clear = () => $$(".drop-a, .drop-b, .dragging", st.pane).forEach((x) => x.classList.remove("drop-a", "drop-b", "dragging"));
    for (const host of [st.thead, st.colBox]) {
      host.addEventListener("dragstart", (ev) => {
        const el = target(ev);
        if (!el || el.dataset.ck === "@no") return;
        drag = el.dataset.ck;
        el.classList.add("dragging");
        ev.dataTransfer.effectAllowed = "move";
        try { ev.dataTransfer.setData("text/plain", drag); } catch (_) { /* 일부 브라우저 */ }
      });
      host.addEventListener("dragover", (ev) => {
        const el = target(ev);
        if (!drag || !el) return;
        ev.preventDefault();
        $$(".drop-a, .drop-b", st.pane).forEach((x) => x.classList.remove("drop-a", "drop-b"));
        if (el.dataset.ck !== drag) el.classList.add(after(ev, el) ? "drop-b" : "drop-a");
      });
      host.addEventListener("drop", (ev) => {
        const el = target(ev);
        if (!drag || !el) return;
        ev.preventDefault();
        const from = drag, to = el.dataset.ck, aft = after(ev, el);
        drag = null;
        clear();
        if (from === to) return;
        const o = st.colOrder.filter((k) => k !== from);
        let i = o.indexOf(to) + (aft ? 1 : 0);
        if (o[0] === "@no" && i < 1) i = 1;                  // No 앞으로는 못 간다
        o.splice(i, 0, from);
        st.colOrder = o;
        applyCols(st);
        draw(st.tab.id);
      });
      host.addEventListener("dragend", () => { drag = null; clear(); });
    }
    st.colBox.addEventListener("change", (ev) => {
      const cb = ev.target.closest("input[data-ck]");
      if (!cb) return;
      if (cb.checked) st.colHidden.delete(cb.dataset.ck); else st.colHidden.add(cb.dataset.ck);
      applyCols(st);
      draw(st.tab.id);
    });
    st.colBox.addEventListener("click", (ev) => {
      const b = ev.target.closest("button[data-act]");
      if (!b) return;
      if (b.dataset.act === "coldef") st.colOrder = st.allCols.map(colKey);
      st.colHidden.clear();
      applyCols(st);
      draw(st.tab.id);
    });
  }
  // 열린 '칸 선택'은 바깥을 누르면 닫는다
  document.addEventListener("click", (ev) => { $$("details.colpick[open]").forEach((d) => { if (!d.contains(ev.target)) d.open = false; }); });

  function pagingHtml(p, pages) {
    const s = Math.floor((p - 1) / 10) * 10 + 1, en = Math.min(pages, s + 9);
    const b = (cls, to, label, glyph, dis) => `<button type="button" class="pg ${cls}" data-p="${to}" aria-label="${label}" title="${label}"${dis ? " disabled" : ""}>${glyph}</button>`;
    let h = b("first", 1, "처음", "«", p === 1) + b("prev", Math.max(1, s - 1), "이전 10쪽", "‹", s === 1) + '<span class="nums">';
    for (let i = s; i <= en; i++) h += `<a href="#" class="num${i === p ? " on" : ""}" data-p="${i}"${i === p ? ' aria-current="page"' : ""}>${i}</a>`;
    return h + "</span>" + b("next", Math.min(pages, en + 1), "다음 10쪽", "›", en === pages) + b("last", pages, "끝", "»", p === pages);
  }

  function downloadCsv(id) {
    const st = S[id];
    const t = T[st.tab.table];
    const cols = t.cols.filter((c) => c !== "imgs" && c !== "pdfs" && (c === "_cg" || !c.startsWith("_")));   // 화면용 열은 빼되 확인그룹은 남긴다
    const q = (v) => {
      if (v == null) return "";
      if (Array.isArray(v)) v = v.join(";");
      const s = String(v);
      return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const TAGC = new Set(["tag", "tag_current", "llm_tag", "rule_tag", "agm_tag_after", "prev_tag"]);    // 정관 태그는 화면 표기(N·Y·YorN)로
    const lines = [cols.map((c) => (c === "_cg" ? "check_group" : c)).join(","), ...st.filtered.map((r) => cols.map((c) => q(TAGC.has(c) ? TL(r[c]) : r[c])).join(","))];
    const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
    const stamp = String(M.as_of || D.built || "").replace(/\D/g, "").slice(0, 8);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${st.tab.csv || st.tab.table}${stamp ? "_" + stamp : ""}${st.filtered.length !== st.rows.length ? `_조회${st.filtered.length}건` : ""}.csv`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }

  /* ---------- 상세 ---------- */
  const sec = (title, body, extra) => `<h4 class="sec">${title}${extra ? `<span class="small">${extra}</span>` : ""}</h4>${body}`;
  const kv = (pairs) => {
    let h = "", col = 0;
    const fill = '<div class="k fill"></div><div class="v fill"></div>';
    for (const p of pairs) {
      if (!p) continue;
      const [k, v, o = {}] = p;
      if (o.wide && col === 1) { h += fill; col = 0; }
      const hl = o.hl ? " hl" : "";
      h += `<div class="k${hl}">${k}</div><div class="v${o.wide ? " wide" : ""}${hl}">${v == null || v === "" ? NA : v}</div>`;
      col = o.wide ? 0 : 1 - col;
    }
    return `<div class="kv">${h}${col === 1 ? fill : ""}</div>`;
  };
  const mono = (v) => (v == null || v === "" ? "" : `<span class="mono">${esc(v)}</span>`);
  const usedBy = (ids, title = "사용 사업보고서") => {
    if (!ids.length) return "";
    return sec(title, `<div class="usedby">${ids.map((rno) => {
      const r = arBy.get(rno) || kcBy.get(rno);
      return r ? `<button type="button" class="lnk" data-open="report:${esc(rno)}">${ymd(r.rcept_dt)} · ${esc(r.report_nm)} · ${esc(rno)}</button>`
        : `<span class="mono">${esc(rno)}</span> ${ext(dartUrl(rno), "DART")}`;
    }).join("")}</div>`, `${ids.length}건`);
  };

  // PDF 첨부 링크: 저장소 파일(git 에 들어 있어 GitHub Pages 에서도 열린다) + DART 원본. pdfs = [[file, src_url, 원래 이름], …] (s08)
  function pdfLinks(r, short) {
    const ps = Array.isArray(r.pdfs) ? r.pdfs : [];
    if (!ps.length) return "";
    return ps.map(([f, src, nm], i) => {
      const label = short ? (ps.length > 1 ? `PDF${i + 1}` : "PDF") : esc(nm || f);
      const local = r.charter_dir ? loc(`${r.charter_dir}/${f}`, short ? label : `${label} (사본)`) : "";
      const dart = src ? ext(src, short && local ? "DART" : (short ? label : `${label} (DART)`), "DART 원본 PDF") : "";
      return [local, dart].filter(Boolean).join(short ? "/" : " · ");
    }).join(short ? " " : "<br>");
  }

  // 스캔 이미지: 앞 6장 + '전체 N장 보기'. 각 장은 로컬 파일 → 없으면 DART 원본 주소(data-alt).
  // imgs = [[폴더 기준 파일, DART 원본 주소], …] (s08). 숨긴 장은 펼칠 때 불러온다(loading=lazy).
  function thumbs(base, imgs, n) {
    let items = Array.isArray(imgs) && imgs.length ? imgs.map((x) => (Array.isArray(x) ? x : [x, ""]))
      : Array.from({ length: n || 0 }, (_, i) => [`img/${String(i + 1).padStart(3, "0")}.jpg`, ""]);
    items = items.map(([f, src]) => { const s = String(f).replace(/^\.?\//, ""); return [s.includes("/") ? s : `img/${s}`, src || ""]; });
    const fig = ([f, src], i) => {
      const p = href(`${base}/${f}`);
      return `<figure${i >= 6 ? ' class="more"' : ""}><a href="${esc(p)}" target="_blank" rel="noopener"><img src="${esc(p)}" data-alt="${esc(src)}" alt="${esc(`${i + 1}쪽`)}" loading="lazy"></a><figcaption>${i + 1}쪽</figcaption></figure>`;
    };
    const more = items.length > 6 ? `<p class="allimg"><button type="button" class="btn_white" data-allimg>전체 ${fmtN(items.length)}장 보기</button></p>` : "";
    return `<div class="thumbs">${items.map(fig).join("")}</div>${more}<p class="small">스캔 이미지는 git 에 올리지 않았습니다. 이 컴퓨터에 파일이 없으면 DART 원본 이미지를 바로 불러옵니다. 누르면 크게 열립니다.</p>`;
  }

  function detailReport(row) {
    if (row._abs) return detailAbsent(row);
    const a = arBy.get(row.rcept_no) || row;
    const k = kcBy.get(row.rcept_no) || ("charter_status" in row ? row : null);
    const r = k ? { ...a, ...k } : { ...a };
    const diff = newDiff(r);
    let h = sec("회사·보고서", kv([
      ["회사명", `<b>${e(r.corp_name)}</b>`], ["종목코드", mono(r.stock_code)],
      ["고유번호", mono(r.corp_code)],
      ["시장", r.market ? `${mk(r.market)} <span class="small">KIND ${ymd(r.market_basis_date)} 현재 · 매칭 ${e(r.market_match_by) || "없음"}</span>` : ""],
      ["법인구분", r.corp_cls ? `${e(r.corp_cls)} ${e(CLS[r.corp_cls] || "")} <span class="small">조회 시점 기준</span>` : ""], ["증권구분", e(r.sec_group)],
      ["보고서명", `${e(stripTag(r.report_nm))}${tagB(r.amend_tag ?? tagOf(r.report_nm))}`, { wide: true }],
      ["제출인", e(r.flr_nm)], ["접수일", ymd(r.rcept_dt)],
      ["사업연도", e(r.fiscal_year)], ["결산월", r.settle_month ? `${r.settle_month}월 <span class="small">(${e(r.report_period)})</span>` : e(r.report_period)],
      ["비고 (rm)", e(r.rm)], ["DART 공시", ext(r.dart_url || dartUrl(r.rcept_no), "공시 화면 열기")],
    ]));
    h += sec("접수번호", kv([
      ["rcept_no (최종본)", `${mono(r.rcept_no)} ${ext(dartUrl(r.rcept_no), "DART")}`, { wide: true }],
      ["rcept_no_new (본문)", r.rcept_no_new ? `${mono(r.rcept_no_new)} ${ext(dartUrl(r.rcept_no_new), "DART")}${diff ? '<span class="badge hl">rcept_no 와 다름: [첨부정정] 본문은 이 접수번호</span>' : ' <span class="small">= rcept_no</span>'}` : "", { wide: true, hl: diff }],
      r.rcept_no_new_status ? ["판정", newSt(r.rcept_no_new_status), { wide: true }] : null,
      k && r.orig_rcept_no ? ["원본 최초 접수", `${mono(r.orig_rcept_no)} <span class="small">${ymd(r.orig_rcept_dt)}</span> ${ext(dartUrl(r.orig_rcept_no), "DART")}${r.orig_rcept_no !== r.rcept_no ? '<span class="badge hl">최종본과 다름</span>' : ""}`, { wide: true }] : null,
    ]));
    if (!k) {
      h += CM.includes(r.market) ? `<div class="notice">${esc(r.market)} 정관 표에 이 행이 없습니다.</div>` : `<p class="small">정관·주주총회 소집공고는 ${CMS} 회사만 모았다.</p>`;
      return { title: r.corp_name, sub: `${r.stock_code || ""} · ${r.report_nm || ""}`, html: h };
    }
    return { title: r.corp_name, sub: `${r.stock_code || ""} · ${r.report_nm || ""}`, html: h + charterDetail(r) };
  }

  // 사업보고서가 없는 상장회사: 회사·근거문서 + 정관·소집공고 (사업보고서 행과 같은 상세)
  function detailAbsent(r) {
    const ab = ABS.flatMap((x) => x.rows).find((x) => x._m === r.market && x.stock_code === r.stock_code) || {};
    const h = sec("회사·근거문서", kv([
      ["회사명", `<b>${e(r.corp_name)}</b>`], ["종목코드", mono(r.stock_code)],
      ["고유번호", mono(r.corp_code)], ["시장", mk(r.market)],
      ["증권구분", e(r.sec_group)], ["상장일", e(r.listed_date)],
      ["결산월", r.settle_month ? `${esc(r.settle_month)}월` : ""], ["근거문서", srcB(r._src)],
      ["문서", `${e(r.charter_source_nm)} ${r.charter_source_url ? ext(r.charter_source_url, "원문 열기", `${r._src} 원문`) : ""}`, { wide: true }],
      ["접수일", e(r.charter_source_dt)], ["접수번호", mono(r.charter_source_rcept_no)],
      ["사업보고서가 없는 이유", `${esc(RS[r.reason_code || ab.reason_code] || r.reason_code || ab.reason_code || "")} ${e(r.reason || ab.reason)}`, { wide: true }],
    ]));
    return { title: r.corp_name, sub: `${r.stock_code || ""} · ${r._src} · ${r.charter_source_nm || ""}`, html: h + charterDetail(r) };
  }

  function charterDetail(r) {
    let h = "";
    const base = charterBase(r);
    const cd = cdBy.get(`${r.charter_rcpNo}|${r.charter_dcmNo}`);
    h += sec("정관", kv([
      ["상태", stB(r.charter_status)], ["첨부 제목", e(r.charter_title)],
      ["첨부일", ymd(r.charter_att_date)], ["정관 문서 수", num(r.n_charter_att)],
      ["접수번호 rcpNo", mono(r.charter_rcpNo)], ["문서번호 dcmNo", mono(r.charter_dcmNo)],
      ["정관 URL", r.charter_url ? ext(r.charter_url, esc(r.charter_url), `정관 URL (${AOI})`) : "", { wide: true }],
      ["원문 viewer", r.charter_viewer_url ? ext(r.charter_viewer_url, esc(r.charter_viewer_url)) : "", { wide: true }],
      ["종류", ctB(r.charter_content_type)], ["글자 수 · 이미지", r.charter_content_type ? [`본문 ${num(r.charter_text_chars)}자`, `이미지 ${num(r.charter_n_images)}장`,
        r.charter_llm_chars != null ? `Opus OCR ${num(r.charter_llm_chars)}자` : "",
        r.charter_pdf_chars != null ? `PDF ${num(r.charter_n_pdfs)}개 · ${num(r.charter_pdf_chars)}자` : ""].filter(Boolean).join(" · ") : ""],
      r.charter_pdf_txt ? ["PDF 원문", pdfLinks(r, false), { wide: true }] : null,
      ["로컬 파일", [r.charter_txt && loc(r.charter_txt, "charter.txt"), r.charter_llm_txt && loc(r.charter_llm_txt, "charter_llm.txt"),
        r.charter_pdf_txt && loc(r.charter_pdf_txt, "charter_pdf.txt"),
        !IS_PAGES && r.charter_img_dir && loc(r.charter_img_dir, "img/"), r.charter_meta && loc(r.charter_meta, "meta.json"),
        !IS_PAGES && base && loc(base, "폴더")].filter(Boolean).join(" · "), { wide: true }],
      cd ? ["정관 문서 수집", [`노드 ${num(cd.n_nodes)}`, (cd.n_image_errors || 0) > 0 ? `<b class="bad">이미지 오류 ${fmtN(cd.n_image_errors)}</b>` : "",
        cd.fetched_at ? `수집 ${esc(String(cd.fetched_at).replace("T", " ").slice(0, 16))}` : "",
        list(cd.used_by_rcept_no).length > 1 ? `이 정관을 쓴 사업보고서 ${fmtN(list(cd.used_by_rcept_no).length)}건` : ""].filter(Boolean).join(" · "), { wide: true }] : null,
    ]), AOI);
    const bt = bestTxt(r);
    if (noText(r)) h += `<div class="notice warn">정관 PDF 를 받지 못해 본문이 없습니다 (DART 미서비스 또는 DRM). PDF 사본·DART 주소에는 안내 문구만 있습니다.</div>`;
    if (bt) h += sec("정관 본문 미리보기", `<div class="pvbox" data-path="${esc(bt.p)}"></div>`,
      `${bt.f} · ${fmtN(bt.n)}자 · ${bt.why}${bt.l !== "txt" ? ". 기계가 읽은 글이므로 인용할 때는 이미지와 대조" : ""}`);
    if ((r.charter_n_images || 0) > 0 && base) h += sec("스캔 이미지", thumbs(base, r.imgs, r.charter_n_images), `전체 ${fmtN(r.charter_n_images)}장`);
    if ("agm_rcept_nos" in r || "agm_count" in r) h += agmSection(r);
    return h;
  }

  function agmSection(r) {
    const ids = list(r.agm_rcept_nos), kinds = arr(r.agm_kinds);
    const amIds = arr(r.agm_charter_amend_rcept_nos), amTxt = arr(r.agm_charter_amend_txt), amUrl = arr(r.agm_charter_amend_dart_url);
    const amAt = new Map(amIds.map((id, i) => [id, i]));
    const range = `${ymd(r.orig_rcept_dt) || "?"} ~ ${M.as_of ? ymd(M.as_of.replace(/-/g, "")) : "기준일"}`;
    if (!ids.length) return sec("주주총회 소집공고", `<p class="small">기간 안 소집공고 없음${agmN(r) ? ` (개수 ${fmtN(agmN(r))}, 목록 없음)` : ""}</p>`, range);
    const body = ids.map((id, i) => {
      const n = agBy.get(id) || {};
      const j = amAt.get(id);
      const am = j != null || yes(n.has_charter_amend);
      const txt = n.charter_amend_txt || (j != null ? amTxt[j] : "");
      return `<tr><td class="c no">${i + 1}</td><td class="c mono">${ymd(n.rcept_dt || dateOfRno(id))}</td>
        <td class="c mono">${AG.length && n.rcept_no ? `<button type="button" class="lnk" data-open="notice:${esc(id)}">${esc(id)}</button>` : esc(id)}</td>
        <td>${n.report_nm ? esc(stripTag(n.report_nm)) + tagB(n.amend_tag ?? tagOf(n.report_nm)) : NA}</td>
        <td class="c">${e(n.agm_kind || kinds[i]) || NA}</td>
        <td class="c">${am ? '<b class="hl">있음</b>' : n.error ? '<span class="bad">오류</span>' : '<span class="zero">없음</span>'}</td>
        <td class="c">${n.detect ? esc(DETECT[n.detect] || n.detect) : NA}</td>
        <td class="num">${am ? num(n.section_chars) : NA}</td>
        <td class="c">${ext(n.dart_url || (j != null ? amUrl[j] : "") || dartUrl(id), "공시")}</td>
        <td class="c">${txt ? loc(txt, "정관의변경.txt") : NA}</td></tr>`;
    }).join("");
    let h = sec("주주총회 소집공고", `<div class="grid static"><table><thead><tr><th>No</th><th>접수일</th><th>접수번호</th><th>보고서명</th><th>주총 구분</th>
      <th title="정관의 변경 (Changes to articles of incorporation)">정관의 변경</th><th>찾은 방법</th><th>절 글자 수</th><th>DART</th><th>정관개정안건 본문</th></tr></thead>
      <tbody>${body}</tbody></table></div>`, `${range} · ${fmtN(ids.length)}건 · 정관변경 ${fmtN(amN(r))}건`);
    const items = amIds.map((id, i) => ({ id, n: agBy.get(id) || {}, txt: (agBy.get(id) || {}).charter_amend_txt || amTxt[i] })).filter((x) => x.txt);
    if (items.length) {
      h += sec("정관의변경.txt 미리보기", items.map((x, i) => `<details class="pvd" data-path="${esc(x.txt)}"${i === 0 ? " open" : ""}>
        <summary>${ymd(x.n.rcept_dt || dateOfRno(x.id))} · ${esc(x.id)}${x.n.agm_kind ? ` · ${esc(x.n.agm_kind)}` : ""}</summary><div class="pvbox"></div></details>`).join(""),
      "Changes to articles of incorporation");
    }
    return h;
  }

  function detailNotice(n) {
    const xp = xmlPath(n);
    let h = sec("소집공고", kv([
      ["회사명", `<b>${e(n.corp_name)}</b>`], ["종목코드", mono(n.stock_code)],
      ["고유번호", mono(n.corp_code)], ["접수일", ymd(n.rcept_dt)],
      ["보고서명", `${e(stripTag(n.report_nm))}${tagB(n.amend_tag ?? tagOf(n.report_nm))}`, { wide: true }],
      ["접수번호", `${mono(n.rcept_no)} ${ext(n.dart_url || dartUrl(n.rcept_no), "DART 공시")}`, { wide: true }],
      ["주총 구분", e(n.agm_kind)],
      ["정관의 변경 절", n.error ? '<span class="bad">원문 오류</span>' : yes(n.has_charter_amend) ? '<b class="hl">있음</b>' : n.has_charter_amend == null ? "" : "없음"],
      ["찾은 방법", n.detect ? `${esc(DETECT[n.detect] || n.detect)} <span class="small">(${esc(n.detect)})</span>` : ""], ["절 글자 수", yes(n.has_charter_amend) ? num(n.section_chars) : ""],
      ["정관개정안건 본문", n.charter_amend_txt ? loc(n.charter_amend_txt, esc(n.charter_amend_txt)) : "", { wide: true }],
      ["원문 XML", IS_PAGES ? '<span class="small">git 에 올리지 않아 이 페이지에서는 열 수 없습니다. DART 공시에서 보세요</span>' : xp ? loc(xp, esc(xp)) : "", { wide: true }],
      IS_PAGES ? null : ["폴더", n.folder ? loc(n.folder, esc(n.folder)) : "", { wide: true }],
      n.error ? ["오류", `<span class="bad">${e(n.error)}</span>`, { wide: true }] : null,
    ]));
    h += usedBy(list(n.used_by_rcept_no));
    if (n.charter_amend_txt) h += sec("정관의변경.txt 미리보기", `<div class="pvbox" data-path="${esc(n.charter_amend_txt)}"></div>`, "Changes to articles of incorporation");
    return { title: n.corp_name, sub: `${n.stock_code || ""} · ${n.report_nm || ""} · ${ymd(n.rcept_dt)}`, html: h };
  }

  /* 본문 미리보기: fetch('../' + 경로). 같은 파일은 한 번만 받는다. */
  const txtCache = new Map();
  function getText(path) {
    if (!txtCache.has(path)) {
      const p = fetch(href(path), { cache: "no-cache" }).then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.text(); });
      p.catch(() => txtCache.delete(path));
      txtCache.set(path, p);
    }
    return txtCache.get(path);
  }
  function loadPreview(box, path) {
    if (!box || !path) return;
    box.innerHTML = `<p class="small">불러오는 중… <code>${esc(path)}</code></p>`;
    getText(path).then((txt) => {
      const dir = path.replace(/\/[^/]*$/, "");
      const MAX = 300000, cut = txt.length > MAX;
      const body = esc(cut ? txt.slice(0, MAX) : txt)
        .replace(/→ (img\/[^\s<]+)/g, (m, f) => `→ <a class="loc" href="${esc(href(`${dir}/${f}`))}" target="_blank" rel="noopener">${f}</a>`);
      box.innerHTML = `<div class="pvhead"><span>${fmtN(txt.length)}자 · ${fmtN(txt.split("\n").length)}줄</span>${loc(path, "파일 열기")}</div>
        <pre class="pv">${body}</pre>${cut ? `<p class="small">앞 ${fmtN(MAX)}자만 보였습니다.</p>` : ""}`;
    }).catch((err) => {
      box.innerHTML = `<div class="note">${IS_FILE
        ? "파일(<code>file://</code>)로 연 페이지에서는 브라우저가 로컬 파일 읽기를 막아 미리보기를 보여 줄 수 없습니다. 케이스 폴더에서 <code>python -m http.server 8000</code> 을 실행하고 <code>http://localhost:8000/site/</code> 로 열면 보입니다."
        : `불러오지 못했습니다 (${esc(err && err.message ? err.message : err)}). 이 서버에 원문 파일이 없을 수 있습니다.`}<br>바로 열기: ${loc(path, esc(path))}</div>`;
    });
  }
  function afterDetail(body) {
    $$(".pvbox[data-path]", body).forEach((b) => loadPreview(b, b.dataset.path));
    $$("details.pvd", body).forEach((d) => {
      const go = () => { if (d.open && !d.dataset.loaded) { d.dataset.loaded = "1"; loadPreview($(".pvbox", d), d.dataset.path); } };
      d.addEventListener("toggle", go);
      go();
    });
    $$(".thumbs img, .crops img", body).forEach((img) => {
      const fall = () => {
        const alt = img.dataset.alt;
        if (alt && img.getAttribute("src") !== alt) {          // 로컬 파일 없음 → DART 원본
          img.setAttribute("src", alt);
          const a = img.closest("a");
          if (a) a.href = alt;
          return;
        }
        img.closest("figure").classList.add("noimg");         // DART 도 실패
      };
      img.addEventListener("error", fall);
      if (!img.closest(".more") && img.complete && img.naturalWidth === 0 && img.getAttribute("src")) fall();
    });
    $$("[data-allimg]", body).forEach((b) => b.addEventListener("click", () => {
      const p = b.closest(".allimg");
      p.previousElementSibling.classList.add("all");
      p.remove();
    }));
  }

  /* ---------- 상세 창 ---------- */
  const layer = $("#layer"), lbody = $("#layer-body");
  const stack = [];
  let lastFocus = null;
  function render(entry) {
    const d = entry.fn(entry.row);
    $("#layer-title").textContent = d.title || "";
    $("#layer-sub").textContent = d.sub || "";
    $("#layer-back").hidden = stack.length < 2;
    lbody.innerHTML = d.html;
    lbody.scrollTop = 0;
    afterDetail(lbody);
  }
  function openDetail(fn, row, push) {
    if (!push) { stack.length = 0; lastFocus = document.activeElement; }
    stack.push({ fn, row });
    layer.hidden = false;
    document.body.classList.add("noscroll");
    render(stack[stack.length - 1]);
    $("#layer-x").focus();
  }
  function closeDetail() {
    layer.hidden = true;
    document.body.classList.remove("noscroll");
    stack.length = 0;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  $("#layer-x").addEventListener("click", closeDetail);
  $("#layer-back").addEventListener("click", () => { if (stack.length > 1) { stack.pop(); render(stack[stack.length - 1]); } });
  layer.addEventListener("click", (ev) => { if (ev.target === layer) closeDetail(); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !layer.hidden) closeDetail(); });
  lbody.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-open]");
    if (!b) return;
    const [kind, key] = b.dataset.open.split(/:(.*)/s);
    if (kind === "report") { const r = kcBy.get(key) || arBy.get(key); if (r) openDetail(detailReport, r, true); }
    if (kind === "notice") { const n = agBy.get(key); if (n) openDetail(detailNotice, n, true); }
  });
  function openRow(id, i) {
    const st = S[id];
    const r = st.filtered[i];
    if (!r) return;
    st.sel = r;
    $$("tr.sel", st.tbody).forEach((tr) => tr.classList.remove("sel"));
    const tr = $(`tr[data-i="${i}"]`, st.tbody);
    if (tr) tr.classList.add("sel");
    openDetail(st.tab.detail, r, false);
  }

  /* ---------- 탭 전환 ---------- */
  $("#tabs").innerHTML = TABS.map((t) => `<li><button type="button" role="tab" data-id="${t.id}" aria-controls="pane-${t.id}"${t.tip ? ` title="${esc(t.tip)}"` : ""}>${esc(t.label)}<span class="n">${t.custom ? esc(t.badge || "") : T[t.table] ? fmtN(T[t.table].rows.length) : "수집 중"}</span></button></li>`).join("");
  TABS.forEach(buildTab);
  function show(id) {
    const tab = TABS.find((t) => t.id === id) || TABS[0];
    TABS.forEach((t) => { S[t.id].pane.hidden = t.id !== tab.id; });
    $$("#tabs button").forEach((b) => { const on = b.dataset.id === tab.id; b.parentElement.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); });
    $("#title").textContent = tab.title;
    $("#title").title = tab.tip || "";
    $("#crumb").innerHTML = `kospi-charter<i>›</i>${esc(tab.label)}${T[tab.table] && T[tab.table].updated ? `<i>·</i>${esc(T[tab.table].file)} ${esc(T[tab.table].updated)}` : ""}`;
    return tab;
  }
  $("#tabs").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-id]"); if (b) location.hash = b.dataset.id; });
  // 예전 탭 4개(코스피 정관·전체 사업보고서·소집공고·정관 문서)는 표 하나로 합쳤다, 옛 주소는 그 필터로 연다
  const ALIAS = { kospi: "list:market=코스피", annual: "list", agm: "list:agm=@any", docs: "list:chr=@any" };
  const goTo = (spec, scroll = true) => {
    const i = spec.indexOf(":");
    const id = i < 0 ? spec : spec.slice(0, i), preset = i < 0 ? "" : spec.slice(i + 1);
    if (location.hash.slice(1) !== id) location.hash = id; else show(id);
    if (S[id] && !S[id].missing && !S[id].custom) {
      reset(id);
      for (const p of preset.split("&").filter(Boolean)) {      // 체크칸은 '필터', 선택칸은 '필터=값'
        const j = p.indexOf("=");
        const el = $(`[data-f="${j < 0 ? p : p.slice(0, j)}"]`, S[id].pane);
        if (!el) continue;
        if (el.type === "checkbox") el.checked = true; else el.value = j < 0 ? "" : p.slice(j + 1);
      }
      apply(id);
    }
    if (scroll) $("#tabs").scrollIntoView({ block: "start", behavior: "smooth" });
  };
  const route = (h) => (ALIAS[h] ? goTo(ALIAS[h], false) : show(h));
  window.addEventListener("hashchange", () => route(location.hash.slice(1)));
  $("#panes").addEventListener("click", (ev) => { const c = ev.target.closest("a[data-go]"); if (c) { ev.preventDefault(); goTo(c.dataset.go); } });
  route(location.hash.slice(1) || TABS[0].id);
})();
