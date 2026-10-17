"""業務イベントドメインの例外。"""

from app.domain.foundation.exceptions import DomainError


class CareEventDomainError(DomainError):
    """業務イベントの規則に反する場合の基底例外。"""

    default_message = "業務イベントの規則に反しています。"
    default_code = "CARE_EVENT_DOMAIN_ERROR"


class EventDefinitionAlreadyExistsError(CareEventDomainError):
    """同じ法人に同名の有効なEvent定義がある。"""

    default_message = "同名の有効なイベント種別があります。"
    default_code = "EVENT_DEFINITION_ALREADY_EXISTS"


class EventAlreadyAssociatedError(CareEventDomainError):
    """1つの受付に複数のEventを関連付けようとした。"""

    default_message = "受付にはすでにEventが関連付いています。"
    default_code = "EVENT_ALREADY_ASSOCIATED"
