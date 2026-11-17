"""공용 — 경로·기준일·키·HTTP(간격·재시도·캐시)·DART 화면 파서.

기준일(AS_OF)을 고정해 두어야 같은 결과가 다시 나온다.
"최종보고서" 여부와 DART 화면의 본문·첨부 목록은 그 뒤 정정 공시가 나오면 바뀌기 때문이다.
바꾸려면 환경변수 KC_AS_OF=YYYY-MM-DD 를 주고 data/raw 캐시를 지운 뒤 처음부터 다시 돌린다.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# IPv4 로만 접속한다. 이 PC 망은 IPv6 를 NAT64(64:ff9b::…)로 내보내는데, 2026-11-16 DART 웹이 그 NAT64 쪽 주소만
# 막고 직접 IPv4 경로는 열려 있었다(curl -6 → 연결 끊김, curl -4 → 200). 파이썬은 기본으로 IPv6 를 먼저 쓴다.
import socket as _socket  # noqa: E402
import urllib3.util.connection as _u3conn  # noqa: E402

_u3conn.allowed_gai_family = lambda: _socket.AF_INET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
FINAL = ROOT / "data" / "final"
CHARTER = ROOT / "data" / "charter"
LOGS = ROOT / "logs"

# ── 기준일과 조회기간 ────────────────────────────────────────────────────────
AS_OF = date.fromisoformat(os.environ.get("KC_AS_OF", "2026-11-16"))
BGN = AS_OF - timedelta(days=365)          # 최근 1년: 2025-11-16 ~ 2026-11-16 (양끝 포함)

DART_WEB = "https://dart.fss.or.kr"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


# ── .env ────────────────────────────────────────────────────────────────────
def load_env() -> dict[str, str]:
    env = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k, v in os.environ.items():          # 환경변수가 .env 보다 우선 (Colab 등)
        if k.startswith("DART_API_KEY") and v:
            env[k] = v
    return env


def dart_keys() -> list[str]:
    env = load_env()
    keys = [v for k, v in sorted(env.items()) if k.startswith("DART_API_KEY") and v]
    keys = list(dict.fromkeys(keys))
    if not keys:
        raise SystemExit("DART_API_KEY 가 없습니다 — .env.example 을 .env 로 복사해 키를 넣으세요.")
    return keys


# ── HTTP ────────────────────────────────────────────────────────────────────
class Http:
    """호스트 하나에 순차로, 최소 간격을 두고 부른다.

    DART 웹·OpenDART 는 IP 단위로 막는다. 연속 실패가 이어지면 차단으로 보고 오래 쉰다.

    **DART 웹(dart.fss.or.kr)은 IP 당 1분에 100건이 한도다** (사용자 확인 2026-11-16 — 화면 1초 + 이미지 0.5초를
    인스턴스마다 따로 세다가 분당 ~180건이 되어 막혔다). 그래서 간격·분당 건수를 **인스턴스가 아니라 호스트 단위로**
    한 프로세스 안에서 함께 센다. 재시도도 한 건으로 센다. 다른 프로세스와 동시에 돌리면 이 장치로도 못 막는다.
    """

    # DART 웹 한도 100 → 여유 두고 80. OpenDART 는 같은 금감원 망(61.73.60.x)이라 한도를 함께 쓰는 것으로 보고 같이 묶는다
    PER_MIN = {"dart.fss.or.kr": 80, "opendart.fss.or.kr": 80}
    _hosts: dict[str, dict] = {}               # 호스트 → {"last": 마지막 요청 시각, "q": 최근 60초 요청 시각들}

    def __init__(self, delay: float = 1.0, timeout: int = 40, tries: int = 4, referer: str | None = None):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        if referer:
            self.s.headers["Referer"] = referer
        self.delay, self.timeout, self.tries = delay, timeout, tries
        self.consec_fail = 0

    def _wait(self, url: str):
        from collections import deque
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        st = Http._hosts.setdefault(host, {"last": 0.0, "q": deque()})
        d = self.delay - (time.time() - st["last"])
        if d > 0:
            time.sleep(d)
        cap = self.PER_MIN.get(host)
        if cap:
            q = st["q"]
            while True:
                now = time.time()
                while q and now - q[0] >= 60:
                    q.popleft()
                if len(q) < cap:
                    break
                time.sleep(60 - (now - q[0]) + 0.2)
            q.append(time.time())
        st["last"] = time.time()

    def get(self, url: str, **kw) -> requests.Response:
        err = None
        for i in range(self.tries):
            self._wait(url)
            try:
                r = self.s.get(url, timeout=self.timeout, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                self.consec_fail = 0
                return r
            except Exception as e:          # noqa: BLE001 — 네트워크 오류는 모두 재시도
                err = e
                time.sleep(3 * (2 ** i))
        self.consec_fail += 1
        if self.consec_fail >= 5:
            print(f"  연속 실패 {self.consec_fail}건 — 차단으로 보고 600초 쉰다", flush=True)
            time.sleep(600)
            self.consec_fail = 0
        raise RuntimeError(f"GET 실패 {url}: {err}")


def cached_text(path: Path, fetch) -> str:
    """path 가 있으면 읽고, 없으면 fetch() 결과를 저장한다 (원본 응답 캐시)."""
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(encoding="utf-8")
    text = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── 보고서명 해석 ─────────────────────────────────────────────────────────────
_PREFIX = re.compile(r"^((?:\[[^\]]*\])*)")
_PERIOD = re.compile(r"\((\d{4})\.(\d{2})\)\s*$")


def parse_report_nm(nm: str) -> dict:
    """'[첨부정정]사업보고서 (2025.12)' → 접두어·본문 서식명·기준연월.

    사업연도(fiscal_year)는 기준연월의 연도다. OpenDART 정기보고서 API 의 bsns_year 와 같다
    (9월 결산 '(2025.09)' → bsns_year=2025, 3월 결산 '(2026.03)' → 2026 확인, docs/03-검증기록.md).
    """
    nm = (nm or "").strip()
    prefix = _PREFIX.match(nm).group(1)
    body = nm[len(prefix):].strip()
    m = _PERIOD.search(body)
    out = {"amend_tag": prefix, "form_nm": _PERIOD.sub("", body).strip(),
           "report_period": None, "fiscal_year": None, "settle_month": None}
    if m:
        out.update(report_period=f"{m[1]}.{m[2]}", fiscal_year=int(m[1]), settle_month=int(m[2]))
    return out


# ── DART 화면(main.do) 파서 — OpenDartReader 와 같은 규칙 ────────────────────
def main_url(rcp_no: str) -> str:
    return f"{DART_WEB}/dsaf001/main.do?rcpNo={rcp_no}"


def select_options(html: str, sel_id: str) -> list[tuple[str, str]]:
    """<select id=sel_id> 의 (value, 제목). 'null' 옵션은 뺀다.

    id='att'    → OpenDartReader.attach_docs() 와 같은 목록 (첨부문서)
    id='family' → 같은 보고서의 본문 버전들(최신이 맨 위). 사용자 기존 프로젝트의 get_recent() 가 쓰는 목록
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, features="lxml")
    sel = soup.find(id=sel_id)
    if not sel:
        return []
    out = []
    for opt in sel.find_all("option"):
        v = opt.get("value", "null")
        if v == "null":
            continue
        out.append((v, " ".join(opt.text.split())))
    return out


