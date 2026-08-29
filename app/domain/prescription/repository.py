"""処方箋のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionId,
)


class PrescriptionRepository(Protocol):
    """処方箋集約を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription | None:
        """指定法人の処方箋を取得する。

        他法人の処方箋は存在を隠すため ``None`` を返す（403ではなく404相当）。
        """
        ...

    async def get_by_document_number(
        self,
        *,
        corporate_id: CorporateId,
        document_number: PrescriptionDocumentNumber,
    ) -> Prescription | None:
        """引換番号や処方箋番号から処方箋を取得する。

        紙処方箋の番号は医療機関ごとの採番なので法人内で衝突しうる。
        衝突しているときにどれを返すかは規定しない（電子処方箋の引換番号は
        :meth:`save` の契約により法人内で一意なので、一意に定まる）。
        他法人の処方箋は ``None`` を返す。
        """
        ...

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[Prescription]:
        """指定法人・患者の処方箋一覧を取得する。"""
        ...

    async def save(self, prescription: Prescription) -> None:
        """引換番号の重複を原子的に拒否して処方箋を保存する。

        **電子処方箋（``PrescriptionSourceType.ELECTRONIC``）のときだけ**、
        同一法人内で ``document_number`` が重複する行を拒否し、
        ``PrescriptionDocumentNumberAlreadyExistsError`` を送出する。
        引換番号は電子処方箋管理サービスが発行する一意な番号であり、
        重複は二重取り込みを意味するため。

        紙処方箋（``PAPER_QR``）の番号は医療機関ごとの採番なので、
        別の医療機関が同じ番号を採番しうる。一意性を課すと正当な処方箋を
        拒否するため課さない。

        同じ集約IDの現在行は重複候補から除外し、自身の状態変更を妨げない。
        Applicationの事前readは早期エラー用であり原子性の代替ではない。

        読み込みから保存までの間に同じ集約が別トランザクションで更新されて
        いた場合、上書きせずに ``ConcurrentModificationError`` を送出する。
        同時更新が起こりえない実装（インメモリなど）では送出されない。
        """
        ...
