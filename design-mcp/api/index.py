"""Vercel 이 실행하는 입구 파일 — design_server.py 의 원격(HTTP) 앱을 그대로 내보내요."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # design_server.py 가 있는 폴더

from design_server import http_app  # noqa: E402

app = http_app()
