"""Login/logout API tests."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User

pytestmark = pytest.mark.django_db


def login_url() -> str:
    return reverse("accounts_api:login")


def logout_url() -> str:
    return reverse("accounts_api:logout")


def test_login_registers_unknown_user():
    client = APIClient()
    response = client.post(login_url(), {"username": "api-user", "password": "secret"}, format="json")
    assert response.status_code == 200
    user = User.objects.get(username="api-user")
    assert user.check_password("secret")
    assert response.json() == {"id": user.id, "username": "api-user"}


def test_login_existing_user_with_correct_password():
    user = User.objects.create_user(username="existing", password="right-password")
    client = APIClient()
    response = client.post(login_url(), {"username": "existing", "password": "right-password"}, format="json")
    assert response.status_code == 200
    assert response.json()["username"] == "existing"
    assert User.objects.filter(username="existing").count() == 1
    assert client.session["_auth_user_id"] == str(user.id)


def test_login_existing_user_with_wrong_password():
    User.objects.create_user(username="existing", password="right-password")
    client = APIClient()
    response = client.post(login_url(), {"username": "existing", "password": "wrong"}, format="json")
    assert response.status_code == 401
    assert "Неверный пароль" in response.json()["detail"]


def test_login_requires_password():
    client = APIClient()
    response = client.post(login_url(), {"username": "x"}, format="json")
    assert response.status_code == 400


def test_login_then_logout():
    client = APIClient()
    assert (
        client.post(login_url(), {"username": "sess-user", "password": "s"}, format="json").status_code == 200
    )
    assert "_auth_user_id" in client.session

    response = client.post(logout_url(), format="json")
    assert response.status_code == 204
    assert "_auth_user_id" not in client.session
