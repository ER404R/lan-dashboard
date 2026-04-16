"""Focused tests for Issue #15: Harden CI gates — static analysis + GitHub Actions on every PR.

Verifies:
1. pyproject.toml exists with correct ruff config (select = ["F", "E9"], target py312).
2. ruff is declared in requirements-dev.txt.
3. tests/test_imports.py smoke test exists and is properly structured.
4. .github/workflows/ci.yml exists with `lint` and `test` jobs.
5. README has "CI & Quality Gates" section.
6. `ruff check .` passes cleanly on the current codebase.
7. The import smoke test catches a re-introduction of the admin.py F821 bug class.
"""
from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. pyproject.toml
# ---------------------------------------------------------------------------


def test_pyproject_toml_exists():
    assert (REPO_ROOT / "pyproject.toml").is_file(), "pyproject.toml missing at repo root"


def test_pyproject_ruff_config():
    content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ruff]" in content, "Missing [tool.ruff] table"
    assert "[tool.ruff.lint]" in content, "Missing [tool.ruff.lint] table"
    assert 'target-version = "py312"' in content, "target-version not set to py312"
    # select must include F and E9 (pyflakes + syntax-error classes)
    assert '"F"' in content and '"E9"' in content, "Ruff select must include F and E9"


def test_pyproject_scopes_include_app_and_tests():
    content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "app/" in content, "ruff include should reference app/"
    assert "tests/" in content, "ruff include should reference tests/"


# ---------------------------------------------------------------------------
# 2. requirements-dev.txt
# ---------------------------------------------------------------------------


def test_ruff_in_requirements_dev():
    content = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert any(line.startswith("ruff") for line in lines), (
        f"ruff not found in requirements-dev.txt, got: {lines}"
    )


# ---------------------------------------------------------------------------
# 3. tests/test_imports.py smoke test
# ---------------------------------------------------------------------------


def test_import_smoke_test_file_exists():
    assert (REPO_ROOT / "tests" / "test_imports.py").is_file()


def test_import_smoke_test_uses_walk_packages():
    content = (REPO_ROOT / "tests" / "test_imports.py").read_text(encoding="utf-8")
    assert "pkgutil.walk_packages" in content, (
        "Smoke test should use pkgutil.walk_packages to discover modules"
    )
    assert "import_module" in content, "Smoke test should use importlib.import_module"


def test_import_smoke_test_collects_all_failures():
    """The test should accumulate failures, not stop on first error."""
    content = (REPO_ROOT / "tests" / "test_imports.py").read_text(encoding="utf-8")
    # Look for accumulation pattern: list + append
    assert "failures" in content and "append" in content, (
        "Smoke test should collect all failures into a list before asserting"
    )


def test_import_smoke_test_actually_imports_all_modules():
    """Re-run the smoke test's core logic here to be sure every app module loads."""
    import app

    failures: list[str] = []
    for module_info in pkgutil.walk_packages(app.__path__, prefix="app."):
        try:
            importlib.import_module(module_info.name)
        except Exception as exc:  # noqa: BLE001 — we want every failure class
            failures.append(f"{module_info.name}: {type(exc).__name__}: {exc}")

    assert not failures, "Modules failing to import:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 4. .github/workflows/ci.yml
# ---------------------------------------------------------------------------


CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_exists():
    assert CI_YML.is_file(), ".github/workflows/ci.yml missing"


def test_ci_workflow_triggers_on_pr_and_push_main():
    content = CI_YML.read_text(encoding="utf-8")
    assert "pull_request" in content, "CI must trigger on pull_request"
    assert "push" in content, "CI must trigger on push (to main)"
    assert "main" in content, "CI must target main branch"


def test_ci_workflow_has_lint_and_test_jobs():
    content = CI_YML.read_text(encoding="utf-8")
    # Job ids expected by the plan's branch-protection instructions
    assert "\n  lint:" in content or content.startswith("lint:"), "CI must define a `lint` job"
    assert "\n  test:" in content or "\ntest:" in content, "CI must define a `test` job"


def test_ci_workflow_runs_ruff_and_pytest():
    content = CI_YML.read_text(encoding="utf-8")
    assert "ruff check" in content, "Lint job must run `ruff check`"
    assert "pytest" in content, "Test job must run pytest"


def test_ci_workflow_uses_python_312():
    content = CI_YML.read_text(encoding="utf-8")
    assert "3.12" in content, "CI workflow must pin Python 3.12"


def test_ci_workflow_sets_test_env_vars():
    """Test job needs SECRET_KEY/DATABASE_URL etc. so tests can start the app."""
    content = CI_YML.read_text(encoding="utf-8")
    for var in ("SECRET_KEY", "DATABASE_URL", "ADMIN_INVITE_TOKEN"):
        assert var in content, f"CI test job must set {var} in env"


# ---------------------------------------------------------------------------
# 5. README documentation
# ---------------------------------------------------------------------------


def test_readme_has_ci_section():
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "CI" in content and "Quality Gate" in content, (
        "README must document the CI & Quality Gates section"
    )
    assert "ruff check" in content, "README should show how to run ruff locally"
    assert "pytest" in content, "README should show how to run pytest locally"


# ---------------------------------------------------------------------------
# 6. End-to-end: ruff actually passes on the codebase
# ---------------------------------------------------------------------------


def test_ruff_check_passes_on_codebase():
    """Run `ruff check .` and require a clean pass."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        pytest.skip("ruff not available in this environment")
    assert result.returncode == 0, (
        f"`ruff check .` failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# 7. Verification: re-introducing the original bug is caught
# ---------------------------------------------------------------------------


def test_ruff_catches_undefined_name_f821(tmp_path: Path):
    """Simulate the admin.py bug class: a route uses a name that was never imported.

    Ruff with select = ['F'] should flag this as F821.
    """
    bad = tmp_path / "bad_module.py"
    bad.write_text(
        "def handler():\n"
        "    return require_admin()  # never imported\n",
        encoding="utf-8",
    )
    # Use the project's ruff config by pointing --config at pyproject.toml's rules.
    # We pass --select F so the test is independent of the project config location.
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F", str(bad)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        "Ruff should have flagged the undefined name `require_admin`"
    )
    assert "F821" in result.stdout + result.stderr, (
        f"Expected F821 in ruff output, got:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
