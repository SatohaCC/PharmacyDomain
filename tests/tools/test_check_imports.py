from pathlib import Path

import pytest

from tools.check_imports import (
    ImportAnalysisError,
    ImportRule,
    analyze_source,
    is_within,
    load_config,
    main,
    module_name_for,
)

_DOMAIN_RULE = ImportRule(package="app.domain", forbidden=("app.application",))


def test_禁止された接頭辞のimportは違反になる() -> None:
    # Arrange
    source = "from app.application.corporate import CorporateAccessService\n"

    # Act
    violations = analyze_source(
        source,
        module_name="app.domain.corporate.corporate",
        rules=[_DOMAIN_RULE],
    )

    # Assert
    assert len(violations) == 1
    assert violations[0].imported == "app.application.corporate"
    assert violations[0].forbidden == "app.application"


def test_許可された接頭辞のimportは違反にならない() -> None:
    # Arrange
    source = "from app.domain.foundation.entity import AggregateRoot\n"

    # Act
    violations = analyze_source(
        source,
        module_name="app.domain.corporate.corporate",
        rules=[_DOMAIN_RULE],
    )

    # Assert
    assert violations == ()


def test_規則の対象外パッケージは検査されない() -> None:
    # Arrange
    source = "from app.application.corporate import CorporateAccessService\n"

    # Act
    violations = analyze_source(
        source,
        module_name="app.application.store.get_store",
        rules=[_DOMAIN_RULE],
    )

    # Assert
    assert violations == ()


def test_親モジュールから名前を取り出すimportも違反になる() -> None:
    # Arrange: `from app.application import staff` は app.application.staff への依存。
    source = "from app.application import staff\n"
    rule = ImportRule(
        package="app.application.corporate", forbidden=("app.application.staff",)
    )

    # Act
    violations = analyze_source(
        source,
        module_name="app.application.corporate.corporate_access",
        rules=[rule],
    )

    # Assert
    assert len(violations) == 1
    assert violations[0].imported == "app.application.staff"


def test_import文の形式でも違反を検出する() -> None:
    # Arrange
    source = "import app.application.store.get_store as gs\n"
    rule = ImportRule(
        package="app.application.corporate", forbidden=("app.application.store",)
    )

    # Act
    violations = analyze_source(
        source,
        module_name="app.application.corporate.get_corporate",
        rules=[rule],
    )

    # Assert
    assert len(violations) == 1
    assert violations[0].line == 1


def test_TYPE_CHECKING内のimportも違反になる() -> None:
    # Arrange: 実行時依存は無くても設計上の依存方向は同じく壊れる。
    source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.corporate import CorporateAccessService
"""

    # Act
    violations = analyze_source(
        source,
        module_name="app.domain.corporate.corporate",
        rules=[_DOMAIN_RULE],
    )

    # Assert
    assert len(violations) == 1


def test_相対importを絶対モジュール名へ解決する() -> None:
    # Arrange: app.domain.corporate.corporate から見た `from ..staff import X`。
    source = "from ..staff import Staff\n"
    rule = ImportRule(package="app.domain", forbidden=("app.domain.staff",))

    # Act
    violations = analyze_source(
        source,
        module_name="app.domain.corporate.corporate",
        rules=[rule],
    )

    # Assert
    assert len(violations) == 1
    assert violations[0].imported == "app.domain.staff"


def test_解決できない相対importは解析例外になる() -> None:
    # Arrange
    source = "from ..... import broken\n"

    # Act / Assert
    with pytest.raises(ImportAnalysisError, match="相対 import を解決できません"):
        analyze_source(
            source,
            module_name="app.domain.corporate",
            rules=[_DOMAIN_RULE],
        )


def test_構文エラーは解析例外になる() -> None:
    # Act / Assert
    with pytest.raises(ImportAnalysisError, match="Pythonの構文解析に失敗しました"):
        analyze_source(
            "from app import (",
            module_name="app.domain.broken",
            rules=[_DOMAIN_RULE],
            source_file=Path("broken.py"),
        )


def test_パッケージ配下の判定は接頭辞の境界を区別する() -> None:
    # Act / Assert
    assert is_within("app.domain.corporate", "app.domain")
    assert is_within("app.domain", "app.domain")
    assert not is_within("app.domain_extra", "app.domain")


def test_ファイルパスからモジュール名を決定する(tmp_path: Path) -> None:
    # Arrange
    module_path = tmp_path / "app" / "domain" / "corporate.py"
    package_path = tmp_path / "app" / "domain" / "__init__.py"

    # Act
    module = module_name_for(module_path, tmp_path)
    package = module_name_for(package_path, tmp_path)

    # Assert
    assert module == ("app.domain.corporate", False)
    assert package == ("app.domain", True)


def test_ルート外のファイルは解析例外になる(tmp_path: Path) -> None:
    # Act / Assert
    with pytest.raises(ImportAnalysisError, match="解析対象がルート外にあります"):
        module_name_for(tmp_path / "outside.py", tmp_path / "root")


def test_自身を含む接頭辞を禁止先に指定すると設定エラーになる(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[tool.import_rules.forbidden]
"app.domain" = ["app"]
""",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="自身を含む接頭辞"):
        load_config(config_path)


