"""共有基盤の禁止先が新しいパッケージにも適用されることを検証する。"""

import tomllib
from pathlib import Path

import pytest

from tools.check_foundation_dependencies import forbidden_imports

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "source",
    [
        "import pydantic",
        "from fastapi import Request",
        "from app.domain.new_context.identifiers import NewId",
        "from ..shared import actor",
    ],
)
def test_共通基盤_外部技術や業務語彙の参照は_拒否する(source: str) -> None:
    assert forbidden_imports(
        source,
        module="app.domain.foundation.example",
        allowed_internal=("app.domain.foundation",),
    )


def test_共通基盤_標準ライブラリと内部基盤の参照は_許可する() -> None:
    assert (
        forbidden_imports(
            "from datetime import date\nfrom .exceptions import Error",
            module="app.domain.foundation.example",
            allowed_internal=("app.domain.foundation",),
        )
        == ()
    )


def test_共通基盤_本番コードは_宣言した依存範囲を守る() -> None:
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    rules = config["tool"]["import_rules"]["allowed_internal"]
    assert rules
    violations: list[str] = []
    for package, allowed in rules.items():
        for path in (_ROOT / package.replace(".", "/")).rglob("*.py"):
            module = ".".join(path.relative_to(_ROOT).with_suffix("").parts)
            if path.name == "__init__.py":
                module = module.removesuffix(".__init__")
            violations.extend(
                f"{path.relative_to(_ROOT)}:{item}"
                for item in forbidden_imports(
                    path.read_text(encoding="utf-8"),
                    module=module,
                    allowed_internal=tuple(allowed),
                    is_package=path.name == "__init__.py",
                )
            )
    assert not violations, violations
