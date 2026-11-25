"""The existing public Python API uses the grouped prototype implementation."""
import importlib
import unittest


class TestVercelEntrypoints(unittest.TestCase):
    def test_python_compatibility_entrypoint_uses_the_original_handler(self):
        entry = importlib.import_module("api.copy")
        prototype = importlib.import_module("prototypes.hookcut.api.copy")
        self.assertIs(entry.handler, prototype.handler)
