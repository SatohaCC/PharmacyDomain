"""スタッフ・患者・資格・受付・医薬品マスタのHTTPルートの振る舞い。

型検査はCommandの項目名と型しか見ないので、「どの本文項目をどのCommand項目へ
渡したか」の取り違えは通ってしまう（``store_id`` を ``new_store_id`` へ渡す等）。
往復させて結果を見ることでそこを固定する。
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from tests.presentational.conftest import AUTHORIZED_HEADERS, Api

_CORPORATE_BODY = {
    "name": "サンプル法人",
    "representative_last_name": "山田",
    "representative_first_name": "太郎",
}
_STORE_BODY = {
    "name": "サンプル薬局",
    "name_kana": "サンプルヤッキョク",
    "postal_code": "1234567",
    "address": "東京都千代田区1-2-3",
    "phone_number": "03-1234-5678",
}
_STAFF_BODY = {
    "last_name": "鈴木",
    "first_name": "花子",
    "last_name_kana": "スズキ",
    "first_name_kana": "ハナコ",
}
_PATIENT_BODY = {
    "last_name": "佐藤",
    "first_name": "一郎",
    "last_name_kana": "サトウ",
    "first_name_kana": "イチロウ",
    "birth_date": "1980-05-06",
}
_COVERAGE_BODY = {
    "coverage_type": "insurance",
    "valid_from": "2026-04-01",
    "activated_on": "2026-04-01",
    "insurer_number": "012345",
    "insured_symbol": "サンプル記号",
    "insured_number": "12345",
    "insured_type": "self",
    "benefit_ratio": 70,
}
_MEDICINE_BODY = {
    "code_type": "yj",
    "code": "1234567F1023",
    "name": "サンプル錠10mg",
    "unit": "錠",
    "dosage_form": "tablet",
    "listed_on": "2020-04-01",
    "catalog_version": "2026-04-01",
}


def _post(api: Api, path: str, body: dict[str, Any], expected: int = 201) -> Any:
    response = api.client.post(path, json=body, headers=AUTHORIZED_HEADERS)
    assert response.status_code == expected, response.text
    return response.json()


def _corporate(api: Api) -> str:
    corporate_id: str = _post(api, "/corporates", _CORPORATE_BODY)["id"]
    return corporate_id


def _store(api: Api, corporate_id: str) -> str:
    store_id: str = _post(api, f"/corporates/{corporate_id}/stores", _STORE_BODY)["id"]
    return store_id


def _patient(api: Api, corporate_id: str) -> str:
    patient_id: str = _post(api, f"/corporates/{corporate_id}/patients", _PATIENT_BODY)[
        "id"
    ]
    return patient_id


# --- スタッフ ---------------------------------------------------------------


def test_スタッフを登録して_主所属つきで取得できる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    store_id = _store(api, corporate_id)

    # Act
    staff_id = _post(
        api,
        f"/corporates/{corporate_id}/staffs",
        {
            **_STAFF_BODY,
            "job_title": "管理薬剤師",
            "pharmacist_license_number": "123456",
            "initial_home_store_id": store_id,
            "initial_start_date": "2026-04-01",
        },
    )["id"]
    detail = api.client.get(
        f"/corporates/{corporate_id}/staffs/{staff_id}",
        params={"target_date": "2026-04-02"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    body = detail.json()
    assert detail.status_code == HTTPStatus.OK
    assert body["last_name"] == "鈴木"
    assert body["job_title"] == "管理薬剤師"
    assert body["is_pharmacist"] is True
    assert body["current_home_store_id"] == store_id


def test_主所属の異動は_異動日から新店舗になる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    first_store_id = _store(api, corporate_id)
    second_store_id = _post(
        api,
        f"/corporates/{corporate_id}/stores",
        {**_STORE_BODY, "name": "第二薬局"},
    )["id"]
    staff_id = _post(
        api,
        f"/corporates/{corporate_id}/staffs",
        {
            **_STAFF_BODY,
            "initial_home_store_id": first_store_id,
            "initial_start_date": "2026-04-01",
        },
    )["id"]

    # Act
    transferred = api.client.patch(
        f"/corporates/{corporate_id}/staffs/{staff_id}/home-store",
        json={"store_id": second_store_id, "transfer_date": "2026-07-01"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert: 異動前後で引ける主所属が変わる（本文の項目が取り違えられていない）。
    assert transferred.status_code == HTTPStatus.NO_CONTENT
    before = api.client.get(
        f"/corporates/{corporate_id}/staffs/{staff_id}",
        params={"target_date": "2026-06-30"},
        headers=AUTHORIZED_HEADERS,
    ).json()
    after = api.client.get(
        f"/corporates/{corporate_id}/staffs/{staff_id}",
        params={"target_date": "2026-07-01"},
        headers=AUTHORIZED_HEADERS,
    ).json()
    assert before["current_home_store_id"] == first_store_id
    assert after["current_home_store_id"] == second_store_id


def test_退職すると_退職日以降の主所属が引けなくなる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    store_id = _store(api, corporate_id)
    staff_id = _post(
        api,
        f"/corporates/{corporate_id}/staffs",
        {
            **_STAFF_BODY,
            "initial_home_store_id": store_id,
            "initial_start_date": "2026-04-01",
        },
    )["id"]

    # Act
    retired = api.client.post(
        f"/corporates/{corporate_id}/staffs/{staff_id}/retirement",
        json={"retired_on": "2026-06-30"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert: 退職日以前は引けたまま、以降は引けない。
    assert retired.status_code == HTTPStatus.NO_CONTENT
    on_duty = api.client.get(
        f"/corporates/{corporate_id}/staffs/{staff_id}",
        params={"target_date": "2026-06-30"},
        headers=AUTHORIZED_HEADERS,
    ).json()
    after = api.client.get(
        f"/corporates/{corporate_id}/staffs/{staff_id}",
        params={"target_date": "2026-07-01"},
        headers=AUTHORIZED_HEADERS,
    ).json()
    assert on_duty["current_home_store_id"] == store_id
    assert on_duty["is_active"] is False
    assert after["current_home_store_id"] is None


def test_兼務は_終了日をクエリで受け取って解除する(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    home_store_id = _store(api, corporate_id)
    concurrent_store_id = _post(
        api, f"/corporates/{corporate_id}/stores", {**_STORE_BODY, "name": "兼務薬局"}
    )["id"]
    staff_id = _post(
        api,
        f"/corporates/{corporate_id}/staffs",
        {
            **_STAFF_BODY,
            "initial_home_store_id": home_store_id,
            "initial_start_date": "2026-04-01",
        },
    )["id"]
    assigned = api.client.post(
        f"/corporates/{corporate_id}/staffs/{staff_id}/concurrent-stores",
        json={"store_id": concurrent_store_id, "start_date": "2026-05-01"},
        headers=AUTHORIZED_HEADERS,
    )
    assert assigned.status_code == HTTPStatus.NO_CONTENT, assigned.text

    # Act
    removed = api.client.delete(
        f"/corporates/{corporate_id}/staffs/{staff_id}"
        f"/concurrent-stores/{concurrent_store_id}",
        params={"end_date": "2026-06-30"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert removed.status_code == HTTPStatus.NO_CONTENT
    assert len(api.staffs.items) == 1


def test_スタッフ一覧は_法人単位で返る(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    _post(api, f"/corporates/{corporate_id}/staffs", _STAFF_BODY)

    # Act
    response = api.client.get(
        f"/corporates/{corporate_id}/staffs", headers=AUTHORIZED_HEADERS
    )

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert [item["last_name"] for item in response.json()] == ["鈴木"]


# --- 患者 -------------------------------------------------------------------


def test_患者を登録して取得できる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)

    # Act
    patient_id = _patient(api, corporate_id)
    response = api.client.get(
        f"/corporates/{corporate_id}/patients/{patient_id}", headers=AUTHORIZED_HEADERS
    )

    # Assert
    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert body["last_name"] == "佐藤"
    assert body["birth_date"] == "1980-05-06"
    assert body["patient_number"] >= 1


def test_外部患者IDは_無効化してから別患者へ付け替えられる(api: Api) -> None:
    # Arrange: 誤って紐付けた外部IDを直す流れ。
    corporate_id = _corporate(api)
    wrong_patient_id = _patient(api, corporate_id)
    right_patient_id = _post(
        api,
        f"/corporates/{corporate_id}/patients",
        {**_PATIENT_BODY, "last_name": "高橋"},
    )["id"]
    identifier = _post(
        api,
        f"/corporates/{corporate_id}/patients/{wrong_patient_id}/external-identifiers",
        {"system_name": "レセコン", "external_patient_id": "P-0001"},
    )

    # Act
    deactivated = api.client.post(
        f"/corporates/{corporate_id}"
        f"/patient-external-identifiers/{identifier['id']}/deactivation",
        headers=AUTHORIZED_HEADERS,
    )
    reassigned = _post(
        api,
        f"/corporates/{corporate_id}/patients/{right_patient_id}/external-identifiers",
        {"system_name": "レセコン", "external_patient_id": "P-0001"},
    )

    # Assert
    assert deactivated.status_code == HTTPStatus.NO_CONTENT
    assert reassigned["patient_id"] == right_patient_id
    assert reassigned["is_active"] is True
    detail = api.client.get(
        f"/corporates/{corporate_id}/patient-external-identifiers/{identifier['id']}",
        headers=AUTHORIZED_HEADERS,
    ).json()
    assert detail["is_active"] is False


def test_外部患者IDの一覧は_患者単位で返る(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    patient_id = _patient(api, corporate_id)
    _post(
        api,
        f"/corporates/{corporate_id}/patients/{patient_id}/external-identifiers",
        {"system_name": "レセコン", "external_patient_id": "P-0001"},
    )

    # Act
    response = api.client.get(
        f"/corporates/{corporate_id}/patients/{patient_id}/external-identifiers",
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert [item["external_patient_id"] for item in response.json()] == ["P-0001"]


# --- 資格台帳 ---------------------------------------------------------------


def test_資格を登録して_患者単位で一覧できる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    patient_id = _patient(api, corporate_id)

    # Act
    registered = _post(
        api,
        f"/corporates/{corporate_id}/patients/{patient_id}/coverages",
        _COVERAGE_BODY,
    )
    listed = api.client.get(
        f"/corporates/{corporate_id}/patients/{patient_id}/coverages",
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert registered["coverage_type"] == "insurance"
    assert registered["benefit_ratio"] == 70
    assert registered["valid_to"] is None
    assert [item["id"] for item in listed.json()] == [registered["id"]]


def test_資格の無効化は_発効日を持つ事実として残る(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    patient_id = _patient(api, corporate_id)
    coverage = _post(
        api,
        f"/corporates/{corporate_id}/patients/{patient_id}/coverages",
        _COVERAGE_BODY,
    )

    # Act
    response = api.client.post(
        f"/corporates/{corporate_id}/coverages/{coverage['id']}/deactivation",
        json={"effective_on": "2026-09-01"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert: 消えるのではなく、無効化発効日が付く。
    assert response.status_code == HTTPStatus.OK
    assert response.json()["deactivated_on"] == "2026-09-01"
    detail = api.client.get(
        f"/corporates/{corporate_id}/coverages/{coverage['id']}",
        headers=AUTHORIZED_HEADERS,
    )
    assert detail.status_code == HTTPStatus.OK


def test_資格の期間変更は_変更後の期間を返す(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    patient_id = _patient(api, corporate_id)
    coverage = _post(
        api,
        f"/corporates/{corporate_id}/patients/{patient_id}/coverages",
        _COVERAGE_BODY,
    )

    # Act
    response = api.client.patch(
        f"/corporates/{corporate_id}/coverages/{coverage['id']}/period",
        json={"valid_from": "2026-04-01", "valid_to": "2027-03-31"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json()["valid_to"] == "2027-03-31"


# --- 受付 -------------------------------------------------------------------


def test_受付の資格選択は_記録して候補として引き直せる(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    store_id = _store(api, corporate_id)
    patient_id = _patient(api, corporate_id)
    coverage = _post(
        api,
        f"/corporates/{corporate_id}/patients/{patient_id}/coverages",
        _COVERAGE_BODY,
    )

    # Act
    recorded = _post(
        api,
        f"/corporates/{corporate_id}/coverage-selections",
        {
            "store_id": store_id,
            "patient_id": patient_id,
            "applied_on": "2026-08-30",
            "coverage_ids": [coverage["id"]],
        },
    )
    latest = api.client.get(
        f"/corporates/{corporate_id}/coverage-selections/latest",
        params={
            "store_id": store_id,
            "patient_id": patient_id,
            "applied_on": "2026-08-31",
        },
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    body = latest.json()
    assert recorded["selection"]["insurance"]["source_coverage_id"] == coverage["id"]
    assert latest.status_code == HTTPStatus.OK
    assert body["record"]["id"] == recorded["id"]
    assert body["is_still_valid"] is True


def test_履歴が無ければ_候補はnullで返る(api: Api) -> None:
    # Arrange
    corporate_id = _corporate(api)
    store_id = _store(api, corporate_id)
    patient_id = _patient(api, corporate_id)

    # Act
    response = api.client.get(
        f"/corporates/{corporate_id}/coverage-selections/latest",
        params={
            "store_id": store_id,
            "patient_id": patient_id,
            "applied_on": "2026-08-31",
        },
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() is None


# --- 医薬品マスタ -----------------------------------------------------------


def test_医薬品は_時点を指定して引く(api: Api) -> None:
    """収載前の時点では見つからない。「今」で引くと過去の処方を誤判定する。"""
    # Arrange
    registered = _post(api, "/medicines", _MEDICINE_BODY)

    # Act
    effective = api.client.get(
        f"/medicines/yj/{_MEDICINE_BODY['code']}",
        params={"as_of": "2026-04-01"},
        headers=AUTHORIZED_HEADERS,
    )
    before_listing = api.client.get(
        f"/medicines/yj/{_MEDICINE_BODY['code']}",
        params={"as_of": "2019-01-01"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert registered["name"] == "サンプル錠10mg"
    assert effective.status_code == HTTPStatus.OK
    assert effective.json()["id"] == registered["id"]
    assert before_listing.status_code == HTTPStatus.NOT_FOUND


def test_医薬品マスタは_法人IDを取らない() -> None:
    """薬価基準は国が定めるので、法人ごとに複製しない。"""
    # Arrange
    from app.presentational.routers import medicine_catalog

    # Assert
    assert "{corporate_id}" not in medicine_catalog.router.prefix
