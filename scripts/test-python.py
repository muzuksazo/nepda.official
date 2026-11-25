"""Run the offline regression suite, optionally filtered to one PRD area."""
import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
if not sys.flags.utf8_mode:
    raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv]))

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("area", nargs="?")
args = parser.parse_args()
start = ROOT / "tests"
if args.area:
    candidate = (start / args.area).resolve()
    if not candidate.is_relative_to(start) or not candidate.is_dir():
        parser.error("Choose a directory inside tests/")
    start = candidate
suite = unittest.defaultTestLoader.discover(str(start), pattern="test_*.py", top_level_dir=str(ROOT))
if suite.countTestCases() == 0:
    parser.error("This PRD area has no executable Python tests yet; see tests/README.md")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
