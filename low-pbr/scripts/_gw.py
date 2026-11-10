"""CHECK API 게이트웨이(원격 PC 공개버전) 클라이언트.

    from _gw import call, rows
    rows(call('/stock/m001/hist_info', jcode='005930', sdate='20261001', edate='20261022'))

- POST {CHECK_GW_URL}/v1/check{path}, 헤더 X-API-Key, 본문 JSON.
- TLS: 기본은 .secrets 의 루트 CA로 검증. 서버 leaf 가 만료돼 있으면(Caddy 갱신 중단)
  CHECK_GW_FP(루트 CA로 체인 검증을 마친 leaf 지문)를 고정해 지문만 대조한다.
- 응답은 data/raw/gw/ 에 (path+params) 해시로 캐시한다. 같은 요청은 다시 보내지 않는다.
- success:false 는 빈 결과가 아니라 예외로 올린다(한도 초과·rate limit 이 HTTP 200 으로 온다).
- 시계열 조회는 초당 1회 제한 → 호출 간 MIN_GAP 초를 둔다.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "gw"
MIN_GAP = 1.15
_last = 0.0


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()


class _PinnedAdapter(HTTPAdapter):
    """leaf 인증서 SHA-256 지문을 대조한다(만료 여부 무시, 지문이 다르면 연결 거부)."""

    def __init__(self, fp: str, **kw):
        self._fp = fp.replace(":", "").lower()
        super().__init__(**kw)

    def init_poolmanager(self, *a, **kw):
        kw["assert_fingerprint"] = self._fp
        kw["cert_reqs"] = "CERT_NONE"
        return super().init_poolmanager(*a, **kw)


def _session() -> tuple[requests.Session, object]:
    s = requests.Session()
    if ENV.get("CHECK_GW_FP"):
        s.mount(ENV["CHECK_GW_URL"], _PinnedAdapter(ENV["CHECK_GW_FP"]))
        return s, False
    return s, str(ROOT / ENV["CHECK_GW_CA"])


_S, _VERIFY = _session()
if _VERIFY is False:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GatewayError(RuntimeError):
    pass


def _key(path: str, params: dict) -> str:
    blob = json.dumps([path, params], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode()).hexdigest()


class NotCached(LookupError):
    pass


def call(path: str, *, use_cache: bool = True, offline: bool = False, retries: int = 4, **params) -> dict:
    """offline=True 면 캐시에 있는 응답만 돌려주고, 없으면 NotCached (네트워크를 쓰지 않는다)."""
    global _last
    params = {k: str(v) for k, v in params.items()}
    f = CACHE / path.strip("/").replace("/", "_") / f"{_key(path, params)}.json"
    if use_cache and f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if offline:
        raise NotCached(path)
    for attempt in range(retries):
        gap = MIN_GAP - (time.time() - _last)
        if gap > 0:
            time.sleep(gap)
        _last = time.time()
        try:
            r = _S.post(
                ENV["CHECK_GW_URL"] + "/v1/check" + path,
                headers={"X-API-Key": ENV["CHECK_GW_KEY"]},
                json=params,
                verify=_VERIFY,
                timeout=120,
            )
        except requests.RequestException as e:
            # 네트워크 전환·일시 단절(실측 2026-11-10 WinError 10065)은 몇 분이면 돌아온다.
            # 연결 오류는 재시도 횟수와 별도로 10초→5분까지 늘려 가며 최대 약 15분 기다린다.
            for wait in (10, 30, 60, 120, 300, 300):
                time.sleep(wait)
                try:
                    _S.get(ENV["CHECK_GW_URL"] + "/healthz", verify=_VERIFY, timeout=15)
                    break
                except requests.RequestException:
                    continue
            else:
                raise
            if attempt == retries - 1:
                raise
            continue
        if r.status_code == 429:
            # 게이트웨이 호출 속도 제한(실측 2026-11-10 19:18, Retry-After 없음 · 곧 풀림).
            # 재시도 횟수와 별도로 1분→15분까지 늘려 가며 기다린다. 기다린 시간은 logs 로 남긴다.
            for wait in (60, 120, 300, 600, 900, 900, 900):
                print(f"    [429] {wait}초 대기", flush=True)
                time.sleep(int(r.headers.get("Retry-After") or wait))
                _last = time.time()
                r = _S.post(ENV["CHECK_GW_URL"] + "/v1/check" + path, headers={"X-API-Key": ENV["CHECK_GW_KEY"]},
                            json=params, verify=_VERIFY, timeout=120)
                if r.status_code != 429:
                    break
        if r.status_code >= 500 and attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("success") is False:
            msg = str(data.get("message") or data)
            if "1초" in msg and attempt < retries - 1:
                time.sleep(2)
                continue
            raise GatewayError(f"{path} {params} → {msg}")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    raise GatewayError(f"{path} {params} → 재시도 소진")


def rows(data: dict) -> list[dict]:
    r = data.get("results", data) if isinstance(data, dict) else data
    return r if isinstance(r, list) else [r]
