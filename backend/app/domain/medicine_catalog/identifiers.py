"""medicine_catalogの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class MedicineCatalogEntryId(EntityUUID):
    """医薬品マスタ1行の一意識別子（UUIDv7）。

    ``MedicineIdentifier``（薬品コード）を同一性に使わない。同じ薬品コードでも
    収載期間の異なる行が複数存在しうるためで、コードを識別子にすると
    「いつ時点のマスタか」を表せなくなる。
    """

    identifier_name = "医薬品マスタ行ID"
