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
    $("#summary").hidden = true;
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
  for (const [name, t] of Object.entries(D.tables || {})) {
    if (!t || !Array.isArray(t.cols) || !Array.isArray(t.rows)) continue;
    const cols = t.cols;
    T[name] = { cols, file: t.file, updated: t.updated,
      rows: t.rows.map((r) => { const o = {}; for (let i = 0; i < cols.length; i++) o[cols[i]] = r[i]; return o; }) };
  }
  const rowsOf = (n) => (T[n] ? T[n].rows : []);
  const has = (n, col) => !!T[n] && T[n].cols.includes(col);
  const KC = rowsOf("kospi_charter"), AR = rowsOf("annual_reports"), AG = rowsOf("agm_notices");
  const kcBy = new Map(KC.map((r) => [r.rcept_no, r]));
  const arBy = new Map(AR.map((r) => [r.rcept_no, r]));
  const agBy = new Map(AG.map((r) => [r.rcept_no, r]));
  const M = D.manifest || {};
  const CNT = M.counts || {};
  const WIN = Array.isArray(M.window) ? M.window : [];

  // 한계 문구의 수집시점: manifest.fetched.dart_main = [처음, 마지막] (ISO 시각)
  {
    const span = (M.fetched || {}).dart_main;
    const el = document.getElementById("fetched-dart");
    if (el && Array.isArray(span) && span.length === 2) {
      const f = (s) => String(s).replace("T", " ").slice(0, 16);
      const [a, b] = span.map(f);
      el.textContent = a.slice(0, 10) === b.slice(0, 10) ? `${a} ~ ${b.slice(11)}` : `${a} ~ ${b}`;
    }
  }

  const agmN = (r) => r.agm_count ?? list(r.agm_rcept_nos).length;
  const amN = (r) => r.agm_charter_amend_count ?? list(r.agm_charter_amend_rcept_nos).length;
  const newDiff = (r) => !!r.rcept_no_new && r.rcept_no_new !== r.rcept_no;
  const charterBase = (r) => r.charter_dir || String(r.charter_img_dir || "").replace(/\/img\/?$/, "") || String(r.charter_txt || "").replace(/\/[^/]*$/, "");
  const xmlPath = (n) => (!n.main_xml ? "" : String(n.main_xml).includes("/") || !n.folder ? n.main_xml : `${n.folder}/${n.main_xml}`);

  /* ---------- 머리말 ---------- */
  $("#hinfo").innerHTML = [
    M.as_of ? `<span class="asof">기준일 <b>${esc(M.as_of)}</b></span>` : "",
    `<span>페이지 데이터 ${esc(D.built || "")}</span>`,
  ].join("");
  $("#hbar").innerHTML = [
    WIN.length === 2 ? `조회기간 <b>${esc(WIN[0])} ~ ${esc(WIN[1])}</b>` : "",
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

  /* ---------- 요약 띠 ---------- */
  const tally = (rows, f) => { const o = {}; for (const r of rows) { const k = f(r); o[k] = (o[k] || 0) + 1; } return o; };
  const mkt = AR.length ? tally(AR, (r) => r.market || "기타") : CNT.market || {};
  const nAR = AR.length || CNT.annual_reports;
  const nKC = KC.length || CNT.kospi_rows;
  const ctc = KC.length && has("kospi_charter", "charter_content_type")
    ? tally(KC.filter((r) => r.charter_content_type), (r) => r.charter_content_type) : CNT.charter_content_type || null;
  const nOk = KC.length ? KC.filter((r) => r.charter_status === "ok").length : (CNT.kospi_charter_status || {}).ok;
  let nAgm, nAm, nAmCorp = null;
  if (has("kospi_charter", "agm_rcept_nos")) {
    nAgm = new Set(KC.flatMap((r) => list(r.agm_rcept_nos))).size;
    nAm = new Set(KC.flatMap((r) => list(r.agm_charter_amend_rcept_nos))).size;
    nAmCorp = KC.filter((r) => amN(r) > 0).length;
  } else if (T.agm_notices) {
    nAgm = AG.length;
    nAm = AG.filter((n) => yes(n.has_charter_amend)).length;
  } else {
    nAgm = CNT.agm_notices;
    nAm = CNT.agm_notices_with_charter_amend;
  }
  const V = (v, u = "") => (v == null ? '<span class="wait">수집 중</span>' : `${fmtN(v)}${u ? `<span class="u">${u}</span>` : ""}`);
  const card = (label, value, sub, go, title) => `<div class="cell${go ? " go" : ""}"${go ? ` data-go="${esc(go)}" role="button" tabindex="0"` : ""}${title ? ` title="${esc(title)}"` : ""}>
    <div class="t">${label}</div><div class="v">${value}</div><div class="s">${sub || ""}</div></div>`;
  $("#summary").innerHTML = [
    card("사업보고서 (전 시장)", V(nAR, "건"), MKT.filter((m) => mkt[m]).map((m) => `${m} ${fmtN(mkt[m])}`).join(" · "), "annual"),
    card("코스피 사업보고서", V(nKC, "건"), nOk != null ? `정관 찾음 ${fmtN(nOk)}건` : "", "kospi"),
    card("정관 원문 종류", ctc ? `<span class="trio">${["text", "image", "pdf", "mixed"].filter((k) => k !== "mixed" || ctc[k]).map((k) => `<span>${fmtN(ctc[k])}<i>${CT[k]}</i></span>`).join("")}</span>`
      : V(null), ctc && ctc.empty ? `빈 문서 ${fmtN(ctc.empty)} · 코스피 행 기준` : "코스피 행 기준", "docs", `정관 (${AOI}) 원문 형태`),
    card("기간 내 소집공고", V(nAgm, "건"), "회사별 원본 최초 접수일 ~ 기준일", "agm"),
    card("정관변경 포함 소집공고", V(nAm, "건"), nAmCorp != null ? `해당 회사 ${fmtN(nAmCorp)}사` : "'정관의 변경' 절이 있는 공고",
      "agm:has_amend", `정관의 변경 (Changes to articles of incorporation)`),
  ].join("");

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

  /* ---------- 열 정의 ---------- */
  const C_NO = { t: "No", c: "c no", no: true, need: [] };
  const C_CODE = { k: "stock_code", t: "종목코드", c: "c mono" };
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

  /* ---------- 탭 ---------- */
  const TABS = [
    {
      id: "kospi", label: "코스피 정관", table: "kospi_charter", title: "코스피 정관",
      tip: `정관 (${AOI}): 코스피 사업보고서별 첨부 정관과 주주총회 소집공고`,
      desc: `코스피 회사의 최근 사업보고서(최종본) 1건마다 첨부 목록에서 찾은 정관(${AOI})과, 사업보고서 원본 최초 접수일부터 기준일까지 접수된 주주총회 소집공고(최종본)를 붙였다. 행을 누르면 상세가 열린다.`,
      filters: [
        [Q(), F_MONTH, F_YEAR],
        [F_AMEND, SEL("ctype", "정관 종류", "charter_content_type", { fmt: (v) => CT[v] || v, empty: "정관 없음", order: ["text", "image", "pdf", "mixed", "empty"] }),
          SEL("status", "정관 상태", "charter_status", { fmt: (v) => ST[v] || v, order: Object.keys(ST) })],
        [CHK("agm_amend", "주주총회", "정관변경 주총 있음", (r) => amN(r) > 0, ["agm_charter_amend_count", "agm_charter_amend_rcept_nos"],
          "기간 안 소집공고 중 '정관의 변경'(Changes to articles of incorporation) 안건이 있는 회사"), F_NEW],
      ],
      sort: ["stock_code", 1],
      cols: [
        C_NO, C_CODE, C_NAME,
        { k: "report_period", t: "결산기", c: "c mono", need: ["report_period", "report_nm"], title: "사업보고서 (결산기) · 정정구분",
          h: (r) => `${e(r.report_period) || e(stripTag(r.report_nm)) || NA}${tagB(r.amend_tag ?? tagOf(r.report_nm))}` },
        C_DT("rcept_dt", "접수일"),
        C_RNO(true),
        { k: "charter_title", t: "정관 첨부", title: `정관 (${AOI}) DART 첨부 문서 URL`, need: ["charter_title", "charter_url", "charter_status"],
          h: (r) => (r.charter_url ? ext(r.charter_url, esc(r.charter_title || "정관"), `정관 URL (${AOI}), DART 첨부`) + (r.charter_status && r.charter_status !== "ok" ? ` ${stB(r.charter_status)}` : "") : stB(r.charter_status)) },
        { k: "charter_content_type", t: "종류", c: "c", h: (r) => ctB(r.charter_content_type) },
        { k: "charter_text_chars", t: "글자 수", c: "num", title: "정관 본문 글자 수 — 스캔은 글자 인식(OCR), PDF 는 PDF 글 기준",
          v: (r) => r.charter_llm_chars ?? r.charter_ocr_chars ?? r.charter_pdf_chars ?? r.charter_text_chars,
          h: (r) => (r.charter_llm_chars != null ? `${num(r.charter_llm_chars)} <span class="small">Opus</span>`
            : r.charter_ocr_chars != null ? `${num(r.charter_ocr_chars)} <span class="small">OCR</span>`
            : r.charter_pdf_chars != null ? `${num(r.charter_pdf_chars)} <span class="small">PDF</span>` : num(r.charter_text_chars)) },
        { k: "charter_n_images", t: "이미지", c: "num" },
        { k: "charter_txt", t: "원문 파일", c: "c", need: ["charter_txt", "charter_img_dir"], title: "정관 txt · 글자 인식(OCR) txt · 이미지 폴더(로컬)",
          h: (r) => (r.charter_txt || r.charter_img_dir ? [r.charter_txt && loc(r.charter_txt, "txt"), r.charter_llm_txt && loc(r.charter_llm_txt, "Opus"),
            r.charter_ocr_txt && loc(r.charter_ocr_txt, "OCR"),
            r.charter_pdf_txt && loc(r.charter_pdf_txt, "PDF글"), pdfLinks(r, true),
            !IS_PAGES && r.charter_img_dir && loc(r.charter_img_dir, "img/")].filter(Boolean).join(" · ") : NA) },
        { k: "agm_count", t: "소집공고", need: ["agm_count", "agm_rcept_nos"], v: agmN, h: agmChips, title: "기간 안 소집공고 수 · 칩 = 각 공고 DART (주황 = 정관변경 안건)" },
        { k: "agm_charter_amend_count", t: "정관변경 · txt", need: ["agm_charter_amend_count", "agm_charter_amend_rcept_nos"], v: amN,
          title: "정관의 변경 (Changes to articles of incorporation) 안건이 있는 소집공고 수 · txt = 정관의변경.txt (정관개정안건 본문, 로컬)",
          h: (r) => (amN(r) > 0 ? `<b class="hl cnt">${fmtN(amN(r))}</b>${list(r.agm_charter_amend_txt).length ? amTxtChips(r) : ""}` : '<span class="zero cnt">0</span>') },
      ],
      detail: (r) => detailReport(r),
    },
    {
      id: "annual", label: "전체 사업보고서", table: "annual_reports", title: "전체 사업보고서",
      desc: "조회기간 안 사업보고서 최종본 전체 (모든 시장). 시장은 기준일 현재 KIND 상장 목록 기준이다(제출 당시 아님). [첨부정정] 행은 rcept_no_new 에 본문 접수번호를 적었다. 다르면 주황으로 표시한다.",
      filters: [
        [Q(), SEL("market", "시장", "market", { order: MKT, empty: "(빈 값)" }), SEL("sec_group", "증권구분", "sec_group", { empty: "목록에 없음" })],
        [F_MONTH, F_YEAR, F_AMEND],
        [F_NEW],
      ],
      sort: ["rcept_dt", -1],
      cols: [
        C_NO, { k: "market", t: "시장", c: "c", h: (r) => mk(r.market), v: (r) => { const i = MKT.indexOf(r.market); return i < 0 ? 9 : i; } },
        C_CODE, C_NAME,
        { k: "corp_cls", t: "법인구분", c: "c", h: (r) => (r.corp_cls ? `<span title="${esc(CLS[r.corp_cls] || "")} (현재 기준)">${esc(r.corp_cls)}</span>` : NA) },
        C_RNM,
        { k: "fiscal_year", t: "사업연도", c: "c" },
        { k: "settle_month", t: "결산월", c: "c", h: (r) => (r.settle_month ? `${r.settle_month}월` : NA) },
        C_DT("rcept_dt", "접수일"),
        C_RNO(false),
        { k: "rcept_no_new", t: "rcept_no_new", c: "c mono", title: "[첨부정정] 행의 본문 접수번호, 다르면 주황",
          h: (r) => (!r.rcept_no_new ? NA : newDiff(r) ? `<span class="diffcell">${esc(r.rcept_no_new)}</span>` : `<span class="same">${esc(r.rcept_no_new)}</span>`) },
        { k: "flr_nm", t: "제출인" },
        { k: "rm", t: "비고", c: "c" },
        { k: "sec_group", t: "증권구분", c: "c" },
        { t: "정관", c: "c", need: [], title: `코스피 행의 정관 (${AOI}) 종류`, v: (r) => (kcBy.get(r.rcept_no) || {}).charter_content_type,
          h: (r) => { const k = kcBy.get(r.rcept_no); return k ? (k.charter_content_type ? ctB(k.charter_content_type) : stB(k.charter_status)) : NA; } },
      ],
      detail: (r) => detailReport(r),
    },
    {
      id: "agm", label: "주주총회 소집공고", table: "agm_notices", title: "주주총회 소집공고",
      desc: "코스피 회사의 주주총회소집공고 최종본 중, 회사별로 [사업보고서 원본 최초 접수일, 기준일] 안에 접수된 것. 원문에 '정관의 변경'(Changes to articles of incorporation) 절이 있으면 그 절을 정관의변경.txt 로 저장했다.",
      filters: [
        [Q(), SEL("agm_kind", "주총 구분", "agm_kind", { empty: "구분 미상", order: ["정기", "임시", "정기·종류", "임시·종류", "종류"] }), F_AMEND],
        [CHK("has_amend", "안건", "정관변경 안건 있음", (n) => yes(n.has_charter_amend), ["has_charter_amend"], "Changes to articles of incorporation"),
          SEL("detect", "찾은 방법", "detect", { fmt: (v) => DETECT[v] || v, empty: "해당 없음" }),
          CHK("err", "오류", "원문 받기 오류", (n) => !!n.error, ["error"])],
      ],
      sort: ["rcept_dt", -1],
      cols: [
        C_NO, C_CODE, C_NAME, C_RNM, C_DT("rcept_dt", "접수일"),
        C_RNO(false),
        { k: "agm_kind", t: "주총 구분", c: "c" },
        { k: "has_charter_amend", t: "정관변경", c: "c", title: "정관의 변경 (Changes to articles of incorporation) 절 · 원문 오류는 '오류'",
          need: ["has_charter_amend", "error"], v: (n) => (n.error ? -1 : yes(n.has_charter_amend) ? 1 : 0),
          h: (n) => (n.error ? `<span class="bad" title="${esc(n.error)}">오류</span>` : yes(n.has_charter_amend) ? '<b class="hl">있음</b>' : n.has_charter_amend == null ? NA : '<span class="zero">없음</span>') },
        { k: "detect", t: "찾은 방법", c: "c", h: (n) => (n.detect ? esc(DETECT[n.detect] || n.detect) : NA) },
        { k: "section_chars", t: "글자 수", c: "num", title: "'정관의 변경' 절 글자 수 (공백 제외)", h: (n) => (yes(n.has_charter_amend) ? num(n.section_chars) : NA) },
        { k: "charter_amend_txt", t: "정관의변경.txt", c: "c", h: (n) => loc(n.charter_amend_txt, "txt"), title: "정관개정안건 본문 (로컬 txt)" },
        { k: "main_xml", t: "원문", c: "c", title: "소집공고 원문 XML (로컬) · GitHub Pages 에서는 DART 공시",
          h: (n) => (IS_PAGES ? ext(n.dart_url || dartUrl(n.rcept_no), "DART") : loc(xmlPath(n), "xml")) },
        { k: "used_by_rcept_no", t: "보고서", c: "num", v: (n) => list(n.used_by_rcept_no).length, h: (n) => `${fmtN(list(n.used_by_rcept_no).length)}건`, title: "이 공고를 센 사업보고서 수" },
      ],
      detail: (n) => detailNotice(n),
    },
    {
      id: "docs", label: "정관 문서", table: "charter_docs", title: "정관 문서",
      tip: `정관 (${AOI}) 문서 색인`,
      desc: `내려받은 정관(${AOI}) 문서 1건 = 1행. 같은 정관을 여러 사업보고서가 쓰면 한 줄로 모으고 '사용 보고서'에 센다. 스캔 이미지는 로컬에만 있다.`,
      filters: [
        [Q(), SEL("ctype", "정관 종류", "content_type", { fmt: (v) => CT[v] || v, empty: "(빈 값)", order: ["text", "image", "pdf", "mixed", "empty"] })],
        [CHK("imgerr", "이미지", "이미지 오류 있음", (d) => (d.n_image_errors || 0) > 0, ["n_image_errors"]),
          CHK("multi", "사용 보고서", "2건 이상", (d) => list(d.used_by_rcept_no).length > 1, ["used_by_rcept_no"])],
      ],
      sort: ["stock_code", 1],
      cols: [
        C_NO, C_CODE, C_NAME,
        { k: "att_title", t: "첨부 제목", title: `정관 (${AOI}) 첨부 DART URL`, h: (d) => ext(d.att_url, esc(d.att_title || "정관"), `정관 URL (${AOI})`) },
        C_DT("att_date", "첨부일"),
        { k: "rcpNo", t: "접수번호", c: "c mono" },
        { k: "dcmNo", t: "문서번호", c: "c mono" },
        { k: "content_type", t: "종류", c: "c", h: (d) => ctB(d.content_type) },
        { k: "text_chars", t: "글자 수", c: "num" },
        { k: "n_images", t: "이미지", c: "num" },
        { k: "n_image_errors", t: "오류", c: "num", title: "이미지 내려받기 오류 수", h: (d) => ((d.n_image_errors || 0) > 0 ? `<b class="bad">${fmtN(d.n_image_errors)}</b>` : num(d.n_image_errors)) },
        { k: "n_nodes", t: "노드", c: "num" },
        { t: "원문 파일", c: "c", need: ["folder"], title: "charter.txt · 이미지 폴더 (로컬)",
          h: (d) => (d.folder ? [loc(`${d.folder}/charter.txt`, "txt"), (d.n_images || 0) > 0 ? loc(`${d.folder}/img`, "img/") : ""].filter(Boolean).join(" · ") : NA) },
        { k: "used_by_rcept_no", t: "사용 보고서", c: "num", v: (d) => list(d.used_by_rcept_no).length, h: (d) => `${fmtN(list(d.used_by_rcept_no).length)}건` },
        { k: "fetched_at", t: "수집시점", c: "c mono", h: (d) => (d.fetched_at ? esc(String(d.fetched_at).replace("T", " ").slice(0, 16)) : NA) },
      ],
      detail: (d) => detailDoc(d),
    },
  ];

  /* ---------- 탭 화면 만들기 ---------- */
  const coll = new Intl.Collator("ko", { numeric: true });
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
      return `<div class="fld"><label class="lbl" for="${id}">${f.label}</label><select id="${id}" data-f="${f.id}"><option value="">전체</option>${
        options(f, rows).map((o) => `<option value="${esc(o.v)}">${esc(o.label)} (${fmtN(o.n)})</option>`).join("")}</select></div>`;
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
    const t = T[tab.table];
    if (!t) {
      pane.innerHTML = `<p class="desc">${esc(tab.desc)}</p><div class="notice">결과 파일 <code>data/final/${esc(tab.table)}.json</code> 이 아직 없습니다 (수집 중).
        파일이 생기면 <code>python -X utf8 scripts/s08_site.py</code> 를 다시 실행하세요.</div>`;
      S[tab.id] = { tab, pane, rows: [], missing: true };
      return;
    }
    const cols = tab.cols.filter((c) => visCol(c, t.cols));
    const filters = tab.filters.map((row) => row.filter((f) => visFilter(f, t.cols))).filter((row) => row.length);
    const sortKey = cols.some((c) => c.k === tab.sort[0]) ? tab.sort : [cols.find((c) => c.k)?.k, 1];
    pane.innerHTML = `
      <p class="desc">${esc(tab.desc)}</p>
      <form class="search_tb" autocomplete="off" onsubmit="return false">
        <div class="rows">${filters.map((row) => `<div class="srow">${row.map((f) => fieldHtml(tab, f, t.rows)).join("")}</div>`).join("")}</div>
        <div class="btns"><button type="submit" class="btn_black" data-act="search">조회</button><button type="button" class="btn_white" data-act="reset">초기화</button></div>
      </form>
      <div class="toolbar">
        <span class="total" aria-live="polite"></span>
        <span class="right">
          <label class="small">쪽당 <select data-act="size">${[20, 50, 100, 300].map((n) => `<option value="${n}"${n === 50 ? " selected" : ""}>${n}행</option>`).join("")}</select></label>
          <button type="button" class="btn_down" data-act="csv" title="조회된 행 전체를 CSV(UTF-8 BOM)로 받기">${DL_ICON}다운로드(CSV)</button>
        </span>
      </div>
      <div class="grid rows"><table>
        <thead><tr>${cols.map((c) => {
          const cls = [c.k || c.v ? "sort" : "", c.c && c.c.includes("num") ? "num" : "", c.c && c.c.includes("stick") ? "stick" : ""].filter(Boolean).join(" ");
          const key = c.k ? c.k : c.v ? `@${c.t}` : "";
          return `<th${cls ? ` class="${cls}"` : ""}${key && !c.no ? ` data-k="${esc(key)}" aria-sort="none"` : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.t)}</th>`;
        }).join("")}</tr></thead>
        <tbody></tbody>
      </table></div>
      <div class="paging" role="navigation" aria-label="쪽 번호"></div>`;
    const st = S[tab.id] = { tab, pane, rows: t.rows, cols, filters: filters.flat(), sort: sortKey, page: 1, size: 50, filtered: t.rows.slice(), sel: null,
      tbody: $("tbody", pane), thead: $("thead", pane), total: $(".total", pane), paging: $(".paging", pane) };

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
    if (!st || st.missing) return;
    const vals = {};
    for (const f of st.filters) {
      const el = $(`[data-f="${f.id}"]`, st.pane);
      vals[f.id] = !el ? "" : f.type === "check" ? el.checked : el.value.trim();
    }
    st.filtered = st.rows.filter((r) => st.filters.every((f) => {
      const v = vals[f.id];
      if (!v) return true;
      if (f.type === "text") return f.test(r, v);
      if (f.type === "select") { const x = r[f.key]; return v === "@empty" ? x == null || x === "" : String(x) === v; }
      return f.test(r);
    }));
    sortRows(id);
    st.page = 1;
    draw(id);
  }

  function sortCol(st) {
    const k = st.sort[0];
    return st.cols.find((c) => (c.k && c.k === k) || (!c.k && `@${c.t}` === k));
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
      ? part.map((r, i) => `<tr data-i="${from + i}" tabindex="0"${st.sel === r ? ' class="sel"' : ""}>${st.cols.map((c) => `<td${c.c ? ` class="${c.c}"` : ""}>${c.no ? from + i + 1 : cell(c, r)}</td>`).join("")}</tr>`).join("")
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
    const cols = t.cols.filter((c) => c !== "imgs" && c !== "pdfs");
    const q = (v) => {
      if (v == null) return "";
      if (Array.isArray(v)) v = v.join(";");
      const s = String(v);
      return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [cols.join(","), ...st.filtered.map((r) => cols.map((c) => q(r[c])).join(","))];
    const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
    const stamp = String(M.as_of || D.built || "").replace(/\D/g, "").slice(0, 8);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${st.tab.table}${stamp ? "_" + stamp : ""}${st.filtered.length !== st.rows.length ? `_조회${st.filtered.length}건` : ""}.csv`;
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
      if (r.market === "코스피") h += `<div class="notice">코스피 정관 표에 이 행이 없습니다.</div>`;
      return { title: r.corp_name, sub: `${r.stock_code || ""} · ${r.report_nm || ""}`, html: h };
    }
    const base = charterBase(r);
    h += sec("정관", kv([
      ["상태", stB(r.charter_status)], ["첨부 제목", e(r.charter_title)],
      ["첨부일", ymd(r.charter_att_date)], ["정관 문서 수", num(r.n_charter_att)],
      ["접수번호 rcpNo", mono(r.charter_rcpNo)], ["문서번호 dcmNo", mono(r.charter_dcmNo)],
      ["정관 URL", r.charter_url ? ext(r.charter_url, esc(r.charter_url), `정관 URL (${AOI})`) : "", { wide: true }],
      ["원문 viewer", r.charter_viewer_url ? ext(r.charter_viewer_url, esc(r.charter_viewer_url)) : "", { wide: true }],
      ["종류", ctB(r.charter_content_type)], ["글자 수 · 이미지", r.charter_content_type ? [`본문 ${num(r.charter_text_chars)}자`, `이미지 ${num(r.charter_n_images)}장`,
        r.charter_llm_chars != null ? `Opus 전사 ${num(r.charter_llm_chars)}자` : "",
        r.charter_ocr_chars != null ? `글자 인식 ${num(r.charter_ocr_chars)}자` : "",
        r.charter_pdf_chars != null ? `PDF ${num(r.charter_n_pdfs)}개 · ${num(r.charter_pdf_chars)}자` : ""].filter(Boolean).join(" · ") : ""],
      r.charter_pdf_txt ? ["PDF 원문", pdfLinks(r, false), { wide: true }] : null,
      ["로컬 파일", [r.charter_txt && loc(r.charter_txt, "charter.txt"), r.charter_llm_txt && loc(r.charter_llm_txt, "charter_llm.txt"),
        r.charter_ocr_txt && loc(r.charter_ocr_txt, "charter_ocr.txt"),
        r.charter_pdf_txt && loc(r.charter_pdf_txt, "charter_pdf.txt"),
        !IS_PAGES && r.charter_img_dir && loc(r.charter_img_dir, "img/"), r.charter_meta && loc(r.charter_meta, "meta.json"),
        !IS_PAGES && base && loc(base, "폴더")].filter(Boolean).join(" · "), { wide: true }],
    ]), AOI);
    if (r.charter_txt) h += sec("정관 본문 미리보기", `<div class="pvbox" data-path="${esc(r.charter_txt)}"></div>`, "charter.txt");
    if (r.charter_llm_txt) h += sec("Opus 전사 본문 미리보기", `<div class="pvbox" data-path="${esc(r.charter_llm_txt)}"></div>`,
      `charter_llm.txt · ${fmtN(r.charter_llm_chars)}자 · Claude Opus 5.5 가 스캔 이미지를 직접 읽어 옮긴 글`);
    if (r.charter_ocr_txt) h += sec("글자 인식(OCR) 본문 미리보기", `<div class="pvbox" data-path="${esc(r.charter_ocr_txt)}"></div>`,
      `charter_ocr.txt · ${fmtN(r.charter_ocr_chars)}자 · 스캔 이미지를 기계로 읽은 글자라 틀린 곳이 있을 수 있습니다`);
    if (r.charter_pdf_txt) h += sec("PDF 정관 글 미리보기", `<div class="pvbox" data-path="${esc(r.charter_pdf_txt)}"></div>`,
      "charter_pdf.txt · PDF 글자층을 그대로 뽑았고, 글자층이 없는 쪽만 글자 인식([쪽 N · OCR])");
    if ((r.charter_n_images || 0) > 0 && base) h += sec("스캔 이미지", thumbs(base, r.imgs, r.charter_n_images), `전체 ${fmtN(r.charter_n_images)}장`);
    if ("agm_rcept_nos" in r || "agm_count" in r) h += agmSection(r);
    return { title: r.corp_name, sub: `${r.stock_code || ""} · ${r.report_nm || ""}`, html: h };
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
      ["원문 XML", IS_PAGES ? '<span class="small">git 에 올리지 않아 이 페이지에서는 열 수 없습니다 — DART 공시에서 보세요</span>' : xp ? loc(xp, esc(xp)) : "", { wide: true }],
      IS_PAGES ? null : ["폴더", n.folder ? loc(n.folder, esc(n.folder)) : "", { wide: true }],
      n.error ? ["오류", `<span class="bad">${e(n.error)}</span>`, { wide: true }] : null,
    ]));
    h += usedBy(list(n.used_by_rcept_no));
    if (n.charter_amend_txt) h += sec("정관의변경.txt 미리보기", `<div class="pvbox" data-path="${esc(n.charter_amend_txt)}"></div>`, "Changes to articles of incorporation");
    return { title: n.corp_name, sub: `${n.stock_code || ""} · ${n.report_nm || ""} · ${ymd(n.rcept_dt)}`, html: h };
  }

  function detailDoc(d) {
    let h = sec("정관 문서", kv([
      ["회사명", `<b>${e(d.corp_name)}</b>`], ["종목코드", mono(d.stock_code)],
      ["고유번호", mono(d.corp_code)], ["첨부일", ymd(d.att_date)],
      ["첨부 제목", e(d.att_title), { wide: true }],
      ["접수번호 rcpNo", mono(d.rcpNo)], ["문서번호 dcmNo", mono(d.dcmNo)],
      ["정관 URL", d.att_url ? ext(d.att_url, esc(d.att_url), `정관 URL (${AOI})`) : "", { wide: true }],
      ["종류", ctB(d.content_type)], ["글자 수", d.text_chars == null ? "" : `${num(d.text_chars)}자`],
      ["이미지", d.n_images == null ? "" : `${num(d.n_images)}장${(d.n_image_errors || 0) > 0 ? ` <span class="bad">오류 ${fmtN(d.n_image_errors)}</span>` : ""}`], ["노드", num(d.n_nodes)],
      ["폴더", d.folder ? [loc(d.folder, esc(d.folder)), loc(`${d.folder}/charter.txt`, "charter.txt"), loc(`${d.folder}/meta.json`, "meta.json")].join(" · ") : "", { wide: true }],
      ["수집시점", e(d.fetched_at)],
    ]), AOI);
    h += usedBy(list(d.used_by_rcept_no));
    if (d.folder) h += sec("정관 본문 미리보기", `<div class="pvbox" data-path="${esc(`${d.folder}/charter.txt`)}"></div>`, "charter.txt");
    if (d.content_type === "pdf" && d.folder) {
      h += sec("PDF 원문", `<p>${pdfLinks({ charter_dir: d.folder, pdfs: d.pdfs }, false)}</p>`);
      h += sec("PDF 정관 글 미리보기", `<div class="pvbox" data-path="${esc(`${d.folder}/charter_pdf.txt`)}"></div>`, "charter_pdf.txt");
    }
    if ((d.n_images || 0) > 0 && d.folder) h += sec("스캔 이미지", thumbs(d.folder, d.imgs, d.n_images), `전체 ${fmtN(d.n_images)}장`);
    return { title: d.corp_name, sub: `${d.stock_code || ""} · ${d.att_title || "정관"}`, html: h };
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
    $$(".thumbs img", body).forEach((img) => {
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
  $("#tabs").innerHTML = TABS.map((t) => `<li><button type="button" role="tab" data-id="${t.id}" aria-controls="pane-${t.id}"${t.tip ? ` title="${esc(t.tip)}"` : ""}>${esc(t.label)}<span class="n">${T[t.table] ? fmtN(T[t.table].rows.length) : "수집 중"}</span></button></li>`).join("");
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
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));
  const goTo = (spec) => {
    const [id, preset] = spec.split(":");
    if (location.hash.slice(1) !== id) location.hash = id; else show(id);
    if (preset && S[id] && !S[id].missing) {
      reset(id);
      const el = $(`[data-f="${preset}"]`, S[id].pane);
      if (el && el.type === "checkbox") el.checked = true;
      apply(id);
    }
    $("#tabs").scrollIntoView({ block: "start", behavior: "smooth" });
  };
  $("#summary").addEventListener("click", (ev) => { const c = ev.target.closest("[data-go]"); if (c) goTo(c.dataset.go); });
  $("#summary").addEventListener("keydown", (ev) => { const c = ev.target.closest("[data-go]"); if (c && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); goTo(c.dataset.go); } });
  show(location.hash.slice(1) || "kospi");
})();
