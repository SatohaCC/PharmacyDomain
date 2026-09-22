"""薬学的処方鑑査（相互作用・飲み合わせ機能）のドメインテスト。"""

from __future__ import annotations

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.prescription.interaction_audit import (
    DrugInteractionAuditService,
    DrugInteractionPair,
    InteractionSeverity,
)
from app.domain.shared.medicine import YjCode
from tests.fakes.fake_drug_interaction import FakeDrugInteractionDataSource


def test_yj_code_正常生成() -> None:
    """TC-01: 12桁英数字がNFKC正規化・大文字化され正常に生成されること。"""
    # 半角大文字
    code1 = YjCode("1179041F1025")
    assert code1.value == "1179041F1025"

    # 小文字から大文字への変換
    code2 = YjCode("1179041f1025")
    assert code2.value == "1179041F1025"

    # 全角英数からのNFKC正規化
    code3 = YjCode("１１７９０４１Ｆ１０２５")
    assert code3.value == "1179041F1025"


@pytest.mark.parametrize(
    "invalid_code",
    [
        "",  # 空文字
        "   ",  # 空白のみ
        "1179041F102",  # 11桁（不足）
        "1179041F10250",  # 13桁（超過）
        "1179041F-025",  # ハイフン混入
        "1179041F#025",  # 記号混入
    ],
)
def test_yj_code_不正形式の拒否(invalid_code: str) -> None:
    """TC-02: 12桁英数字以外の不正な形式はDomainValidationErrorで拒否されること。"""
    with pytest.raises(DomainValidationError):
        YjCode(invalid_code)


@pytest.mark.asyncio
async def test_単剤または0剤の組み合わせ判定() -> None:
    """TC-03: 0剤または1剤の入力では組み合わせペアが0件であること。"""
    service = DrugInteractionAuditService()
    fake_ds = FakeDrugInteractionDataSource()

    # 0剤
    result_empty = await service.audit([], fake_ds)
    assert result_empty.target_yj_codes == ()
    assert result_empty.pairs == ()
    assert result_empty.total_combinations == 0

    # 1剤
    code_a = YjCode("1179041F1025")
    result_single = await service.audit([code_a], fake_ds)
    assert result_single.target_yj_codes == (code_a,)
    assert result_single.pairs == ()
    assert result_single.total_combinations == 0


@pytest.mark.asyncio
async def test_多剤の全組み合わせ網羅生成() -> None:
    """TC-04: 2剤(1ペア)、3剤(3ペア)、5剤(10ペア)の全組み合わせが網羅生成されること。"""
    service = DrugInteractionAuditService()
    fake_ds = FakeDrugInteractionDataSource()

    c1 = YjCode("1111111A1000")
    c2 = YjCode("2222222B2000")
    c3 = YjCode("3333333C3000")
    c4 = YjCode("4444444D4000")
    c5 = YjCode("5555555E5000")

    # 2剤 -> 1ペア
    res_2 = await service.audit([c1, c2], fake_ds)
    assert res_2.total_combinations == 1
    assert len(res_2.pairs) == 1

    # 3剤 -> 3ペア
    res_3 = await service.audit([c1, c2, c3], fake_ds)
    assert res_3.total_combinations == 3
    assert len(res_3.pairs) == 3

    # 5剤 -> 10ペア
    res_5 = await service.audit([c1, c2, c3, c4, c5], fake_ds)
    assert res_5.total_combinations == 10
    assert len(res_5.pairs) == 10


@pytest.mark.asyncio
async def test_ペアの対称性と重複排除() -> None:
    """TC-05: 入力順序によらず辞書順で正規化され、同一コードの重複が排除されること。"""
    service = DrugInteractionAuditService()
    fake_ds = FakeDrugInteractionDataSource()

    cA = YjCode("1111111A1000")
    cB = YjCode("2222222B2000")

    # [A, B] と [B, A]
    res_ab = await service.audit([cA, cB], fake_ds)
    res_ba = await service.audit([cB, cA], fake_ds)

    assert len(res_ab.pairs) == 1
    assert len(res_ba.pairs) == 1
    assert res_ab.pairs[0].medicine_a == cA
    assert res_ab.pairs[0].medicine_b == cB
    assert res_ba.pairs[0].medicine_a == cA
    assert res_ba.pairs[0].medicine_b == cB

    # 重複 [A, B, A] -> 2剤扱い（1ペア）
    res_dup = await service.audit([cA, cB, cA], fake_ds)
    assert len(res_dup.pairs) == 1
    assert res_dup.target_yj_codes == (cA, cB)


