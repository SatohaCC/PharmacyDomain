"""NSIPS取込側が要求する業務操作の契約。具象Handlerへ依存しない。"""

from __future__ import annotations

from typing import Protocol

from app.application.dispensing.commands.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.commands.models import StartDispensingCommand
from app.application.patient.commands.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.commands.models import (
    RegisterPatientCommand,
    RegisterPatientExternalIdentifierCommand,
)
from app.application.prescription.commands.dtos.get_prescription import PrescriptionDto
from app.application.prescription.commands.models import (
    ReadyForDispensingCommand,
    RegisterPrescriptionCommand,
)
from app.domain.patient.identifiers import PatientId


class StartDispensingOperation(Protocol):
    async def execute(self, command: StartDispensingCommand) -> DispensingProcessDto:
        """更新に必要な認可・検証を行い、単一の業務操作を実行する。"""
        ...


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


class ReadyForDispensingOperation(Protocol):
    async def execute(self, command: ReadyForDispensingCommand) -> PrescriptionDto:
        """更新に必要な認可・検証を行い、単一の業務操作を実行する。"""
        ...


class RegisterPrescriptionOperation(Protocol):
    async def execute(self, command: RegisterPrescriptionCommand) -> PrescriptionDto:
        """更新に必要な認可・検証を行い、単一の業務操作を実行する。"""
        ...
