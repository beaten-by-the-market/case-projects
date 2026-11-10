"""MySQL dart_periodic 접속. 접속값은 low-pbr/.env 의 MYSQL_*."""
import sys
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).parent))
from _gw import ENV  # noqa: E402


def get_conn(database: str | None = None, dict_cursor: bool = False):
    return pymysql.connect(
        host=ENV.get("MYSQL_HOST", "localhost"),
        port=int(ENV.get("MYSQL_PORT", "3306")),
        user=ENV["MYSQL_USER"],
        password=ENV["MYSQL_PASSWORD"],
        database=database if database is not None else ENV.get("MYSQL_DATABASE", "dart_periodic"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor,
        read_timeout=600,
        autocommit=False,
    )


def dart_keys() -> list[str]:
    keys = [v for k, v in sorted(ENV.items()) if k.startswith("DART_API_KEY") and v]
    return list(dict.fromkeys(keys))
