"""Shared paths and platform setup for offline PRD tests."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "backend", ROOT / "libraries" / "media-tools"):
    sys.path.insert(0, str(directory))
if os.name == "nt":
    for variable, filename in (("SHORTFORM_FONT_BOLD", "malgunbd.ttf"),
                               ("SHORTFORM_FONT_REGULAR", "malgun.ttf")):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if font.exists():
            os.environ.setdefault(variable, str(font))

# 테스트는 개발자 backend/.env 의 실제 저장소(R2 등)를 절대 건드리지 않는다 (환경변수가 .env 보다 우선한다).
# 2026-11-27: .env 를 r2 로 바꾼 뒤 일부 테스트가 결과 파일을 실제 버킷에 올린 일이 있었다.
os.environ["STORAGE_BACKEND"] = "local"
