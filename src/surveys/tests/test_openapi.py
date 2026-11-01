import json

import pytest

pytestmark = pytest.mark.django_db


def test_schema_endpoint_serves_openapi(client):
    response = client.get("/api/schema/?format=json")
    assert response.status_code == 200
    paths = json.loads(response.content)["paths"]
    assert "/api/v1/auth/login/" in paths
    assert "/api/v1/auth/logout/" in paths
    assert "/api/v1/users/" in paths
    assert "/api/v1/surveys/" in paths
    assert "/api/v1/surveys/{survey_id}/next-question/" in paths


def test_swagger_ui_is_served(client):
    response = client.get("/api/docs/")
    assert response.status_code == 200
