"""実際のImport Linterで許可経路と禁止経路を確認する。"""

import ast
import fnmatch
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _run_contract(
    tmp_path: Path,
    contract_id: str,
    source: str,
    target: str,
    *,
    source_import: str | None = None,
    support_modules: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contract = next(
        item
        for item in config["tool"]["importlinter"]["contracts"]
        if item["id"] == contract_id
    )
    modules = {
        source,
        target,
        "app",
        "app.domain",
        "app.application",
        "app.infrastructure",
        "app.presentational",
    }
    modules.update(support_modules or {})
    for key in ("source_modules", "forbidden_modules", "modules"):
        modules.update(name for name in contract.get(key, []) if "*" not in name)
    packages = {
        "app",
        "app.domain",
        "app.application",
        "app.infrastructure",
        "app.presentational",
    }
    for module in modules:
        parts = module.split(".")
        packages.update(".".join(parts[:index]) for index in range(1, len(parts)))
    for package in sorted(packages):
        directory = tmp_path.joinpath(*package.split("."))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").touch()
    for module in modules - packages:
        tmp_path.joinpath(*module.split(".")).with_suffix(".py").touch()
    for module, text in (support_modules or {}).items():
        tmp_path.joinpath(*module.split(".")).with_suffix(".py").write_text(
            text, encoding="utf-8"
        )
    tmp_path.joinpath(*source.split(".")).with_suffix(".py").write_text(
        source_import or f"import {target}\n", encoding="utf-8"
    )
    lines = [
        "[tool.importlinter]",
        'root_package = "app"',
        "include_external_packages = true",
        "[[tool.importlinter.contracts]]",
    ]
    for key, value in contract.items():
        lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    (tmp_path / "pyproject.toml").write_text("\n".join(lines), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--no-cache",
            "--no-logo",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize(
    ("contract_id", "source", "target"),
    [
        ("domain-layers", "app.domain.example", "app.application.example"),
        ("domain-layers", "app.domain.example", "fastapi"),
        ("domain-layers", "app.domain.example", "sqlalchemy"),
        ("application-layers", "app.application.example", "app.infrastructure.example"),
        ("application-layers", "app.application.example", "fastapi"),
        ("application-layers", "app.application.example", "sqlalchemy"),
        ("presentation-domain", "app.presentational.example", "app.domain.example"),
        ("presentation-infrastructure", "app.presentational.example", "app.bootstrap"),
        ("presentation-infrastructure", "app.presentational.example", "sqlalchemy"),
        (
            "domain-primitives",
            "app.domain.example.primitives",
            "app.domain.example.value_objects",
        ),
        (
            "domain-values",
            "app.domain.example.value_objects",
            "app.domain.example.entities",
        ),
        (
            "domain-entities",
            "app.domain.example.entities",
            "app.domain.example.repositories",
        ),
        (
            "domain-repositories",
            "app.domain.example.repositories",
            "app.domain.example.services",
        ),
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.primitives",
        ),
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.entities",
        ),
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.value_objects",
        ),
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.repositories",
        ),
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.services",
        ),
        (
            "application-contexts",
            "app.application.patient.example",
            "app.application.identity.example",
        ),
        (
            "presentation-hierarchy",
            "app.presentational.schemas",
            "app.presentational.routers.example",
        ),
        (
            "infrastructure-composition",
            "app.infrastructure.example",
            "app.infrastructure.di.example",
        ),
        (
            "persistence-external",
            "app.infrastructure.postgres.example",
            "app.infrastructure.prescription.external.example",
        ),
        (
            "payload-mapping",
            "app.infrastructure.postgres.codec",
            "app.infrastructure.patient.example",
        ),
        (
            "application-models",
            "app.application.example.commands.models",
            "app.application.patient.commands.register_patient",
        ),
        (
            "presentation-infrastructure",
            "app.presentational.example",
            "app.infrastructure.example",
        ),
        (
            "infrastructure-presentation",
            "app.infrastructure.example",
            "app.presentational.example",
        ),
    ],
)
def test_レイヤー_禁止方向の参照は_実リンターが検出する(
    tmp_path: Path, contract_id: str, source: str, target: str
) -> None:
    result = _run_contract(tmp_path, contract_id, source, target)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "BROKEN" in result.stdout
    assert source in result.stdout
    assert target in result.stdout


