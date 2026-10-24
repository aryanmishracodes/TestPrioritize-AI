"""
tests/test_app.py
Unit tests verifying that app.py imports properly, exposes its expected
dashboard constants and components, and operates safely.
"""

import sys
import pytest


def test_app_imports_cleanly():
    """Verifies that app.py can be imported as a Python module without syntax or runtime import errors."""
    import app
    assert hasattr(app, "run_pipeline")
    assert hasattr(app, "get_api_key")
    assert hasattr(app, "FileChange")
    assert hasattr(app, "RankedItem")


def test_app_constants_match_engine():
    """Ensures scoring labels and constants used in app.py match ranking_engine."""
    import app
    from ranking_engine import PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW

    assert app.PRIORITY_HIGH == PRIORITY_HIGH
    assert app.PRIORITY_MEDIUM == PRIORITY_MEDIUM
    assert app.PRIORITY_LOW == PRIORITY_LOW
