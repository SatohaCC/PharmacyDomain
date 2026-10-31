"""実ソースの適合だけでなく、合成した禁止例で検査規則を検証する。"""

from pathlib import Path

import pytest

from tools.check_application_architecture import check, main

CONFIG = {
    "features": {
        "orders": {
            "depends_on": ["catalog"],
            "public_modules": ["commands.models", "queries.get_order"],
        },
        "catalog": {
            "depends_on": [],
            "public_modules": ["commands.models", "queries.get_product"],
        },
        "other": {"depends_on": [], "public_modules": ["commands.models"]},
    }
}


def write(root: Path, files: dict[str, str]) -> None:
    (root / "backend/app/application").mkdir(parents=True, exist_ok=True)
    for relative, source in files.items():
        path = root / "backend/app/application" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "path,source,expected",
    [
        ("orders/create_order/handler.py", "", "APP001"),
        (
            "orders/__init__.py",
            "from app.application.orders.commands.models import Order",
            "APP004",
        ),
        (
            "orders/commands/models.py",
            "from backend.infrastructure.db import Session",
            "APP005",
        ),
        (
            "orders/commands/models.py",
            "from backend.config.settings import Settings",
            "APP005",
        ),
        ("orders/commands/models.py", "import pydantic", "APP005"),
        (
            "orders/commands/models.py",
            "from app.application.orders.interfaces.reader import Reader",
            "APP006",
        ),
        (
            "orders/interfaces/reader.py",
            "from app.application.orders.commands.services.orders_service import Service",
            "APP006",
        ),
        (
            "orders/commands/create_order.py",
            "from app.application.orders.queries.get_order import get_order",
            "APP007",
        ),
        (
            "orders/queries/get_order.py",
            "from app.application.orders.queries.list_orders import list_orders",
            "APP007",
        ),
        (
            "orders/commands/create_order.py",
            "from app.application.other.commands.models import Item",
            "APP008",
        ),
        (
            "orders/commands/create_order.py",
            "from app.application.catalog.interfaces.reader import Reader",
            "APP008",
        ),
        (
            "common/models.py",
            "from app.application.orders.commands.models import Order",
            "APP009",
        ),
        (
            "orders/commands/create_order.py",
            "from concurrent.futures import ThreadPoolExecutor",
            "APP010",
        ),
        ("orders/commands/create_order.py", "import importlib as loader", "APP010"),
        (
            "orders/commands/create_order.py",
            "__import__('backend.infrastructure.db')",
            "APP011",
        ),
        ("orders/commands/create_order.py", "def broken(:", "APP000"),
    ],
)
def test_禁止例_各規則の違反を検出する(
    tmp_path: Path, path: str, source: str, expected: str
) -> None:
    write(tmp_path, {path: source})
    assert expected in {finding.rule for finding in check(tmp_path, CONFIG)}


@pytest.mark.parametrize(
    "source",
    [
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import backend.infrastructure.db as db",
        "def execute():\n    from backend.infrastructure.db import Session",
    ],
)
def test_型専用と関数内import_外層依存を隠せない(tmp_path: Path, source: str) -> None:
    write(tmp_path, {"orders/commands/create_order.py": source})
    assert "APP005" in {f.rule for f in check(tmp_path, CONFIG)}


def test_package形式のimport_定義先の役割を検査する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/models.py": "from app.application.orders.commands.services import orders_service as svc",
            "orders/commands/services/orders_service.py": "",
        },
    )
    assert "APP006" in {f.rule for f in check(tmp_path, CONFIG)}


def test_相対import_参照先の禁止規則も検査する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {"orders/commands/models.py": "from ....infrastructure.db import Session"},
    )
    assert "APP005" in {f.rule for f in check(tmp_path, CONFIG)}


