"""Compatibility entry point for the existing Vercel /api/copy URL."""
from prototypes.hookcut.api.copy import handler

__all__ = ["handler"]