def test_レイヤー_ApplicationからDomainへの参照は_許可する(tmp_path: Path) -> None:
    result = _run_contract(
        tmp_path, "application-layers", "app.application.example", "app.domain.example"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "KEPT" in result.stdout


@pytest.mark.parametrize(
    ("contract_id", "source", "target"),
    [
        (
            "domain-contexts",
            "app.domain.example.entities",
            "app.domain.another.identifiers",
        ),
        (
            "domain-values",
            "app.domain.example.value_objects",
            "app.domain.example.primitives",
        ),
        (
            "domain-entities",
            "app.domain.example.entities",
            "app.domain.example.value_objects",
        ),
        (
            "domain-repositories",
            "app.domain.example.repositories",
            "app.domain.example.entities",
        ),
        (
            "domain-repositories",
            "app.domain.example.services",
            "app.domain.example.repositories",
        ),
        (
            "presentation-hierarchy",
            "app.presentational.routers.example",
            "app.presentational.dependencies",
        ),
        (
            "application-contexts",
            "app.application.staff.example",
            "app.application.store.example",
        ),
    ],
)
def test_依存境界_明示した許可方向は_規則に違反しない(
    tmp_path: Path, contract_id: str, source: str, target: str
) -> None:
    result = _run_contract(tmp_path, contract_id, source, target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "KEPT" in result.stdout


@pytest.mark.parametrize(
    "source_import",
    [
        "import app.application.example as target\n",
        "from app.application import example\n",
        "from ..application import example\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import app.application.example\n",
    ],
)
def test_依存契約_別名や相対参照でも_禁止方向を検出する(
    tmp_path: Path, source_import: str
) -> None:
    result = _run_contract(
        tmp_path,
        "domain-layers",
        "app.domain.example",
        "app.application.example",
        source_import=source_import,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "BROKEN" in result.stdout


def test_HTTP依存_Applicationを経由するDomain参照は_許可する(tmp_path: Path) -> None:
    result = _run_contract(
        tmp_path,
        "presentation-domain",
        "app.presentational.example",
        "app.domain.example",
        source_import="import app.application.bridge\n",
        support_modules={"app.application.bridge": "import app.domain.example\n"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "KEPT" in result.stdout


def test_依存契約_本番の全モジュールは_規則に違反しない() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--no-cache",
            "--no-logo",
        ],
        cwd=_ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_業務コンテキスト_追加時は_Applicationの依存契約にも登録する() -> None:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contract = next(
        item
        for item in config["tool"]["importlinter"]["contracts"]
        if item["id"] == "application-contexts"
    )
    contexts = {
        f"app.application.{p.name}"
        for p in (_ROOT / "app/domain").iterdir()
        if p.is_dir() and p.name not in {"foundation", "shared", "__pycache__"}
    }
    assert set(contract["modules"]) == contexts


def test_Domain役割モジュール_全コンテキストが_内部依存契約で検査される() -> None:
    # Arrange
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = {
        item["id"]: item for item in config["tool"]["importlinter"]["contracts"]
    }
    hierarchy = (
        (
            "domain-primitives",
            {"identifiers", "exceptions", "primitives"},
            {"value_objects", "entities", "repositories", "services"},
        ),
        ("domain-values", {"value_objects"}, {"entities", "repositories", "services"}),
        ("domain-entities", {"entities"}, {"repositories", "services"}),
        ("domain-repositories", {"repositories"}, {"services"}),
    )
    paths = [
        path
        for path in (_ROOT / "app/domain").glob("*/*.py")
        if path.parent.name not in {"foundation", "shared"}
        and path.name != "__init__.py"
    ]
    assert paths

    # Act / Assert
    for contract_id, sources, targets in hierarchy:
        contract = contracts[contract_id]
        for path in paths:
            module = ".".join(path.relative_to(_ROOT).with_suffix("").parts)
            for roles, key in (
                (sources, "source_modules"),
                (targets, "forbidden_modules"),
            ):
                if path.stem in roles:
                    assert any(
                        fnmatch.fnmatchcase(module, pattern)
                        for pattern in contract[key]
                    ), (contract_id, key, module)


def test_ユースケース_追加時は_入力と参照契約の禁止先にも登録する() -> None:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contract = next(
        item
        for item in config["tool"]["importlinter"]["contracts"]
        if item["id"] == "application-models"
    )
    for path in (_ROOT / "app/application").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(_ROOT).with_suffix("").parts)
        if any(
            isinstance(node, ast.ClassDef) and node.name.endswith("UseCase")
            for node in tree.body
        ):
            assert module in contract["forbidden_modules"], module
        if path.stem in {"reference", "inputs", "dto", "models"} or path.stem.endswith(
            ("_models", "_contracts")
        ):
            assert any(
                fnmatch.fnmatchcase(module, pattern)
                for pattern in contract["source_modules"]
            ), module
