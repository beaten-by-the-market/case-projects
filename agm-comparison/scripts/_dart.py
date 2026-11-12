"""OpenDART 공용 — 키(.env 의 DART_API_KEY*), 호출 간격, 재시도.

OpenDART·DART 웹은 IP 단위로 차단한다 — 다른 수집과 동시에 돌리지 말 것.
"""
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Mozilla/5.0"}
DELAY = 0.7


def _env() -> dict:
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


ENV = _env()


def dart_keys() -> list[str]:
    keys = [v for k, v in sorted(ENV.items()) if k.startswith("DART_API_KEY") and v]
    return list(dict.fromkeys(keys))


class Keys:
    """한도 초과(020) 시 다음 키로."""
    def __init__(self):
        self.keys, self.i = dart_keys(), 0
        if not self.keys:
            raise SystemExit(".env 에 DART_API_KEY 가 없다")

    @property
    def cur(self):
        return self.keys[self.i]

    def rotate(self):
        self.i += 1
        if self.i >= len(self.keys):
            raise SystemExit("모든 DART 키 한도 초과(020)")


_last = [0.0]


def gap():
    d = DELAY - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    _last[0] = time.time()


class Net:
    sess = requests.Session()

    @classmethod
    def get(cls, url, **kw):
        kw.setdefault("headers", UA)
        for wait in (5, 20, 60, None):
            gap()
            try:
                r = cls.sess.get(url, **kw)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
                if wait is None:
                    raise
                cls.sess.close()
                cls.sess = requests.Session()
                time.sleep(wait)