def test_pyprojectの設定を読み込む(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[tool.import_rules]
root = "src"
paths = ["src/app"]

[tool.import_rules.forbidden]
"app.domain" = ["app.application", "fastapi"]
""",
        encoding="utf-8",
    )

    # Act
    config = load_config(config_path)

    # Assert
    assert config.root == "src"
    assert config.paths == ("src/app",)
    assert config.rules == (
        ImportRule(package="app.domain", forbidden=("app.application", "fastapi")),
    )


def test_Domain基盤とSharedKernelは全Domainコンテキストへの依存を禁止する() -> None:
    # Arrange
    rules = {rule.package: set(rule.forbidden) for rule in load_config().rules}
    contexts = _direct_packages(
        Path("app/domain"),
        prefix="app.domain",
        excluded={"foundation", "shared"},
    )

    # Act
    foundation_forbidden = rules["app.domain.foundation"]
    shared_forbidden = rules["app.domain.shared"]

    # Assert
    assert contexts <= foundation_forbidden
    assert contexts <= shared_forbidden
    assert "app.domain.shared" in foundation_forbidden
    assert "app.application" in foundation_forbidden
    assert "app.application" in shared_forbidden


def test_Application共通基盤は全Applicationコンテキストへの依存を禁止する() -> None:
    # Arrange
    rules = {rule.package: set(rule.forbidden) for rule in load_config().rules}
    contexts = _direct_packages(
        Path("app/application"),
        prefix="app.application",
        excluded={"common"},
    )

    # Act
    common_forbidden = rules["app.application.common"]

    # Assert
    assert contexts <= common_forbidden
    assert "app.domain" in common_forbidden


def test_設定ファイルが無い場合は既定値を返す(tmp_path: Path) -> None:
    # Act
    config = load_config(tmp_path / "missing.toml")

    # Assert
    assert config.rules == ()
    assert config.paths == ("app",)


def test_違反だけでは既定で終了成功になる(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    config_path = _write_violating_project(tmp_path)

    # Act
    exit_code = main(["--config", str(config_path)])

    # Assert
    assert exit_code == 0
    assert "違反 1件" in capsys.readouterr().out


def test_fail_on_violation指定時は終了コード一になる(tmp_path: Path) -> None:
    # Arrange
    config_path = _write_violating_project(tmp_path)

    # Act
    exit_code = main(["--config", str(config_path), "--fail-on-violation"])

    # Assert
    assert exit_code == 1


def test_設定エラーは終了コード二になる(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[tool.import_rules.forbidden]
"app.domain" = []
""",
        encoding="utf-8",
    )

    # Act
    exit_code = main(["--config", str(config_path), "--fail-on-violation"])

    # Assert
    assert exit_code == 2


def _write_violating_project(tmp_path: Path) -> Path:
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[tool.import_rules]
root = "."
paths = ["app"]

[tool.import_rules.forbidden]
"app.domain" = ["app.application"]
""",
        encoding="utf-8",
    )
    source_path = tmp_path / "app" / "domain" / "corporate.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "from app.application.corporate import CorporateAccessService\n",
        encoding="utf-8",
    )
    return config_path


def _direct_packages(
    root: Path,
    *,
    prefix: str,
    excluded: set[str],
) -> set[str]:
    """直下にPythonモジュールを持つパッケージ名を列挙する。"""
    return {
        f"{prefix}.{directory.name}"
        for directory in root.iterdir()
        if directory.is_dir()
        and directory.name not in excluded
        and any(directory.glob("*.py"))
    }
