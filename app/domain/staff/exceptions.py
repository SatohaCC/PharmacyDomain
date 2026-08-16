from app.base.domain.exceptions import DomainError


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
    """主所属と兼務店舗の指定に矛盾がある場合のエラー"""

    default_code = "CONCURRENT_STORE_CONFLICT"


class PrimaryAffiliationDuplicationError(StaffAffiliationError):
    """主所属店舗が同日に複数存在してしまう場合のエラー"""

    default_code = "PRIMARY_AFFILIATION_DUPLICATION"
