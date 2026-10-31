"""新設コンテキストを含むDomain規則の正常例と禁止例を検証する。"""

import json
from pathlib import Path

import pytest

from tools.check_domain_architecture import check, main


def write(root: Path, files: dict[str, str]) -> None:
    domain = root / "backend/app/domain"
    domain.mkdir(parents=True, exist_ok=True)
    (domain / "__init__.py").write_text("", encoding="utf-8")
    for relative, source in files.items():
        path = domain / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "__init__.py").touch()
        path.write_text(source, encoding="utf-8")
    for directory in domain.iterdir():
        if directory.is_dir() and directory.name not in {"foundation", "shared"}:
            identifier = directory / "identifiers.py"
            if not identifier.exists():
                identifier.write_text(
                    "from app.domain.foundation.primitives.identifiers import EntityStringId\n"
                    "class RecordId(EntityStringId): pass\n",
                    encoding="utf-8",
                )


@pytest.mark.parametrize(
    "path,source,rule",
    [
        ("orders/value_objects.py", "def broken(:", "DOM000"),
        ("orders/helpers.py", "", "DOM001"),
        ("orders/nested/helper.py", "", "DOM001"),
        ("orders/__init__.py", "from .identifiers import RecordId", "DOM002"),
        (
            "orders/entities.py",
            "from app.application.chat import queries",
            "DOM003",
        ),
        ("orders/services.py", "from ..other.entities import Product", "DOM003"),
        (
            "foundation/value_objects.py",
            "from ..orders.identifiers import RecordId",
            "DOM003",
        ),
        ("shared/services.py", "from ..orders.identifiers import RecordId", "DOM003"),
        ("orders/primitives.py", "from .value_objects import Value", "DOM004"),
        ("orders/value_objects.py", "from . import entities", "DOM004"),
        ("orders/entities.py", "def f():\n    from .services import execute", "DOM004"),
        (
            "orders/identifiers.py",
            "class FirstId: pass\nclass SecondId: pass",
            "DOM005",
        ),
        ("orders/identifiers.py", "class RecordId(str): pass", "DOM005"),
        ("orders/identifiers.py", "from .primitives import Value", "DOM005"),
        (
            "orders/services.py",
            "import socket\nsocket.create_connection(('test', 443))",
            "DOM006",
        ),
        ("orders/services.py", "import subprocess as sp\nsp.run(['test'])", "DOM006"),
        ("orders/services.py", "import urllib.request", "DOM006"),
        ("orders/services.py", "from urllib import request", "DOM006"),
        ("orders/services.py", "from importlib import import_module as load", "DOM006"),
        ("orders/services.py", "__import__('socket')", "DOM006"),
        (
            "orders/services.py",
            "from builtins import open as read\nread('test')",
            "DOM006",
        ),
        ("orders/services.py", "import pydantic", "DOM006"),
        ("orders/services.py", "import shelve", "DOM006"),
        ("orders/services.py", "import dbm", "DOM006"),
        ("orders/services.py", "print('domain output')", "DOM006"),
        (
            "orders/services.py",
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.infrastructure.persistence import postgres_runtime",
            "DOM003",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass as dc\n@dc\nclass Value: pass",
            "DOM007",
        ),
        (
            "orders/value_objects.py",
            "import dataclasses as dc\n@dc.dataclass\nclass Value: pass",
            "DOM007",
        ),
        ("orders/value_objects.py", "class Value: pass", "DOM007"),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\nimport typing\n@dataclass(frozen=True)\nclass Value:\n    items: typing.List[bool]",
            "DOM008",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\nfrom typing import List as Items\n@dataclass(frozen=True)\nclass Value:\n    items: Items[bool]",
            "DOM008",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\ntype Items = list[bool]\n@dataclass(frozen=True)\nclass Value:\n    items: Items",
            "DOM008",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Value:\n    items: 'list[bool]'",
            "DOM008",
        ),
        (
            "orders/entities.py",
            "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Order:\n    name: str",
            "DOM009",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\ntype Name = str\n@dataclass(frozen=True)\nclass Value:\n    name: Name",
            "DOM009",
        ),
        (
            "orders/value_objects.py",
            "class Value:\n    def create(self): pass",
            "DOM010",
        ),
        (
            "orders/value_objects.py",
            "class Value:\n    def __post_init__(self):\n        object.__setattr__(self, 'items', tuple(self.items))",
            "DOM011",
        ),
        ("orders/primitives.py", "class Value(str): pass", "DOM012"),
        ("orders/repositories.py", "class Store: pass", "DOM012"),
        (
            "orders/services.py",
            "from dataclasses import dataclass as dc\nclass Outer:\n    @dc\n    class Hidden:\n        items: list[str]",
            "DOM012",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Value:\n    items = []",
            "DOM009",
        ),
        (
            "orders/services.py",
            'def f(value: "app.application.chat.queries.models.ChatResponse"): pass',
            "DOM003",
        ),
        (
            "orders/primitives.py",
            'def f(value: "app.domain.orders.value_objects.Value"): pass',
            "DOM004",
        ),
        (
            "orders/value_objects.py",
            "from dataclasses import dataclass, field\n@dataclass(frozen=True)\nclass Value:\n    items: tuple[bool, ...] = field(default_factory=list)",
            "DOM008",
        ),
        (
            "orders/value_objects.py",
            "class Value:\n    def __post_init__(self):\n        self.items = tuple(self.items)",
            "DOM011",
        ),
        (
            "orders/value_objects.py",
            "class Value:\n    def __post_init__(self):\n        if not isinstance(self.items, tuple): raise TypeError()",
            "DOM011",
        ),
    ],
)
def test_禁止例_規則違反を検出する(
    tmp_path: Path, path: str, source: str, rule: str
) -> None:
    write(tmp_path, {path: source})
    findings = check(tmp_path)
    assert any(f.rule == rule and f.line > 0 for f in findings), findings


