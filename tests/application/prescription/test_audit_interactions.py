"""相互作用鑑査ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.access_control import ActorContext, AuthorizationService
from app.application.prescription.audit_interactions import (
    AuditDrugInteractionsCommand,
    AuditDrugInteractionsUseCase,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.prescription.interaction_audit import (
    DrugInteractionPair,
    InteractionSeverity,
)
from app.domain.shared.medicine import YjCode
from tests.application.access_helpers import create_vendor_authorization
from tests.fakes.fake_drug_interaction import FakeDrugInteractionDataSource


@pytest.fixture
def auth_service() -> AuthorizationService:
    return create_vendor_authorization()


@pytest.fixture
def actor() -> ActorContext:
    return ActorContext.vendor_system_admin(principal_id="test-admin")


@pytest.mark.asyncio
async def test_ユースケース正常系(
    auth_service: AuthorizationService, actor: ActorContext
) -> None:
    """TC-09: 複数YJコード文字列をCommandに渡し、全組み合わせの鑑査結果DTOが返却されること。"""
    c1 = "1179041F1025"  # ロキソプロフェン
    c2 = "2149001F1020"  # アスピリン
    c3 = "3339001F1023"  # ワルファリン

    fake_ds = FakeDrugInteractionDataSource()
    # c2 と c3 は併用注意
    fake_ds.register_interaction(
        DrugInteractionPair(
            medicine_a=YjCode(c2),
            medicine_b=YjCode(c3),
            severity=InteractionSeverity.PRECAUTION,
            clinical_condition="出血傾向の増大",
            mechanism="抗凝固作用の増強",
            recommendation="用量調整と出血症状のモニタリング",
        )
    )

    use_case = AuditDrugInteractionsUseCase(
        authorization_service=auth_service,
        data_source=fake_ds,
    )
    command = AuditDrugInteractionsCommand(yj_codes=[c1, c2, c3])

    report = await use_case.execute(actor=actor, command=command)

    assert report.total_combinations == 3
    assert report.precaution_count == 1
    assert report.contraindicated_count == 0
    assert report.has_precautions is True
    assert report.has_contraindications is False
    assert len(report.pairs) == 3

    # ペアDTOの内容検証
    precaution_dto = next(p for p in report.pairs if p.severity == "precaution")
    assert precaution_dto.severity_label == "併用注意"
    assert precaution_dto.clinical_condition == "出血傾向の増大"


@pytest.mark.asyncio
async def test_ユースケース不正YJコード拒否(
    auth_service: AuthorizationService, actor: ActorContext
) -> None:
    """TC-10: 形式不正なYJコード文字列が含まれる場合、バリデーションエラーとなること。"""
    use_case = AuditDrugInteractionsUseCase(
        authorization_service=auth_service,
        data_source=FakeDrugInteractionDataSource(),
    )
    command = AuditDrugInteractionsCommand(yj_codes=["INVALID_CODE", "1179041F1025"])

    with pytest.raises(DomainValidationError):
        await use_case.execute(actor=actor, command=command)
