"""DDD ドメインサービス（Domain Service）の設計規則・無状態性を強制するアーキテクチャテスト。

ドメインサービスの無状態性（Statelessness）、リポジトリ注入の限定、純粋性、
インフラ非依存、ならびに集約のドメイン貧血症（Anemic Model）防止を機械的に検証する。
"""

from __future__ import annotations

import datetime
import importlib
import inspect
import pkgutil
import typing
from typing import Any

import pytest

import app.domain
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientStateConflictError
from app.domain.patient.lifecycle import PatientStatusReason
from app.domain.patient.merge_service import PatientMergeService
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientNumber
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.exceptions import InvalidCorporateAssignmentError
from app.domain.staff.primitives import StaffQualifications
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import ManagerAssignmentConflictError
from app.domain.store.manager_service import StoreManagerAssignmentService
from app.domain.store.primitives import (
    ContactInfo,
    StoreAddress,
    StoreAddressLine,
    StoreName,
    StoreNameKana,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.store import Store

#: 承認された全ドメインサービスの一覧（24件）。
EXPECTED_DOMAIN_SERVICES: frozenset[str] = frozenset(
    {
        "CorporateNameUniquenessService",
        "CounselorQualificationService",
        "CoverageSelectionService",
        "DispensingConsistencyService",
        "DispensingIterationUniquenessService",
        "DispensingPharmacistService",
        "InquiryPharmacistService",
        "InsurancePharmacyNumberUniquenessService",
        "LastAdministratorService",
        "MedicationHistoryUniquenessService",
        "MedicineEffectivePeriodConflictService",
        "NarcoticPrescriptionService",
        "PatientCoverageConflictService",
        "PatientMedicalProfileUniquenessService",
        "PatientMergeService",
        "PrescriptionDocumentNumberUniquenessService",
        "PublicExpenseBurdenService",
        "RefillEligibilityService",
        "StaffCodeUniquenessService",
        "StaffStoreAssignmentService",
        "StatutoryDispensingRecordService",
        "StoreCodeUniquenessService",
        "StoreManagerAssignmentService",
        "StoreNameUniquenessService",
    }
)

#: リポジトリProtocolの注入が許可された一意性ドメインサービスのホワイトリスト（5件）。
REPOSITORY_BACKED_SERVICES: frozenset[str] = frozenset(
    {
        "CorporateNameUniquenessService",
        "StoreNameUniquenessService",
        "StoreCodeUniquenessService",
        "InsurancePharmacyNumberUniquenessService",
        "StaffCodeUniquenessService",
    }
)

_FORBIDDEN_INFRA_MODULE_PREFIXES: tuple[str, ...] = (
    "sqlalchemy",
    "fastapi",
    "starlette",
    "pydantic",
    "asyncpg",
)


def _import_all_domain_modules() -> None:
    """app.domain 配下の全モジュールを走査してロードする。"""
    for module_info in pkgutil.walk_packages(
        app.domain.__path__, prefix=f"{app.domain.__name__}."
    ):
        importlib.import_module(module_info.name)


def _all_concrete_domain_services() -> list[type[object]]:
    """app.domain 配下の具象ドメインサービスクラスを列挙する。"""
    _import_all_domain_modules()
    services: list[type[object]] = []
    for modname, module in list(
        typing.cast(dict[str, Any], importlib.import_module("sys").modules).items()
    ):
        if modname.startswith("app.domain."):
            for name, val in vars(module).items():
                if (
                    isinstance(val, type)
                    and name.endswith("Service")
                    and val.__module__ == modname
                    and not inspect.isabstract(val)
                ):
                    services.append(val)
    return sorted(dict.fromkeys(services), key=lambda c: c.__name__)


def test_全ドメインサービスが網羅的に検出される() -> None:
    """TC-01: 全24件のドメインサービスが漏れなく走査され、承認一覧と完全一致すること。"""
    services = _all_concrete_domain_services()
    actual_names = {s.__name__ for s in services}

    assert actual_names == EXPECTED_DOMAIN_SERVICES, (
        f"ドメインサービスの一覧が想定と異なります。\n"
        f"余剰: {actual_names - EXPECTED_DOMAIN_SERVICES}\n"
        f"不足: {EXPECTED_DOMAIN_SERVICES - actual_names}"
    )


def test_純粋ドメインサービスが無状態である() -> None:
    """TC-02: 19件の純粋ドメインサービスが引数なしでインスタンス化でき、可変状態を持たないこと。"""
    services = _all_concrete_domain_services()
    pure_services = [
        s for s in services if s.__name__ not in REPOSITORY_BACKED_SERVICES
    ]

    assert len(pure_services) == 19, (
        f"純粋ドメインサービス数が19件ではありません: {len(pure_services)}"
    )

    for s in pure_services:
        instance = s()
        # インスタンス辞書に属性（内部状態）が一切存在しないこと
        instance_state = {
            k: v for k, v in instance.__dict__.items() if not k.startswith("__")
        }
        assert instance_state == {}, (
            f"{s.__name__} が内部状態 {instance_state} を保持しています。"
            "純粋ドメインサービスは無状態（Stateless）でなければなりません"
        )


def test_リポジトリ注入が許可された一意性サービスのみに限定されている() -> None:
    """TC-03: リポジトリの注入が許可されるのはホワイトリストの5件の一意性サービスのみであること。"""
    services = _all_concrete_domain_services()

    for s in services:
        init = getattr(s, "__init__", None)
        has_custom_init = bool(init and init is not object.__init__)

        if s.__name__ in REPOSITORY_BACKED_SERVICES:
            assert has_custom_init, (
                f"{s.__name__} はリポジトリ注入用の __init__ を持っていません"
            )
            hints = typing.get_type_hints(init)
            repo_params = [
                (k, v)
                for k, v in hints.items()
                if "repository" in k.lower() or "repository" in str(v).lower()
            ]
            assert repo_params, (
                f"{s.__name__} の __init__ にリポジトリ引数がありません: {hints}"
            )
        else:
            assert not has_custom_init, (
                f"{s.__name__} は純粋ドメインサービスですが、__init__ が定義されています。"
                "リポジトリ注入は一意性検証サービスのみに限定されます"
            )


def test_ドメインサービスがインフラ型に非依存である() -> None:
    """TC-04: ドメインサービスの型注釈にインフラストラクチャ型が含まれていないこと。"""
    services = _all_concrete_domain_services()
    violations: list[str] = []

    for s in services:
        for attr_name in dir(s):
            if attr_name.startswith("_"):
                continue
            attr = getattr(s, attr_name)
            if not callable(attr):
                continue
            hints = typing.get_type_hints(attr)
            for param_name, hint in hints.items():
                hint_str = str(hint)
                for forbidden in _FORBIDDEN_INFRA_MODULE_PREFIXES:
                    if forbidden in hint_str:
                        violations.append(
                            f"{s.__name__}.{attr_name}({param_name}: {hint_str}) が "
                            f"禁止されたインフラ型 {forbidden} を参照しています"
                        )

    assert not violations, (
        "ドメインサービスにインフラ型への依存が見つかりました:\n"
        + "\n".join(violations)
    )


def test_集約ルートがドメイン貧血症でないこと() -> None:
    """TC-05: 主要集約ルートが状態遷移メソッドを持ち、ドメイン貧血症に陥っていないこと。"""
    # ドメインサービスと連携する主要集約のドメインメソッド定義検証
    assert hasattr(Staff, "change_names") and callable(Staff.change_names)
    assert hasattr(Staff, "change_job_title") and callable(Staff.change_job_title)
    assert hasattr(Staff, "update_qualifications") and callable(
        Staff.update_qualifications
    )
    assert hasattr(Staff, "deactivate") and callable(Staff.deactivate)
    assert hasattr(Staff, "activate") and callable(Staff.activate)
    assert hasattr(Staff, "validate") and callable(Staff.validate)

    assert hasattr(Store, "change_status") and callable(Store.change_status)
    assert hasattr(Store, "revoke_closure") and callable(Store.revoke_closure)
    assert hasattr(Store, "opening_state_at") and callable(Store.opening_state_at)
    assert hasattr(Store, "validate") and callable(Store.validate)

    assert hasattr(Patient, "change_names") and callable(Patient.change_names)
    assert hasattr(Patient, "merge_into") and callable(Patient.merge_into)
    assert hasattr(Patient, "deactivate") and callable(Patient.deactivate)
    assert hasattr(Patient, "validate") and callable(Patient.validate)


def test_複数集約ドメインサービスが法人境界を保護する() -> None:
    """TC-06: StaffStoreAssignmentService, StoreManagerAssignmentService, PatientMergeService が法人境界を保護すること。"""
    corp_a = CorporateId.generate()
    corp_b = CorporateId.generate()

    # 1. StaffStoreAssignmentService による別法人店舗配属の拒否
    staff_a = Staff.create(
        corporate_id=corp_a,
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
        qualifications=StaffQualifications.empty(),
    )
    store_b = Store.create(
        corporate_id=corp_b,
        names=StoreNames(
            name=StoreName("別法人店舗"), kana=StoreNameKana("ベツホウジンテンポ")
        ),
        address=StoreAddress(
            postal_code=StorePostalCode("100-0001"),
            address=StoreAddressLine("東京都千代田区1-1"),
        ),
        contact_info=ContactInfo.create(phone_number=StorePhoneNumber("03-1234-5678")),
    )

    assignment_service = StaffStoreAssignmentService()
    today = datetime.date(2026, 9, 22)
    with pytest.raises(InvalidCorporateAssignmentError):
        assignment_service.assign_home_store(
            staff=staff_a, store=store_b, start_date=today
        )

    # 2. StoreManagerAssignmentService による別法人スタッフ任命の拒否
    store_a = Store.create(
        corporate_id=corp_a,
        names=StoreNames(
            name=StoreName("自法人店舗"), kana=StoreNameKana("ジホウジンテンポ")
        ),
        address=StoreAddress(
            postal_code=StorePostalCode("100-0001"),
            address=StoreAddressLine("東京都千代田区1-1"),
        ),
        contact_info=ContactInfo.create(phone_number=StorePhoneNumber("03-1234-5678")),
    )
    staff_b = Staff.create(
        corporate_id=corp_b,
        names=PersonNames.create(
            last_name="鈴木",
            first_name="一郎",
            last_name_kana="スズキ",
            first_name_kana="イチロウ",
        ),
        qualifications=StaffQualifications.empty(),
    )
    assignment = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=corp_a,
        store_id=store_a.id,
        staff_id=staff_b.id,
        person_id=AccountPersonId.generate(),
        period=ManagerAssignmentPeriod(starts_on=today),
    )
    manager_service = StoreManagerAssignmentService()
    with pytest.raises(ManagerAssignmentConflictError):
        manager_service.ensure_assignable(
            assignment=assignment, store=store_a, staff=staff_b
        )

    # 3. PatientMergeService による別法人患者統合の拒否
    patient_a = Patient.create(
        corporate_id=corp_a,
        names=PersonNames.create(
            last_name="佐藤",
            first_name="花子",
            last_name_kana="サトウ",
            first_name_kana="ハナコ",
        ),
        patient_number=PatientNumber(1),
    )
    patient_b = Patient.create(
        corporate_id=corp_b,
        names=PersonNames.create(
            last_name="佐藤",
            first_name="花子",
            last_name_kana="サトウ",
            first_name_kana="ハナコ",
        ),
        patient_number=PatientNumber(2),
    )
    merge_service = PatientMergeService()
    with pytest.raises(PatientStateConflictError):
        merge_service.merge(
            source=patient_b,
            target=patient_a,
            reason=PatientStatusReason("重複登録"),
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=datetime.datetime(2026, 9, 22, 10, 0, tzinfo=datetime.UTC),
        )
