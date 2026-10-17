"""薬歴・頭書き・指導記録の公開識別子。"""

from __future__ import annotations

from typing import ClassVar

from app.domain.foundation.primitives.identifiers import EntityUUID


class MedicationHistoryRecordId(EntityUUID):
    """薬歴指導記録集約の一意識別子（UUIDv7）。"""

    identifier_name = "薬歴ID"


class PatientMedicalProfileId(EntityUUID):
    """患者医療プロファイル（頭書き）集約の一意識別子（UUIDv7）。

    ``PatientId`` を流用しない。他集約のIDを自分のIDにすると、患者の統合・削除が
    起きたときにプロファイルの同一性をどう扱うかが決まらなくなる。患者との
    1:1関係は ``patient_id`` の一意制約（Repository契約）で表す。
    """

    identifier_name = "頭書きID"


class CategoryCatalogId(EntityUUID):
    """薬歴記載区分カタログ集約の一意識別子（UUIDv7）。"""

    identifier_name = "区分カタログID"


class FollowUpId(EntityUUID):
    """服薬期間中のフォローアップ記録を一意に識別するID（UUIDv7）。"""

    identifier_name = "フォローアップID"


class TracingReportId(EntityUUID):
    """トレーシングレポートの一意識別子。"""

    identifier_name: ClassVar[str] = "トレーシングレポートID"
