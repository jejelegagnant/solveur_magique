"""Architectural boundary and zero-coupling verification tests for solver_core (NFR-020)."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
SOLVER_CORE_DIR = BACKEND_DIR / "solver_core"
SCHEMAS_DIR = SOLVER_CORE_DIR / "schemas"


def _resolve_lint_imports_bin() -> Path:
    candidate = Path(sys.executable).parent / "lint-imports"
    if candidate.exists():
        return candidate
    found = shutil.which("lint-imports")
    assert found is not None, f"lint-imports binary not found at {candidate} or on PATH"
    return Path(found)


FORBIDDEN_TOP_LEVEL_MODULES: frozenset[str] = frozenset(
    {
        "app",
        "fastapi",
        "starlette",
        "sqlalchemy",
        "alembic",
        "psycopg",
        "redis",
        "dramatiq",
        "celery",
        "uvicorn",
        "gunicorn",
        "httpx",
        "requests",
        "stripe",
    }
)


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.architecture
def test_ast_zero_forbidden_imports_in_solver_core() -> None:
    """Every module under solver_core/ has zero web, ORM, queue, or app framework imports."""
    py_files = _iter_python_files(SOLVER_CORE_DIR)
    assert py_files, f"Expected Python modules under {SOLVER_CORE_DIR}"

    violations: list[str] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(BACKEND_DIR)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".", maxsplit=1)[0]
                    if top in FORBIDDEN_TOP_LEVEL_MODULES:
                        violations.append(f"{rel}:{node.lineno} imports forbidden '{alias.name}'")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
                top = node.module.split(".", maxsplit=1)[0]
                if top in FORBIDDEN_TOP_LEVEL_MODULES:
                    violations.append(f"{rel}:{node.lineno} imports from forbidden '{node.module}'")

    assert not violations, "Forbidden imports detected in solver_core:\n" + "\n".join(violations)


@pytest.mark.architecture
def test_ast_schemas_never_import_time_utils() -> None:
    """solver_core/schemas/ must remain independent of solver_core.time_utils."""
    schema_files = _iter_python_files(SCHEMAS_DIR)
    assert schema_files, f"Expected schema modules under {SCHEMAS_DIR}"

    violations: list[str] = []
    for path in schema_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(BACKEND_DIR)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "solver_core.time_utils" or alias.name.startswith(
                        "solver_core.time_utils."
                    ):
                        violations.append(f"{rel}:{node.lineno} imports '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "solver_core.time_utils" or mod.startswith("solver_core.time_utils."):
                    violations.append(f"{rel}:{node.lineno} imports from '{mod}'")
                elif mod == "solver_core" and any(
                    alias.name == "time_utils" for alias in node.names
                ):
                    violations.append(f"{rel}:{node.lineno} imports 'time_utils' from solver_core")
                elif node.level >= 2 and (
                    mod == "time_utils"
                    or mod.startswith("time_utils.")
                    or any(alias.name == "time_utils" for alias in node.names)
                ):
                    violations.append(
                        f"{rel}:{node.lineno} relatively imports 'time_utils' (level={node.level})"
                    )

    assert not violations, "Schema layer must not import time_utils:\n" + "\n".join(violations)


@pytest.mark.architecture
def test_import_linter_cli_contract_passes() -> None:
    """import-linter confirms the solver_core forbidden-imports contract is kept."""
    lint_imports_bin = _resolve_lint_imports_bin()
    result = subprocess.run(
        [str(lint_imports_bin)],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"lint-imports failed:\n{combined_output}"
    assert "1 kept, 0 broken" in combined_output, (
        f"Expected '1 kept, 0 broken' in lint-imports output:\n{combined_output}"
    )


@pytest.mark.architecture
def test_import_linter_detects_forbidden_fastapi_import_in_isolated_package(
    tmp_path: Path,
) -> None:
    """Negative test proving import-linter fails when solver_core imports fastapi."""
    pkg_dir = tmp_path / "solver_core"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "bad_coupling.py").write_text("import fastapi\n", encoding="utf-8")

    # Minimal stub package so grimp resolves `fastapi` without requiring it in the venv.
    fastapi_stub = tmp_path / "fastapi"
    fastapi_stub.mkdir()
    (fastapi_stub / "__init__.py").write_text("", encoding="utf-8")

    (tmp_path / "pyproject.toml").write_text(
        """
[tool.importlinter]
root_package = "solver_core"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "solver_core must not import fastapi"
type = "forbidden"
source_modules = ["solver_core"]
forbidden_modules = ["fastapi"]
""".lstrip(),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)

    lint_imports_bin = _resolve_lint_imports_bin()
    result = subprocess.run(
        [str(lint_imports_bin)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, (
        f"Expected lint-imports to fail on forbidden fastapi import:\n{combined_output}"
    )
    assert "0 kept, 1 broken" in combined_output, (
        f"Expected '0 kept, 1 broken' in lint-imports output:\n{combined_output}"
    )
    assert "fastapi" in combined_output
