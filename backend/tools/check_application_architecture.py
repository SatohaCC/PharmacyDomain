"""Applicationソースを実行せず、配置・依存・公開範囲をASTで検査する。"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str
    feature: str = ""


IMPORT_RULES = frozenset(
    {"APP002", "APP003", "APP004", "APP005", "APP009", "APP010", "APP011", "APP000"}
)
ROOT_ROLES = {
    "boundary_models": "boundary_models",
    "values": "values",
    "policies": "policies",
    "errors": "errors",
}
ROLE_DEPENDENCIES = {
    "runtime": {
        "registry",
        "interfaces",
        "values",
        "policies",
        "errors",
        "command_dtos",
    },
    "registry": {"commands", "queries", "registry"},
    "adapters": {
        "adapters",
        "interfaces",
        "values",
        "errors",
        "command_dtos",
        "query_dtos",
        "command_models",
        "query_models",
        "command_services",
        "query_services",
        "policies",
    },
    "common": {"common", "query_dtos"},
    "commands": {
        "command_services",
        "command_interfaces",
        "command_models",
        "command_dtos",
        "command_policies",
        "interfaces",
        "values",
        "policies",
        "errors",
    },
    "queries": {
        "query_services",
        "query_readers",
        "query_interfaces",
        "query_models",
        "query_dtos",
        "query_policies",
        "interfaces",
        "values",
        "policies",
        "errors",
    },
    "command_services": {
        "command_services",
        "command_interfaces",
        "command_models",
        "command_dtos",
        "command_policies",
        "interfaces",
        "values",
        "policies",
        "errors",
    },
    "query_services": {
        "query_services",
        "query_readers",
        "query_interfaces",
        "query_models",
        "query_dtos",
        "query_policies",
        "interfaces",
        "values",
        "policies",
        "errors",
    },
    "command_interfaces": {
        "command_interfaces",
        "command_models",
        "command_dtos",
        "values",
        "errors",
    },
    "query_readers": {
        "query_readers",
        "query_models",
        "query_dtos",
        "values",
        "errors",
    },
    "query_interfaces": {
        "query_interfaces",
        "query_readers",
        "query_models",
        "query_dtos",
        "values",
        "errors",
    },
    "command_models": {"values", "errors", "boundary_models"},
    "query_models": {"values", "errors", "boundary_models"},
    "command_dtos": {"command_models", "command_dtos", "values", "errors"},
    "query_dtos": {"query_models", "query_dtos", "values", "errors"},
    "command_policies": {
        "command_models",
        "command_dtos",
        "command_policies",
        "values",
        "policies",
        "errors",
    },
    "query_policies": {
        "query_models",
        "query_dtos",
        "query_policies",
        "values",
        "policies",
        "errors",
    },
    "interfaces": {
        "interfaces",
        "command_models",
        "command_dtos",
        "query_models",
        "query_dtos",
        "values",
        "errors",
    },
    "values": {"errors", "values", "boundary_models"},
    "boundary_models": {"boundary_models", "values", "errors"},
    "boundary_interfaces": {"boundary_models", "values", "errors"},
    "policies": {"values", "errors", "policies"},
    "errors": set(),
}

for _role in ROLE_DEPENDENCIES.values():
    _role.update({"boundary_models", "boundary_interfaces"})


def module_side(parts: list[str]) -> str | None:
    if not parts:
        return None
    if parts[0] in {"commands", "queries"}:
        return parts[0]
    if (
        parts[0] == "interfaces"
        and len(parts) >= 2
        and parts[1].endswith(("_query_reader", "_reader"))
    ):
        return "queries"
    return None


TECHNICAL_MODULES = {
    "os",
    "pathlib",
    "asyncio",
    "threading",
    "concurrent",
    "multiprocessing",
    "subprocess",
    "sqlite3",
    "socket",
    "http",
    "urllib",
    "importlib",
}


def module_role(parts: list[str]) -> str | None:
    if not parts:
        return None
    if parts[0] == "common":
        return None
    if parts == ["runtime"]:
        return "runtime"
    if parts == ["registry"]:
        return "registry"
    if len(parts) == 2 and parts[0] == "adapters":
        return "adapters"
    generic = {"command", "query", "handler", "result", "dto", "service"}
    if len(parts) == 1:
        return ROOT_ROLES.get(parts[0])
    if len(parts) == 2 and parts[0] == "boundary_interfaces":
        return "boundary_interfaces"
    if len(parts) == 2 and parts[0] in {"interfaces", "policies"}:
        return parts[0] if parts[1] not in generic else None
    side = module_side(parts)
    if side:
        prefix = "command" if side == "commands" else "query"
        if len(parts) == 2:
            if parts[1] == "models":
                return f"{prefix}_models"
            return (
                side
                if parts[1]
                not in generic
                | {"services", "interfaces", "readers", "dtos", "policies"}
                else None
            )
        if len(parts) == 3 and parts[1] in {
            "services",
            "interfaces",
            "dtos",
            "policies",
        } | ({"readers"} if side == "queries" else set()):
            return f"{prefix}_{parts[1]}" if parts[2] not in generic else None
    return None


def check(
    root: Path,
    config: dict[str, Any],
    *,
    phase: str = "all",
    feature: str | None = None,
) -> list[Finding]:
    application = root / "backend" / "app" / "application"
    if not application.is_dir():
        raise ValueError(f"Applicationディレクトリがありません: {application}")
    features = config["features"]
    # 依存宣言にも循環を許可しない。
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            raise ValueError(f"コンテキスト依存に循環があります: {name}")
        if name in visited:
            return
        if name not in features:
            raise ValueError(f"未登録の依存先です: {name}")
        active.add(name)
        for dependency in features[name].get("depends_on", []):
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in features:
        visit(name)
    findings: set[Finding] = set()
    node: ast.AST
    edges: dict[str, set[str]] = {}
    side_edges: dict[str, set[str]] = {}
    side_locations: dict[tuple[str, str], tuple[Path, int]] = {}
    edge_locations: dict[tuple[str, str], tuple[Path, int]] = {}

    def emit(
        path: Path, line: int, rule: str, message: str, *, scope: str = ""
    ) -> None:
        relative = path.relative_to(root)
        owner = (
            relative.parts[3]
            if len(relative.parts) > 4 and relative.parts[2] == "application"
            else scope
        )
        findings.add(Finding(relative.as_posix(), line, rule, message, owner))

    for path in sorted(application.rglob("*.py")):
        rel = path.relative_to(application)
        if "__pycache__" in rel.parts:
            continue
        if feature is not None and (len(rel.parts) < 2 or rel.parts[0] != feature):
            continue
        module = ".".join(path.relative_to(root / "backend").with_suffix("").parts)
        source_feature = rel.parts[0] if len(rel.parts) >= 2 else None
        parts = list(rel.with_suffix("").parts[1:])
        source_role = module_role(parts)
        if source_feature == "common" and len(parts) == 1 and parts[0] != "models":
            source_role = "common"
        if (
            source_role in {"runtime", "registry", "adapters"}
            and source_feature != "composition"
        ):
            source_role = None
        if source_feature == "common" and len(parts) == 2 and parts[0] == "dtos":
            source_role = "query_dtos"
        if source_feature is None and rel.name != "__init__.py":
            emit(path, 1, "APP001", "宣言されたコンテキスト内へ配置してください")
        if source_feature not in {None, "common"} and source_feature not in features:
            emit(path, 1, "APP001", f"未登録のコンテキストです: {source_feature}")
        if (
            source_feature == "common"
            and rel.name != "__init__.py"
            and source_role not in {"values", "errors", "query_dtos", "common"}
        ):
            emit(
                path,
                1,
                "APP001",
                "commonはコンテキスト非依存の値・例外・共通契約だけを所有します",
            )
        if (
            rel.name != "__init__.py"
            and source_feature != "common"
            and source_role is None
        ):
            emit(
                path,
                1,
                "APP001",
                "commands/queriesと側別の補助処理・DTO・interfacesへ配置してください",
            )
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as exc:
            emit(path, exc.lineno or 1, "APP000", f"構文エラー: {exc.msg}")
            continue
        if source_role in {"boundary_models", "boundary_interfaces"}:
            for definition in tree.body:
                if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    emit(
                        path,
                        definition.lineno,
                        "APP001",
                        "公開境界にはデータかProtocolを配置してください",
                    )
                if isinstance(definition, ast.ClassDef):
                    bases = {
                        ast.unparse(base).split(".")[-1] for base in definition.bases
                    }
                    is_data = any(
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Name)
                        and dec.func.id == "dataclass"
                        and any(
                            k.arg == "frozen"
                            and isinstance(k.value, ast.Constant)
                            and k.value.value is True
                            for k in dec.keywords
                        )
                        for dec in definition.decorator_list
                    )
                    valid = (
                        ("Protocol" in bases)
                        if source_role == "boundary_interfaces"
                        else (is_data or bool(bases & {"Enum", "StrEnum", "IntEnum"}))
                    )
                    if not valid or (
                        source_role == "boundary_models"
                        and any(
                            isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and member.name
                            in {
                                "execute",
                                "read",
                                "save",
                                "delete",
                                "login",
                                "require_active",
                            }
                            for member in definition.body
                        )
                    ):
                        emit(
                            path,
                            definition.lineno,
                            "APP001",
                            "公開境界に具象Serviceや可変モデルを配置できません",
                        )
        if rel.name == "__init__.py":
            # 初期化子からの再公開や実行処理を禁止する。
            for node in tree.body:
                if not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    emit(
                        path,
                        node.lineno,
                        "APP004",
                        "__init__.pyは空またはdocstringだけにしてください",
                    )
        for node in ast.walk(tree):
            targets: list[str] = []
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"open", "eval", "exec", "compile"}
            ):
                emit(
                    path,
                    node.lineno,
                    "APP010",
                    "ファイル操作と動的実行はInfrastructureへ配置してください",
                )
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    emit(
                        path,
                        node.lineno,
                        "APP002",
                        "appから始まる絶対importを使用してください",
                    )
                    package = module.split(".")[:-1]
                    base_parts = package[: len(package) - node.level + 1]
                    base = ".".join(base_parts + ([node.module] if node.module else []))
                else:
                    base = node.module or ""
                if any(alias.name == "*" for alias in node.names):
                    emit(path, node.lineno, "APP003", "wildcard importは禁止です")
                targets = [base]
                # package形式のimportも実際の参照先へ解決する。
                for alias in node.names:
                    candidate = f"{base}.{alias.name}"
                    candidate_path = (root / "backend").joinpath(*candidate.split("."))
                    if (
                        candidate_path.with_suffix(".py").is_file()
                        or candidate_path.is_dir()
                    ):
                        targets.append(candidate)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            ):
                emit(
                    path,
                    node.lineno,
                    "APP011",
                    "動的importは禁止です",
                )
            if not isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                continue
            for target in targets:
                source_side = module_side(parts)
                if (
                    source_side != "commands"
                    and source_role != "adapters"
                    and target.startswith("app.domain.")
                    and "repositories" in target.split(".")
                ):
                    emit(
                        path,
                        node.lineno,
                        "APP015",
                        "参照側はDomain RepositoryではなくQueryReaderを使用してください",
                    )
                top = target.split(".")[0]
                if top in TECHNICAL_MODULES:
                    emit(
                        path,
                        node.lineno,
                        "APP010",
                        f"技術的なI/O・実行基盤はInfrastructureへ配置してください: {target}",
                    )
                if top not in sys.stdlib_module_names and top != "app":
                    emit(
                        path,
                        node.lineno,
                        "APP005",
                        f"標準ライブラリ・Application・Domainだけをimportできます: {target}",
                    )
                # 親packageの参照先は、上で解決した候補でも検査する。
                if (
                    top == "app"
                    and not target.startswith(("app.application.", "app.domain."))
                    and target not in {"app.application", "app.domain"}
                ):
                    emit(
                        path,
                        node.lineno,
                        "APP005",
                        f"外層への依存は禁止です: {target}",
                    )
                if source_feature == "common" and target.startswith("app.domain."):
                    emit(
                        path,
                        node.lineno,
                        "APP009",
                        "commonからDomainへの依存は禁止です",
                    )
                if not target.startswith("app.application."):
                    continue
                target_parts = target.split(".")
                target_feature = target_parts[2]
                target_tail = target_parts[3:]
                if (
                    (
                        not target_tail
                        or (root / "backend").joinpath(*target.split(".")).is_dir()
                    )
                    and isinstance(node, ast.ImportFrom)
                    and len(targets) > 1
                ):
                    continue
                target_role = module_role(target_tail)
                target_side = module_side(target_tail)
                if target != module:
                    side_edges.setdefault(module, set()).add(target)
                    side_locations[(module, target)] = (path, node.lineno)
                if target_feature == "common" and target_tail[:1] == ["dtos"]:
                    target_side = "queries"
                if source_side and target_side and source_side != target_side:
                    emit(
                        path,
                        node.lineno,
                        "APP014",
                        "CommandとQueryのHandler・Reader・DTO・モデルを共有できません",
                    )

                if (
                    source_feature == target_feature
                    and target != module
                    and source_role
                    and target_role
                ):
                    edges.setdefault(module, set()).add(target)
                    edge_locations[(module, target)] = (path, node.lineno)
                if (
                    source_feature != target_feature
                    and source_role in {"commands", "queries"}
                    and target_role in {"commands", "queries"}
                ):
                    emit(
                        path,
                        node.lineno,
                        "APP007",
                        "ユースケース同士を直接importできません",
                    )
                if source_feature == "common" and target_feature != "common":
                    emit(
                        path,
                        node.lineno,
                        "APP009",
                        "commonから個別コンテキストへの依存は禁止です",
                    )
                elif target_feature != source_feature and target_feature != "common":
                    allowed = features.get(source_feature, {}).get("depends_on", [])
                    if target_feature not in allowed:
                        emit(
                            path,
                            node.lineno,
                            "APP008",
                            f"未宣言のコンテキスト依存です: {source_feature} -> {target_feature}",
                        )
                    public = (
                        config.get("common_public_modules", [])
                        if target_feature == "common"
                        else features.get(target_feature, {}).get("public_modules", [])
                    )
                    if ".".join(target_tail) not in public:
                        emit(
                            path,
                            node.lineno,
                            "APP008",
                            f"公開されていないモジュールです: {target}",
                        )
                elif source_feature == target_feature and target != module:
                    if (
                        target_role in {"commands", "queries"}
                        and source_role is not None
                        and source_role != "registry"
                    ):
                        emit(
                            path,
                            node.lineno,
                            "APP007",
                            "Handlerと補助Serviceから他Handlerをimportできません",
                        )
                    elif (
                        source_role
                        and target_role
                        and target_role not in ROLE_DEPENDENCIES[source_role]
                    ):
                        emit(
                            path,
                            node.lineno,
                            "APP006",
                            f"役割間の依存方向に違反しています: {source_role} -> {target_role}",
                        )
    # 中立の契約を挟んでも、反対側のモデルを共有できない。
    for source, side_targets in side_edges.items():
        source_side = module_side(source.split(".")[3:])
        if source_side is None:
            continue
        for initial in side_targets:
            if module_side(initial.split(".")[3:]) is not None:
                continue
            seen: set[str] = set()
            pending = [initial]
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                current_side = module_side(current.split(".")[3:])
                if current_side is not None and current_side != source_side:
                    path, line = side_locations[(source, initial)]
                    emit(
                        path,
                        line,
                        "APP014",
                        "中立の契約を経由してCommandとQueryのモデルを共有できません",
                    )
                    break
                pending.extend(side_edges.get(current, set()))

    # 同じ役割の共有処理でも、モジュールの循環は禁止する。
    done: set[str] = set()
    walking: set[str] = set()

    def visit_module(module: str) -> None:
        if module in done:
            return
        walking.add(module)
        for target in sorted(edges.get(module, set())):
            if target in walking:
                path, line = edge_locations[(module, target)]
                emit(
                    path,
                    line,
                    "APP012",
                    f"Applicationモジュールに循環があります: {module} -> {target}",
                )
            else:
                visit_module(target)
        walking.remove(module)
        done.add(module)

    for module in sorted(edges):
        visit_module(module)

    # 外側の利用者にもApplicationの公開範囲を強制する。
    for path in sorted((root / "backend" / "app").rglob("*.py")):
        relative = path.relative_to(root / "backend" / "app")
        if relative.parts[0] in {"application", "tests", ".venv", "migrations"}:
            continue
        if "__pycache__" in relative.parts:
            continue
        module = ".".join(path.relative_to(root / "backend").with_suffix("").parts)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue  # Application以外の構文検査は言語チェッカが担当する。
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                package = module.split(".")[:-1]
                base = (
                    ".".join(
                        package[: len(package) - node.level + 1]
                        + ([node.module] if node.module else [])
                    )
                    if node.level
                    else node.module or ""
                )
                targets = [base]
                for alias in node.names:
                    candidate = f"{base}.{alias.name}"
                    candidate_path = (root / "backend").joinpath(*candidate.split("."))
                    if (
                        candidate_path.with_suffix(".py").is_file()
                        or candidate_path.is_dir()
                    ):
                        targets.append(candidate)
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in targets:
                if not target.startswith("app.application."):
                    continue
                parts = target.split(".")
                target_feature = parts[2]
                if feature is not None and target_feature != feature:
                    continue
                tail = parts[3:]
                if not tail and isinstance(node, ast.ImportFrom) and len(targets) > 1:
                    continue  # packageではなく解決済みの子モジュールを検査する。
                public = (
                    config.get("common_public_modules", [])
                    if target_feature == "common"
                    else features.get(target_feature, {}).get("public_modules", [])
                )
                if ".".join(tail) not in public:
                    emit(
                        path,
                        node.lineno,
                        "APP008",
                        f"公開されていないApplicationモジュールです: {target}",
                        scope=target_feature,
                    )
                if relative.parts[0] == "presentational" and module_role(tail) in {
                    "interfaces",
                    "policies",
                    "values",
                    "command_interfaces",
                    "query_interfaces",
                    "query_readers",
                    "command_services",
                    "query_services",
                    "command_policies",
                    "query_policies",
                }:
                    emit(
                        path,
                        node.lineno,
                        "APP013",
                        "Presentationは公開UseCase・DTO・実行スコープ契約に依存してください",
                        scope=target_feature,
                    )
    if phase == "imports":
        return sorted(f for f in findings if f.rule in IMPORT_RULES)
    if phase == "enforced":
        enforced = set(config.get("enforced_features", []))
        unknown = enforced - set(features)
        if unknown:
            raise ValueError(
                f"強制対象に未登録コンテキストがあります: {sorted(unknown)}"
            )
        return sorted(
            f for f in findings if f.rule in IMPORT_RULES or f.feature in enforced
        )
    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--phase", choices=("imports", "enforced", "all"), default="all"
    )
    parser.add_argument("--feature")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        with (args.config or root / "backend" / "application-architecture.toml").open(
            "rb"
        ) as stream:
            config = tomllib.load(stream)
        if (
            args.feature
            and args.feature not in config["features"]
            and args.feature != "common"
        ):
            raise ValueError(f"未登録のコンテキストです: {args.feature}")
        findings = check(root, config, phase=args.phase, feature=args.feature)
    except (OSError, ValueError, KeyError) as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "path": f.path,
                        "line": f.line,
                        "rule": f.rule,
                        "message": f.message,
                        "feature": f.feature,
                    }
                    for f in findings
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule} {finding.message}")
        print(
            f"{len(findings)} 件の違反; {dict(sorted(Counter(f.rule for f in findings).items()))}"
        )
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
