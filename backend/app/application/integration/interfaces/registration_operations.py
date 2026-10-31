"""NSIPS取込側が要求する業務操作の契約。具象Handlerへ依存しない。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.commands.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.commands.models import (
    RegisterPatientCommand,
    RegisterPatientExternalIdentifierCommand,
)
from app.domain.patient.identifiers import PatientId


class RegisterPatientOperation(Protocol):
    async def execute(self, command: RegisterPatientCommand) -> PatientId:
        """更新に必要な認可・検証を行い、単一の業務操作を実行する。"""
        ...


class RegisterPatientExternalIdentifierOperation(Protocol):
    async def execute(
        self, command: RegisterPatientExternalIdentifierCommand
    ) -> PatientExternalIdentifierDto:
        """更新に必要な認可・検証を行い、単一の業務操作を実行する。"""
        ...
