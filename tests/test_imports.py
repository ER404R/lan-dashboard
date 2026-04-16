"""Smoke test: verify every module under app/ can be imported.

This catches undefined-name errors, missing imports, and syntax errors
at test-collection time — the cheapest possible correctness floor.
"""
import importlib
import pkgutil

import app


def test_all_app_modules_importable():
    """Walk every sub-module/package under app/ and import it.

    Any ImportError, NameError, or SyntaxError will cause this test
    to fail with a clear traceback pointing at the broken module.
    """
    failures = []
    for module_info in pkgutil.walk_packages(app.__path__, prefix="app."):
        try:
            importlib.import_module(module_info.name)
        except Exception as exc:
            failures.append(f"{module_info.name}: {type(exc).__name__}: {exc}")

    if failures:
        raise AssertionError(
            "The following modules failed to import:\n" + "\n".join(failures)
        )