def attach_docs_from_html(html: str) -> list[dict]:
    """OpenDartReader.dart_utils.attach_docs(rcp_no) 와 같은 (title, url) 목록.

    attach_docs 는 http://dart.fss.or.kr/dsaf001/main.do?{value} 를 만든다. 여기서는 https 로만 바꾼다.
    """
    rows = []
    for v, title in select_options(html, "att"):
        q = dict(p.split("=", 1) for p in v.split("&") if "=" in p)
        rows.append({"title": title, "url": f"{DART_WEB}/dsaf001/main.do?{v}",
                     "rcpNo": q.get("rcpNo"), "dcmNo": q.get("dcmNo")})
    return rows


_NODE = re.compile(
    r"node[12]\['text'\]\s*=\s*\"(.*?)\";\s*"
    r"node[12]\['id'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['rcpNo'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['dcmNo'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['eleId'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['offset'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['length'\]\s*=\s*\"(\d+)\";\s*"
    r"node[12]\['dtd'\]\s*=\s*\"(.*?)\";\s*"
    r"node[12]\['tocNo'\]\s*=\s*\"(\d+)\";", re.S)
_VIEWDOC = re.compile(r"viewDoc\(\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\S+?)'")


def sub_docs_from_html(html: str) -> list[dict]:
    """OpenDartReader.sub_docs() 와 같은 규칙으로 viewer.do 주소를 만든다 (목차 노드 → 없으면 viewDoc)."""
    rows = []
    for m in _NODE.findall(html):
        rows.append({"title": " ".join(m[0].split()), "rcpNo": m[2], "dcmNo": m[3], "eleId": m[4],
                     "offset": m[5], "length": m[6], "dtd": m[7]})
    if not rows:
        for m in _VIEWDOC.findall(html)[:1]:
            rows.append({"title": "", "rcpNo": m[0], "dcmNo": m[1], "eleId": m[2],
                         "offset": m[3], "length": m[4], "dtd": m[5]})
    for r in rows:
        r["url"] = (f"{DART_WEB}/report/viewer.do?rcpNo={r['rcpNo']}&dcmNo={r['dcmNo']}&eleId={r['eleId']}"
                    f"&offset={r['offset']}&length={r['length']}&dtd={r['dtd']}")
    return rows


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(s: str) -> str:
    return _BAD.sub("_", (s or "").strip()).rstrip(". ") or "_"


def stamp_site_assets(site_dir: Path | None = None) -> dict:
    """site/index.html 의 data.js · dividend.js · app.js · style.css 주소에 내용 해시(?v=8자리)를 붙인다.
    GitHub Pages 는 파일을 10분 캐시하고 브라우저는 더 오래 들고 있기도 해서, 고친 파일이 바로 안 보이는 일을 막는다.
    s08(data.js)·s10(dividend.js) 이 파일을 쓴 뒤 부른다. app.js·style.css 를 고친 뒤에는 둘 중 하나를 다시 돌리거나 이 함수를 부른다."""
    import hashlib
    import re as _re
    site = site_dir or ROOT / "site"
    idx = site / "index.html"
    html = idx.read_text(encoding="utf-8")
    vers = {}
    for name in ("style.css", "data.js", "dividend.js", "app.js"):
        f = site / name
        if not f.exists():
            continue
        v = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
        vers[name] = v
        html = _re.sub(r'((?:src|href)=")' + _re.escape(name) + r'(?:\?v=[0-9a-f]*)?(")', rf"\g<1>{name}?v={v}\g<2>", html)
    if html != idx.read_text(encoding="utf-8"):
        idx.write_text(html, encoding="utf-8")
    return vers
