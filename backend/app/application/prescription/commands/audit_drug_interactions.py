"""Applicationのaudit_drug_interactionsを定義する。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.access_control.boundary_models import ActorContext
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.prescription.commands.dtos.audit_interactions import (
    DrugInteractionAuditReportDto,
    DrugInteractionPairDto,
)
from app.domain.prescription.primitives import YjCode
from app.domain.prescription.repositories import DrugInteractionDataSource
from app.domain.prescription.services import DrugInteractionAuditService


@dataclass(frozen=True, kw_only=True)
class AuditDrugInteractionsCommand:
    """相互作用鑑査実行コマンド。"""

    yj_codes: Sequence[str]


class AuditDrugInteractionsUseCase:
    """複数のYJコードから全組み合わせの相互作用を鑑査するユースケース。"""

    def __init__(
        self,
        *,
        authorization_service: AuthorizationService,
        data_source: DrugInteractionDataSource,
        audit_service: DrugInteractionAuditService | None = None,
    ) -> None:
        self._auth = authorization_service
        self._data_source = data_source
        self._audit_service = audit_service or DrugInteractionAuditService()

    async def execute(
        self, actor: ActorContext, command: AuditDrugInteractionsCommand
    ) -> DrugInteractionAuditReportDto:
        """相互作用鑑査を実行する。"""
        if not actor.roles:
            raise AuthorizationError(
                f"操作主体 '{actor.principal_id}' には権限がありません。"
            )
        yj_codes = [YjCode(code) for code in command.yj_codes]
        result = await self._audit_service.audit(
            yj_codes=yj_codes, data_source=self._data_source
        )
        pairs_dto = [
            DrugInteractionPairDto(
                medicine_a=p.medicine_a.value,
                medicine_b=p.medicine_b.value,
                severity=p.severity.value,
                severity_label=p.severity.label,
                clinical_condition=p.clinical_condition.value,
                mechanism=p.mechanism.value,
                recommendation=p.recommendation.value,
            )
            for p in result.pairs
        ]
        return DrugInteractionAuditReportDto(
            target_yj_codes=[code.value for code in result.target_yj_codes],
            total_combinations=result.total_combinations,
            contraindicated_count=result.contraindicated_count,
            precaution_count=result.precaution_count,
            has_contraindications=result.has_contraindications,
            has_precautions=result.has_precautions,
            pairs=pairs_dto,
        )
