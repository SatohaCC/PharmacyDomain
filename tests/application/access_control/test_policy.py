from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.application.access_control import (
    ActorContext,
    ActorRole,
    AuthorizationService,
    Permission,
    TenantBoundaryNotFoundError,
)
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate import CorporateId

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_permission_classification_incomplete_raises_runtime_error() -> None:
    # Arrange
    from app.application.access_control.policy import (
        _verify_permission_classification,
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="いずれかの権限集合に分類されていません"):
        _verify_permission_classification(
            vendor_only=frozenset(),
            corporate_admin=frozenset(),
        )


def test_permission_classification_overlapping_raises_runtime_error() -> None:
    # Arrange
    from app.application.access_control.policy import (
        _verify_permission_classification,
    )

    everything = frozenset(Permission)

    # Act & Assert
    with pytest.raises(RuntimeError, match="重複が存在します"):
        _verify_permission_classification(
            vendor_only=everything,
            corporate_admin=everything,
        )


def test_permission_classification_is_verified_under_optimized_mode() -> None:
    """`assert` へ戻すと `python -O` で検証が消えることを回帰テストで防ぐ。"""
    # Arrange
    snippet = (
        "from app.application.access_control.policy import "
        "_verify_permission_classification as verify\n"
        "verify(vendor_only=frozenset(), corporate_admin=frozenset())\n"
    )

    # Act: Windowsの既定コンソール encoding では日本語メッセージを復号できないため、
    # 子プロセスの出力を UTF-8 に固定する。
    completed = subprocess.run(
        [sys.executable, "-O", "-c", snippet],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )

    # Assert
    assert completed.returncode != 0
    assert "RuntimeError" in completed.stderr


def test_actor_context_corporate_admin_without_corporate_id_raises_value_error() -> (
    None
):
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="法人管理者には所属法人が必要です"):
        ActorContext(
            principal_id="test-admin",
            roles=frozenset({ActorRole.CORPORATE_ADMIN}),
            corporate_id=None,
        )


def test_vendor_admin_any_corporate_allows_access() -> None:
    # Arrange
    authorization = AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
    )

    # Act & Assert (例外が発生しなければ成功)
    authorization.require(
        permission=Permission.MANAGE_STAFF,
        target_corporate_id=CorporateId.generate(),
    )


def test_corporate_admin_own_corporate_allows_access() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    authorization = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="corp-admin-1",
            corporate_id=corporate_id,
        )
    )

    # Act & Assert (例外が発生しなければ成功)
    authorization.require(
        permission=Permission.MANAGE_STAFF,
        target_corporate_id=corporate_id,
    )


def test_corporate_admin_other_corporate_raises_boundary_not_found() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    other_corporate_id = CorporateId.generate()
    authorization = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="corp-admin-1",
            corporate_id=corporate_id,
        )
    )

    # Act & Assert
    with pytest.raises(TenantBoundaryNotFoundError):
        authorization.require(
            permission=Permission.MANAGE_STAFF,
            target_corporate_id=other_corporate_id,
        )


def test_corporate_admin_vendor_only_permission_raises_authorization_error() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    authorization = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="corp-admin-1",
            corporate_id=corporate_id,
        )
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        authorization.require(
            permission=Permission.MANAGE_CORPORATE_STATUS,
            target_corporate_id=corporate_id,
        )


def test_vendor_admin_vendor_permissions_succeed() -> None:
    # Arrange
    authorization = AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
    )

    # Act & Assert
    authorization.require_vendor_system_admin(permission=Permission.REGISTER_CORPORATE)
    authorization.require_vendor_system_admin(
        permission=Permission.MANAGE_CORPORATE_STATUS
    )


def test_corporate_admin_vendor_operation_raises_authorization_error() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    authorization = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="corp-admin-1",
            corporate_id=corporate_id,
        )
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        authorization.require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )


def test_vendor_admin_non_vendor_permission_raises_value_error() -> None:
    # Arrange
    authorization = AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
    )

    # Act & Assert
    with pytest.raises(
        ValueError, match="ベンダーシステム管理者専用権限ではありません"
    ):
        authorization.require_vendor_system_admin(
            permission=Permission.MANAGE_CORPORATE
        )


def test_unknown_role_any_corporate_raises_authorization_error() -> None:
    # Arrange
    authorization = AuthorizationService(
        ActorContext(principal_id="unknown", roles=frozenset())
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        authorization.require(
            permission=Permission.VIEW_CORPORATE,
            target_corporate_id=CorporateId.generate(),
        )
