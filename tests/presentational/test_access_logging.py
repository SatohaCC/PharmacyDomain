"""閲覧と失敗要求の記録が操作者を偽らず秘密を含めない。"""

import logging
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.presentational.dependencies import (
    STATE_ATTRIBUTE,
    PresentationState,
    get_corporate_use_cases,
)
from tests.fakes.stub_actor_context_provider import StubActorContextProvider
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api


def _actor(api: Api) -> ResolvedActorContext:
    actor = ResolvedActorContext(
        principal_id="検証済み操作者",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )
    app = cast(FastAPI, api.client.app)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(actor_provider=StubActorContextProvider(actor)),
    )
    return actor


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    records = [record for record in caplog.records if record.name == "pharmacy.access"]
    assert len(records) == 1
    return records


def test_閲覧ログへ信頼済み本人と対象と結果を記録する(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    actor = _actor(api)
    created = api.client.post(
        "/corporates",
        headers=AUTHORIZED_HEADERS,
        json={
            "name": "閲覧対象法人",
            "representative_last_name": "山田",
            "representative_first_name": "太郎",
        },
    )
    assert created.status_code == 201
    corporate_id = str(created.json()["id"])
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="pharmacy.access"):
        response = api.client.get(
            f"/corporates/{corporate_id}", headers=AUTHORIZED_HEADERS
        )
    assert response.status_code == 200
    record = _records(caplog)[0]
    assert record.__dict__["person_id"] == str(actor.person_id.value)
    assert record.__dict__["account_id"] == str(actor.account_id.value)
    assert record.__dict__["status_code"] == 200
    assert record.__dict__["resource_id"] == corporate_id


def test_未存在への要求でも本人と失敗結果がログへ残る(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    actor = _actor(api)
    with caplog.at_level(logging.INFO, logger="pharmacy.access"):
        response = api.client.get(
            f"/corporates/{CorporateId.generate().value}", headers=AUTHORIZED_HEADERS
        )
    assert response.status_code == 404
    record = _records(caplog)[0]
    assert record.__dict__["person_id"] == str(actor.person_id.value)
    assert record.__dict__["status_code"] == 404


def test_本人未確認の要求は申告された人物を操作者として記録しない(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    claimed_person = str(AccountPersonId.generate().value)
    secret = "絶対にログへ残してはいけない招待秘密"
    with caplog.at_level(logging.INFO, logger="pharmacy.access"):
        response = api.client.post(
            "/corporates",
            headers={"Authorization": "Bearer forged-secret-token"},
            json={"person_id": claimed_person, "name": secret},
        )
    assert response.status_code == 401
    record = _records(caplog)[0]
    assert record.__dict__["person_id"] is None
    assert record.__dict__["account_id"] is None
    assert record.__dict__["status_code"] == 401
    serialized = repr(record.__dict__)
    assert claimed_person not in serialized
    assert secret not in serialized
    assert "forged-secret-token" not in serialized


def test_処理中の例外も失敗ログへ残す(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    actor = _actor(api)
    app = cast(FastAPI, api.client.app)

    def fail() -> None:
        raise RuntimeError("内部障害")

    app.dependency_overrides[get_corporate_use_cases] = fail
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="pharmacy.access"):
        response = client.get(
            f"/corporates/{CorporateId.generate().value}", headers=AUTHORIZED_HEADERS
        )
    assert response.status_code == 500
    record = _records(caplog)[0]
    assert record.__dict__["person_id"] == str(actor.person_id.value)
    assert record.__dict__["status_code"] == 500