def test_公開境界と正当な配置_違反にならない(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/__init__.py": '"""注文。"""',
            "orders/commands/create_order.py": "from app.application.orders.commands.models import Order\nfrom app.application.orders.interfaces.writer import Writer\nfrom app.application.catalog.commands.models import Product\nfrom app.domain.orders.entities import OrderEntity",
            "orders/queries/get_order.py": "from app.application.orders.queries.dtos.order_summary import Summary",
            "orders/interfaces/writer.py": "from app.application.orders.commands.models import Order",
            "orders/policies.py": "from app.application.orders.values import OrderId",
            "orders/commands/models.py": "from app.application.orders.values import OrderId",
            "orders/values.py": "from app.application.orders.errors import InvalidOrder",
            "orders/errors.py": "class InvalidOrder(Exception): pass",
            "orders/queries/dtos/order_summary.py": "from app.application.orders.values import OrderId",
            "common/values.py": "from dataclasses import dataclass",
            "catalog/commands/models.py": "",
        },
    )
    assert not check(tmp_path, CONFIG)


def test_import限定診断_配置の完了を意味しない(tmp_path: Path) -> None:
    write(
        tmp_path,
        {"orders/old_models.py": "from app.domain.orders.entities import Order"},
    )
    assert not check(tmp_path, CONFIG, phase="imports")
    assert {f.rule for f in check(tmp_path, CONFIG)} == {"APP001"}


def test_CLI_終了コードとJSONを返す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, {"orders/commands/create_order.py": "import sqlalchemy"})
    config = tmp_path / "rules.toml"
    config.write_text(
        '[features.orders]\ndepends_on=[]\npublic_modules=["models"]\n',
        encoding="utf-8",
    )
    args = ["--root", str(tmp_path), "--config", str(config)]
    assert main(args + ["--json"]) == 1
    assert '"rule": "APP005"' in capsys.readouterr().out
    assert main(args + ["--feature", "missing"]) == 2
    assert "未登録のコンテキスト" in capsys.readouterr().err
    (tmp_path / "backend/app/application/orders/commands/create_order.py").write_text(
        "", encoding="utf-8"
    )
    assert main(args) == 0


def test_対象限定診断_全体の違反を消さない(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/models.py": "",
            "catalog/commands/models.py": "import sqlalchemy",
        },
    )
    assert not check(tmp_path, CONFIG, feature="orders")
    assert any(f.rule == "APP005" for f in check(tmp_path, CONFIG))


@pytest.mark.parametrize(
    "files, rule",
    [
        ({"orders/commands/handler.py": ""}, "APP001"),
        ({"common/commands/create_order.py": ""}, "APP001"),
        (
            {"common/models.py": "from app.domain.orders.entities import Order"},
            "APP009",
        ),
    ],
)
def test_汎用名と共通層の業務依存_拒否する(
    tmp_path: Path, files: dict[str, str], rule: str
) -> None:
    write(tmp_path, files)
    assert rule in {f.rule for f in check(tmp_path, CONFIG)}


def test_コンテキスト宣言の循環_設定エラーになる(tmp_path: Path) -> None:
    write(tmp_path, {})
    config = {
        "features": {
            "a": {"depends_on": ["b"]},
            "b": {"depends_on": ["a"]},
        }
    }
    with pytest.raises(ValueError, match="循環"):
        check(tmp_path, config)


def test_未登録の依存先_設定エラーになる(tmp_path: Path) -> None:
    write(tmp_path, {})
    with pytest.raises(ValueError, match="未登録の依存先"):
        check(tmp_path, {"features": {"a": {"depends_on": ["missing"]}}})


def test_実ソース_import規則を満たす() -> None:
    import tomllib

    BACKEND_ROOT = Path(__file__).resolve().parents[2]

    root = BACKEND_ROOT.parent
    with (BACKEND_ROOT / "application-architecture.toml").open("rb") as stream:
        config = tomllib.load(stream)
    findings = check(root, config, phase="imports")
    assert not findings, "\n".join(str(finding) for finding in findings)


@pytest.mark.parametrize(
    "source,rule",
    [
        (
            "from app.application.orders.interfaces.writer import Writer",
            "APP008",
        ),
        ("from app.application.orders.policies import policy", "APP013"),
    ],
)
def test_外部利用側_公開規則を検査する(tmp_path: Path, source: str, rule: str) -> None:
    write(tmp_path, {"orders/interfaces/writer.py": "", "orders/policies.py": ""})
    path = tmp_path / "backend/app/presentational/routes.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    assert rule in {f.rule for f in check(tmp_path, CONFIG)}


def test_CompositionRoot_公開ポートを利用できる(tmp_path: Path) -> None:
    write(tmp_path, {"orders/interfaces/writer.py": ""})
    path = tmp_path / "backend/app/infrastructure/composition.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from app.application.orders.interfaces.writer import Writer",
        encoding="utf-8",
    )
    config = {
        "features": {
            "orders": {
                "depends_on": [],
                "public_modules": ["interfaces.writer"],
            }
        }
    }
    assert not check(tmp_path, config)


@pytest.mark.parametrize(
    "source",
    [
        "from app.application.catalog.commands import models as data",
        "import app.application.catalog.commands.models as data",
        "from app.application.catalog.commands.models import Product as Item",
    ],
)
def test_公開importの表記差_同じ依存として扱う(tmp_path: Path, source: str) -> None:
    write(
        tmp_path,
        {"orders/commands/create_order.py": source, "catalog/commands/models.py": ""},
    )
    assert not check(tmp_path, CONFIG)


def test_CLI_呼出元のディレクトリに依存しない(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.check_application_architecture as harness

    BACKEND_ROOT = Path(__file__).resolve().parents[2]

    monkeypatch.chdir(tmp_path)
    assert harness.main(["--phase", "imports"]) == 0
    assert BACKEND_ROOT.is_dir()


def test_強制対象診断_限定対象以外も全体診断に残る(tmp_path: Path) -> None:
    write(tmp_path, {"orders/old_file.py": "", "catalog/old_file.py": ""})
    config = {**CONFIG, "enforced_features": ["orders"]}
    enforced = check(tmp_path, config, phase="enforced")
    assert len(enforced) == 1 and enforced[0].feature == "orders"
    assert len(check(tmp_path, config)) == 2


def test_強制対象診断_外部利用側も検査する(tmp_path: Path) -> None:
    write(tmp_path, {"orders/interfaces/private.py": ""})
    path = tmp_path / "backend/app/presentational/routes.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from app.application.orders.interfaces.private import Writer",
        encoding="utf-8",
    )
    config = {**CONFIG, "enforced_features": ["orders"]}
    assert any(
        f.rule == "APP008" and f.feature == "orders"
        for f in check(tmp_path, config, phase="enforced")
    )


def test_実ソース_強制対象の全規則を満たす() -> None:
    import tomllib

    BACKEND_ROOT = Path(__file__).resolve().parents[2]

    with (BACKEND_ROOT / "application-architecture.toml").open("rb") as stream:
        config = tomllib.load(stream)
    assert not check(BACKEND_ROOT.parent, config, phase="enforced")


def test_共有ServiceとPolicy_正当な依存を許可する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/create_order.py": "from app.application.orders.commands.services.creation import create",
            "orders/commands/services/creation.py": "from app.application.orders.policies.validation import validate\nfrom app.application.orders.interfaces.writer import Writer",
            "orders/policies/validation.py": "from app.application.orders.policies.limits import LIMIT",
            "orders/policies/limits.py": "LIMIT=1",
            "orders/interfaces/writer.py": "from app.application.orders.interfaces.transaction import Transaction",
            "orders/interfaces/transaction.py": "",
        },
    )
    assert not check(tmp_path, CONFIG)


def test_ポート間の循環_検出する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/interfaces/a.py": "from app.application.orders.interfaces.b import B",
            "orders/interfaces/b.py": "from app.application.orders.interfaces.a import A",
        },
    )
    assert any(f.rule == "APP012" for f in check(tmp_path, CONFIG))


def test_共有ServiceからHandler_逆依存を拒否する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/services/creation.py": "from app.application.orders.commands.create_order import execute"
        },
    )
    assert any(f.rule == "APP007" for f in check(tmp_path, CONFIG))


def test_別コンテキストHandler_直接依存を拒否する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/create_order.py": "from app.application.catalog.queries.get_product import execute"
        },
    )
    assert any(f.rule == "APP007" for f in check(tmp_path, CONFIG))


def test_実ソース_全規則と公開先の実在を検証する() -> None:
    import tomllib

    BACKEND_ROOT = Path(__file__).resolve().parents[2]

    with (BACKEND_ROOT / "application-architecture.toml").open("rb") as stream:
        config = tomllib.load(stream)
    assert not check(BACKEND_ROOT.parent, config)
    assert set(config["enforced_features"]) == set(config["features"])
    for feature, spec in config["features"].items():
        for public in spec["public_modules"]:
            path = BACKEND_ROOT / "app" / "application" / feature
            assert path.joinpath(*public.split(".")).with_suffix(".py").is_file(), (
                feature,
                public,
            )


@pytest.mark.parametrize("filename", ["service.py", "services.py"])
def test_Feature直下のService_配置を拒否する(tmp_path: Path, filename: str) -> None:
    write(tmp_path, {f"orders/{filename}": ""})
    assert "APP001" in {f.rule for f in check(tmp_path, CONFIG)}


@pytest.mark.parametrize(
    "path,source,rule",
    [
        (
            "orders/commands/create_order.py",
            "from app.application.orders.queries.dtos.order import Order",
            "APP014",
        ),
        (
            "orders/queries/get_order.py",
            "from app.application.orders.commands.models import Order",
            "APP014",
        ),
        (
            "orders/commands/services/create.py",
            "from app.application.catalog.queries.get_product import execute",
            "APP014",
        ),
        (
            "orders/interfaces/order_query_reader.py",
            "from app.application.orders.commands.models import Order",
            "APP014",
        ),
        (
            "orders/queries/get_order.py",
            "from app.domain.orders.repositories import OrderRepository",
            "APP015",
        ),
        (
            "orders/queries/services/read.py",
            "from app.domain.orders import repositories as repo",
            "APP015",
        ),
        ("orders/services/shared.py", "", "APP001"),
        ("orders/models.py", "", "APP001"),
        ("orders/dtos/order.py", "", "APP001"),
        ("orders/ports/reader.py", "", "APP001"),
    ],
)
def test_CommandQuery境界とRepository参照_違反を検出する(
    tmp_path: Path, path: str, source: str, rule: str
) -> None:
    write(tmp_path, {path: source, "orders/queries/dtos/order.py": ""})
    if "import repositories" in source:
        domain = tmp_path / "backend/app/domain/orders"
        domain.mkdir(parents=True)
        (domain / "repositories.py").write_text("", encoding="utf-8")
    assert rule in {f.rule for f in check(tmp_path, CONFIG)}


def test_Application規則_462_期待した境界を検証する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/queries/get_order.py": "from app.application.orders.interfaces.order_query_reader import OrderQueryReader",
            "orders/interfaces/order_query_reader.py": "from app.application.orders.queries.dtos.order import Order",
            "orders/queries/dtos/order.py": "from dataclasses import dataclass",
        },
    )
    assert not check(tmp_path, CONFIG)


@pytest.mark.parametrize(
    "source",
    [
        "from app.application.orders.queries import models as data",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.application.orders.queries.dtos.order import Order as Result",
        "def execute():\n    from app.application.orders.queries.dtos.order import Order",
    ],
)
def test_Application規則_482_期待した境界を検証する(
    tmp_path: Path, source: str
) -> None:
    write(
        tmp_path,
        {
            "orders/commands/create_order.py": source,
            "orders/queries/models.py": "",
            "orders/queries/dtos/order.py": "",
        },
    )
    assert "APP014" in {f.rule for f in check(tmp_path, CONFIG)}


def test_Application規則_494_期待した境界を検証する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/create_order.py": "from app.application.common.dtos.page import Page",
            "common/dtos/page.py": "",
        },
    )
    assert "APP014" in {f.rule for f in check(tmp_path, CONFIG)}


def test_Application規則_505_期待した境界を検証する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/policies/validation.py": "from app.domain.orders.repositories import OrderRepository"
        },
    )
    assert "APP015" in {f.rule for f in check(tmp_path, CONFIG)}


def test_Application規則_515_期待した境界を検証する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/commands/create_order.py": "from app.domain.orders.repositories import OrderRepository"
        },
    )
    assert not check(tmp_path, CONFIG)


@pytest.mark.parametrize(
    "source", ["import pathlib", "import os", "import asyncio", "open('test.txt')"]
)
def test_技術実装_ファイルと実行基盤を拒否する(tmp_path: Path, source: str) -> None:
    write(tmp_path, {"orders/commands/create_order.py": source})
    assert "APP010" in {f.rule for f in check(tmp_path, CONFIG)}


def test_境界モデル_具象サービスの隠蔽を拒否する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/boundary_models.py": "class Reader:\n    async def execute(self): return 1"
        },
    )
    assert "APP001" in {f.rule for f in check(tmp_path, CONFIG)}


def test_境界契約_具象実装の配置を拒否する(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/boundary_interfaces/authentication.py": "class Authentication:\n    def login(self): return 'token'"
        },
    )
    assert "APP001" in {f.rule for f in check(tmp_path, CONFIG)}


def test_中立の契約経由_反対側のモデルを共有できない(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "orders/queries/get_order.py": "from app.application.orders.interfaces.writer import Writer",
            "orders/interfaces/writer.py": "from app.application.orders.commands.models import State",
            "orders/commands/models.py": "class State: pass",
        },
    )
    assert "APP014" in {f.rule for f in check(tmp_path, CONFIG)}


def test_品質ゲート_通常lintが全規則と自己検証を実行する() -> None:
    import json

    package = Path(__file__).resolve().parents[2] / "package.json"
    scripts = json.loads(package.read_text(encoding="utf-8"))["scripts"]
    assert "pnpm run lint:application" in scripts["lint"]
    assert "pnpm run lint:application:harness" in scripts["lint"]
    assert (
        scripts["lint:application"]
        == "uv run python -m tools.check_application_architecture"
    )


@pytest.mark.parametrize(
    "relative,callee",
    [
        (
            "app/application/access_control/policies.py",
            "_verify_permission_classification",
        ),
        (
            "app/application/composition/adapters/prescription_references.py",
            "_verify_slot_mapping_is_complete",
        ),
    ],
)
def test_起動時検証_定義だけでなく_モジュール読込時に実行する(
    relative: str, callee: str
) -> None:
    import ast

    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / relative).read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == callee
        for node in tree.body
    )
