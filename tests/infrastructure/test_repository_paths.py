"""Verify backend/tool lookup after moving the deployable application."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


class TestRepositoryPaths(unittest.TestCase):
    def test_backend_resolves_media_tools_outside_its_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as elsewhere:
            try:
                os.chdir(elsewhere)
                with patch.dict(os.environ, {}, clear=True):
                    settings = Settings(_env_file=None)
                tools = settings.resolved_scripts_dir
                self.assertEqual(tools, ROOT / "libraries" / "media-tools")
                self.assertTrue((tools / "ad_remix_assemble.py").is_file())
                self.assertTrue((tools / "ad_gate_a_lint.py").is_file())
            finally:
                os.chdir(previous)

    def test_container_can_override_the_media_tools_location(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SCRIPTS_DIR": directory}):
                settings = Settings(_env_file=None)
            self.assertEqual(settings.resolved_scripts_dir, Path(directory).resolve())