def test_新設コンテキスト_正当な別名と参照を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "new_context/primitives.py": "from app.domain.foundation.primitives.base import DomainPrimitive\nclass Name(DomainPrimitive[str]): pass",
            "new_context/value_objects.py": "import dataclasses as dc\nfrom .primitives import Name\n@dc.dataclass(frozen=True)\nclass Value:\n    names: tuple[Name, ...]\n    enabled: bool = False",
            "new_context/services.py": "from urllib.parse import urlparse\nfrom ..other.identifiers import RecordId\nfrom typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from .value_objects import Value",
            "other/services.py": "",
        },
    )
    assert check(tmp_path) == []


def test_新設コンテキスト_公開IDの欠落を検出する(tmp_path: Path) -> None:
    write(tmp_path, {"new_context/entities.py": ""})
    (tmp_path / "backend/app/domain/new_context/identifiers.py").unlink()
    assert any(f.rule == "DOM005" for f in check(tmp_path))


def test_検査器_対象ソースを実行しない(tmp_path: Path) -> None:
    write(tmp_path, {"orders/services.py": "raise RuntimeError('must not execute')"})
    assert check(tmp_path) == []


def test_CLI_作業ディレクトリに依存せず終了コードを返す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, {"orders/services.py": "import socket"})
    monkeypatch.chdir(tmp_path)
    assert main(["--root", str(tmp_path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["rule"] == "DOM006"
    assert main(["--root", str(tmp_path), "--context", "missing"]) == 2
    assert main(["--root", str(tmp_path / "missing")]) == 2


def test_実ソース_全規則を満たす() -> None:
    assert check(Path(__file__).resolve().parents[3]) == []


def test_循環依存_内部モジュールの循環を検出する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "foundation/primitives/base.py": "from .primitives import BaseString",
            "foundation/primitives/primitives.py": "from .base import DomainPrimitive",
        },
    )
    assert any(f.rule == "DOM013" for f in check(tmp_path))


@pytest.mark.parametrize(
    "type_source,rule", [("list[bool]", "DOM008"), ("str", "DOM009")]
)
def test_別モジュールの型別名_不正フィールドを検出する(
    tmp_path: Path, type_source: str, rule: str
) -> None:
    write(
        tmp_path,
        {
            "shared/primitives.py": f"type Payload = {type_source}",
            "orders/value_objects.py": "from dataclasses import dataclass\nfrom ..shared.primitives import Payload\n@dataclass(frozen=True)\nclass Value:\n    payload: Payload",
        },
    )
    assert any(f.rule == rule for f in check(tmp_path))


@pytest.mark.parametrize(
    "declaration",
    [
        "from typing import TypeAlias\nPayload: TypeAlias = {type_source}",
        "from typing import TypeAlias as Alias\nPayload: Alias = {type_source}",
        "import typing as t\nPayload: t.TypeAlias = {type_source}",
    ],
)
@pytest.mark.parametrize("imported", [False, True])
@pytest.mark.parametrize(
    "type_source,rule", [("list[bool]", "DOM008"), ("str", "DOM009")]
)
def test_TypeAlias注釈_不正フィールドを検出する(
    tmp_path: Path, declaration: str, imported: bool, type_source: str, rule: str
) -> None:
    alias = declaration.format(type_source=type_source)
    files = {}
    if imported:
        files["shared/primitives.py"] = alias
        alias = "from ..shared.primitives import Payload"
    files["orders/value_objects.py"] = (
        f"from dataclasses import dataclass\n{alias}\n"
        "@dataclass(frozen=True)\nclass Value:\n    payload: Payload\n"
    )
    write(tmp_path, files)
    assert any(f.rule == rule for f in check(tmp_path))


def test_TypeAlias注釈_不変の値を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/value_objects.py": "from dataclasses import dataclass\nfrom typing import TypeAlias\nPayload: TypeAlias = tuple[bool, ...]\n@dataclass(frozen=True)\nclass Value:\n    payload: Payload",
        },
    )
    assert check(tmp_path) == []


