"""Applicationのupdate_corporate_policyを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.corporate.commands.services.support import (
    load_corporate_or_raise,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.repositories import CorporateRepository
from app.domain.corporate.value_objects import CorporatePolicy, PolicySetting


@dataclass(frozen=True, kw_only=True)
class PolicySettingInput:
    """ポリシー単一項目の更新入力。"""

    value: bool
    overridable: bool


@dataclass(frozen=True, kw_only=True)
class UpdateCorporatePolicyCommand:
    """法人ポリシー更新の入力データ。"""

    corporate_id: str
    require_prescription_audit: PolicySettingInput
    prohibit_self_verification: PolicySettingInput


class UpdateCorporatePolicyUseCase:
    """法人ポリシーを更新する。"""

    def __init__(
        self,
        repository: CorporateRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdateCorporatePolicyCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_CORPORATE
        )
        corporate = await load_corporate_or_raise(self._repository, corporate_id)
        new_policy = CorporatePolicy(
            require_prescription_audit=PolicySetting(
                value=command.require_prescription_audit.value,
                overridable=command.require_prescription_audit.overridable,
            ),
            prohibit_self_verification=PolicySetting(
                value=command.prohibit_self_verification.value,
                overridable=command.prohibit_self_verification.overridable,
            ),
        )
        corporate = corporate.change_policy(new_policy)
        await self._repository.save(corporate)
