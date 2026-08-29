"""薬歴・頭書きのリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId


class MedicationHistoryRepository(Protocol):
    """薬歴指導記録集約を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """指定法人の薬歴を取得する。

        他法人の薬歴は存在を隠すため ``None`` を返す（403ではなく404相当）。
        """
        ...

    async def get_by_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> MedicationHistoryRecord | None:
        """調剤セッションに紐付く**確定済**の薬歴を取得する。

        下書きは複数あってもよいので、確定済だけを返す。確定済は
        :meth:`save` の契約により1件以下なので一意に定まる。
        """
        ...

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを ``counseled_at`` 降順で返す。

        画面は新しい順に見るため降順にする。頭書きの再構築は昇順に畳み込むが、
        並べ替えは ``PatientMedicalProfile.rebuild_from()`` 側が行うので、
        呼び出し順に依存しない。
        """
        ...

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。

        同一法人・同一 ``dispensing_id`` で ``FINALIZED`` の薬歴が2件以上に
        ならないよう、同じ集約IDを除外した上で拒否し、
        ``MedicationHistoryAlreadyExistsError`` を送出する。1回の調剤に対する
        指導記録が二重になると、服薬管理指導料の算定も頭書きの投影も二重になる。

        下書き（``DRAFT``）は制限しない。書きかけを複数持つのは正当である。
        Applicationの事前readは早期エラー用であり原子性の代替ではない。
        """
        ...


class PatientMedicalProfileRepository(Protocol):
    """患者医療プロファイル（頭書き）集約を永続化・検索するための操作インターフェース。"""

    async def get_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile | None:
        """患者の頭書きを取得する。

        ``None`` は欠損ではなく「まだ投影されていない」を意味する。呼び出し側は
        ``PatientMedicalProfile.empty_for()`` を作ってから畳み込んでよい。
        """
        ...

    async def save(self, profile: PatientMedicalProfile) -> None:
        """患者ごとに1件であることを原子的に保証して頭書きを保存する。

        同一法人・同一 ``patient_id`` の重複を、同じ集約IDを除外した上で拒否し、
        ``PatientMedicalProfileAlreadyExistsError`` を送出する。頭書きが2件あると、
        どちらが投影結果かが決まらなくなる。

        患者との1:1関係を ``PatientMedicalProfileId`` ではなく ``patient_id`` の
        一意制約で表すのは、``PatientExternalIdentifier`` と同じ作法である。
        """
        ...