def test_公開ID_基底モジュールの別名を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/identifiers.py": "from app.domain.foundation.primitives import identifiers as ids\nclass RecordId(ids.EntityStringId): pass",
        },
    )
    assert check(tmp_path) == []


def test_CLI_対象絞り込みと正常終了を確認する(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, {"orders/services.py": "", "other/services.py": "import socket"})
    assert check(tmp_path, context="orders") == []
    assert main(["--root", str(tmp_path), "--context", "orders"]) == 0
    assert "0 件の違反" in capsys.readouterr().out


def test_配置_初期化子欠落と空の入れ子を検出する(tmp_path: Path) -> None:
    write(tmp_path, {"orders/services.py": ""})
    directory = tmp_path / "backend/app/domain/orders"
    (directory / "__init__.py").unlink()
    (directory / "hidden_models").mkdir()
    findings = check(tmp_path)
    assert any(
        f.rule == "DOM001" and f.path.endswith("orders/__init__.py") for f in findings
    )
    assert any(
        f.rule == "DOM001" and f.path.endswith("hidden_models") for f in findings
    )


def test_公開ID_余分な操作の公開を検出する(tmp_path: Path) -> None:
    write(tmp_path, {"orders/services.py": ""})
    path = tmp_path / "backend/app/domain/orders/identifiers.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "def helper(): pass\n", encoding="utf-8"
    )
    assert any(f.rule == "DOM005" for f in check(tmp_path))


def test_公開ID_複数集約の正当な識別子を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/identifiers.py": "from app.domain.foundation.primitives.identifiers import EntityUUID\nclass OrderId(EntityUUID): pass\nclass ItemId(EntityUUID): pass"
        },
    )
    assert check(tmp_path) == []


def test_Primitive_列挙型を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/primitives.py": "from enum import StrEnum\nclass Status(StrEnum):\n    ACTIVE = 'active'"
        },
    )
    assert check(tmp_path) == []


def test_業務モデル_別メソッドへ移した暗黙変換も検出する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/value_objects.py": "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Value:\n    enabled: bool\n    def _normalize_fields(self):\n        object.__setattr__(self, 'enabled', True)"
        },
    )
    assert any(item.rule == "DOM011" for item in check(tmp_path))


def test_Repositoryモジュール_不変の検索結果を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/repositories.py": "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Match:\n    found: bool"
        },
    )
    assert check(tmp_path) == []


def test_標準lint_検査器と違反例テストを必ず実行する() -> None:
    root = Path(__file__).resolve().parents[3]
    scripts = json.loads((root / "backend/package.json").read_text(encoding="utf-8"))[
        "scripts"
    ]
    assert "pnpm run lint:domain && pnpm run lint:domain:harness" in scripts["lint"]
    assert scripts["lint:domain"] == "uv run python -m tools.check_domain_architecture"
    assert "tests/tools/test_domain_harness.py" in scripts["lint:domain:harness"]
