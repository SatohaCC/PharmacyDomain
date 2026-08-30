from app.domain.foundation.exceptions import DomainError


class StaffDomainError(DomainError):
    """スタッフドメインの基底例外（他の例外はこのクラスを継承する）"""

    default_message = "スタッフドメインでエラーが発生しました。"
    default_code = "STAFF_DOMAIN_ERROR"


class StaffCodeAlreadyExistsError(StaffDomainError):
    """スタッフコードが重複している場合の例外。"""

    default_message = "同一法人内に同じスタッフコードのスタッフが既に登録されています。"

    # 💡 修正：フロントエンドが識別できる一意のコードにする
    default_code = "STAFF_CODE_ALREADY_EXISTS"


class StaffNotFoundError(StaffDomainError):
    """スタッフが見つからない場合の例外。"""

    default_message = "指定されたスタッフが見つかりません。"
    default_code = "STAFF_NOT_FOUND"


class InvalidCorporateAssignmentError(StaffDomainError):
    """自法人以外の店舗・データを紐付けようとした場合の例外（セキュリティ・ドメイン違反）"""

    default_message = "別法人の店舗を割り当てることはできません。"
    default_code = "INVALID_CORPORATE_ASSIGNMENT"


class StaffAffiliationError(StaffDomainError):
    """所属履歴に関する業務ルール違反の基底例外"""

    default_code = "INVALID_AFFILIATION"


class AffiliationDateConflictError(StaffAffiliationError):
    """異動日などの日付に矛盾がある場合のエラー"""

    default_code = "AFFILIATION_DATE_CONFLICT"


class ConcurrentStoreConflictError(StaffAffiliationError):
    """同一店舗の所属期間が主所属・兼務をまたいで重なる場合のエラー

    日付単位ではなく所属期間（閉区間）の重なりに対して、集約の構築時に送出する。
    """

    default_message = (
        "同一店舗の所属期間が重複しています。"
        "異動する場合は対象店舗の兼務を先に解除してください。"
    )
    default_code = "CONCURRENT_STORE_CONFLICT"


class PrimaryAffiliationDuplicationError(StaffAffiliationError):
    """主所属店舗の所属期間が重複する場合のエラー

    日付単位ではなく所属期間（閉区間）の重なりに対して、集約の構築時に送出する。
    """

    default_message = "主所属店舗の所属期間が重複しています。"
    default_code = "PRIMARY_AFFILIATION_DUPLICATION"


class InactiveStaffAssignmentError(StaffAffiliationError):
    """無効化済み（退職等）のスタッフへ新しい所属を追加しようとした場合のエラー

    無効化は継続中の所属をすべて退職日で閉じるため、その後に無期限の所属を
    足せると「退職しているのに所属し続けている」状態が復活する。過去日の
    所属を後から記録したい場合は、有効化してから所属を追加し、改めて
    無効化する。
    """

    default_message = (
        "無効化されたスタッフに店舗所属を追加することはできません。"
        "先にスタッフを有効化してください。"
    )
    default_code = "INACTIVE_STAFF_ASSIGNMENT"
