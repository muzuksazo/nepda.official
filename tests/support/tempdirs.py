"""Release cyclic sqlite handles before temporary folders close on Windows."""
import gc
import tempfile
from contextlib import contextmanager

@contextmanager
def temporary_directory():
    with tempfile.TemporaryDirectory() as directory:
        try:
            yield directory
        finally:
            gc.collect()
