"""Shared paths and platform setup for offline PRD tests."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "apps" / "backend", ROOT / "libraries" / "media-tools"):
    sys.path.insert(0, str(directory))
if os.name == "nt":
    for variable, filename in (("SHORTFORM_FONT_BOLD", "malgunbd.ttf"),
                               ("SHORTFORM_FONT_REGULAR", "malgun.ttf")):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if font.exists():
            os.environ.setdefault(variable, str(font))
