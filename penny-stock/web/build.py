"""템플릿(dashboard.html) + 데이터(dashboard_data.json) → 배포본(dashboard_final.html).

dashboard.html 안의 `__DATA__` 자리표시자를 data/dashboard_data.json 내용으로
치환한다. 배포본은 외부 의존성 없는 단일 HTML(모든 데이터 embed).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tpl = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
data = (ROOT / "data" / "dashboard_data.json").read_text(encoding="utf-8")

if "__DATA__" not in tpl:
    raise SystemExit("web/dashboard.html에 __DATA__ 자리표시자가 없습니다.")

out = tpl.replace("__DATA__", data)
dest = ROOT / "web" / "dashboard_final.html"
dest.write_text(out, encoding="utf-8")
print(f"빌드 완료: {dest}  ({len(out):,} bytes)")