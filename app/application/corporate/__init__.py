"""法人（`corporate`）コンテキストのアプリケーションサービスと DTO。

`CorporateAccessService` はここに実装がありますが、Store / Staff のユースケースは
この具象クラスではなく `app.application.access_control.CorporateAccessBoundary`
（Protocol）にだけ依存します。実装を import するのは Composition Root とテストだけです。
"""

from app.application.corporate.change_corporate_name import (
    ChangeCorporateNameCommand,
    ChangeCorporateNameUseCase,
)
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusCommand,
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.change_representative import (
    ChangeRepresentativeCommand,
    ChangeRepresentativeUseCase,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.exceptions import (
    CorporateApplicationError,
    CorporateInactiveError,
    CorporateNotFoundError,
)
from app.application.corporate.get_corporate import (
    CorporateResponseDto,
    GetCorporateUseCase,
)
from app.application.corporate.register_corporate import (
    RegisterCorporateCommand,
    RegisterCorporateUseCase,
)
from app.application.corporate.support import (
    load_active_corporate_or_raise,
    load_corporate_or_raise,
)

__all__ = [
    "ChangeCorporateNameCommand",
    "ChangeCorporateNameUseCase",
    "ChangeCorporateStatusCommand",
    "ChangeCorporateStatusUseCase",
    "ChangeRepresentativeCommand",
    "ChangeRepresentativeUseCase",
    "CorporateAccessService",
    "CorporateApplicationError",
    "CorporateInactiveError",
    "CorporateNotFoundError",
    "CorporateResponseDto",
    "GetCorporateUseCase",
    "RegisterCorporateCommand",
    "RegisterCorporateUseCase",
    "load_active_corporate_or_raise",
    "load_corporate_or_raise",
]