@pytest.mark.asyncio
async def test_相互作用重大度と臨床情報の突合() -> None:
    """TC-06: 既知の併用禁忌・併用注意・報告なしペアが正しく判定されること。"""
    c_warfarin = YjCode("3339001F1023")  # ワルファリン
    c_miconazole = YjCode("6290001F1028")  # ミコナゾール（併用禁忌）
    c_aspirin = YjCode("1149001F1020")  # アスピリン（併用注意）
    c_paracetamol = YjCode("1141001F1021")  # アセトアミノフェン（相互作用なし）

    fake_ds = FakeDrugInteractionDataSource()
    # 併用禁忌ペアを登録
    fake_ds.register_interaction(
        DrugInteractionPair(
            medicine_a=c_warfarin,
            medicine_b=c_miconazole,
            severity=InteractionSeverity.CONTRAINDICATED,
            clinical_condition="重篤な出血症状の出現",
            mechanism="ミコナゾールがCYP2C9を阻害しワルファリン血中濃度が著しく上昇",
            recommendation="併用を避けること（併用禁忌）",
        )
    )
    # 併用注意ペアを登録
    fake_ds.register_interaction(
        DrugInteractionPair(
            medicine_a=c_warfarin,
            medicine_b=c_aspirin,
            severity=InteractionSeverity.PRECAUTION,
            clinical_condition="抗凝固作用の増強による出血リスク増大",
            mechanism="血小板凝集抑制作用および消化管粘膜障害の相加",
            recommendation="血液凝固能検査を実施し用量調整を行うこと",
        )
    )

    service = DrugInteractionAuditService()
    # 4剤で鑑査（6ペア生成）
    result = await service.audit(
        [c_warfarin, c_miconazole, c_aspirin, c_paracetamol], fake_ds
    )
    assert result.total_combinations == 6

    # 併用禁忌の検証
    contra_pairs = [
        p for p in result.pairs if p.severity == InteractionSeverity.CONTRAINDICATED
    ]
    assert len(contra_pairs) == 1
    assert contra_pairs[0].clinical_condition == "重篤な出血症状の出現"

    # 併用注意の検証
    precaution_pairs = [
        p for p in result.pairs if p.severity == InteractionSeverity.PRECAUTION
    ]
    assert len(precaution_pairs) == 1
    assert (
        precaution_pairs[0].clinical_condition == "抗凝固作用の増強による出血リスク増大"
    )

    # 相互作用なしの検証（残り4ペア）
    none_pairs = [p for p in result.pairs if p.severity == InteractionSeverity.NONE]
    assert len(none_pairs) == 4


@pytest.mark.asyncio
async def test_監査結果の集計とフィルタ() -> None:
    """TC-07: 集計プロパティおよびフィルタリングメソッドが正しく動作すること。"""
    cA = YjCode("1111111A1000")
    cB = YjCode("2222222B2000")
    cC = YjCode("3333333C3000")

    fake_ds = FakeDrugInteractionDataSource()
    # AとB: 併用禁忌
    fake_ds.register_interaction(
        DrugInteractionPair(
            medicine_a=cA,
            medicine_b=cB,
            severity=InteractionSeverity.CONTRAINDICATED,
            clinical_condition="併用禁忌事象",
        )
    )
    # AとC: 併用注意
    fake_ds.register_interaction(
        DrugInteractionPair(
            medicine_a=cA,
            medicine_b=cC,
            severity=InteractionSeverity.PRECAUTION,
            clinical_condition="併用注意事象",
        )
    )
    # BとC: 相互作用なし（未登録）

    service = DrugInteractionAuditService()
    result = await service.audit([cA, cB, cC], fake_ds)

    assert result.total_combinations == 3
    assert result.contraindicated_count == 1
    assert result.precaution_count == 1
    assert result.has_contraindications is True
    assert result.has_precautions is True

    assert len(result.contraindicated_pairs()) == 1
    assert len(result.precaution_pairs()) == 1


def test_サービスが無状態であること() -> None:
    """TC-08: DrugInteractionAuditServiceが無状態（Stateless）であること。"""
    service = DrugInteractionAuditService()
    state = {k: v for k, v in service.__dict__.items() if not k.startswith("__")}
    assert state == {}, (
        "DrugInteractionAuditServiceに内部可変状態が存在してはなりません"
    )
