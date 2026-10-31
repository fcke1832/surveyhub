"""Users list endpoint tests."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_user_list_returns_all_users():
    User.objects.create_user(username="alice", password="x")
    User.objects.create_user(username="bob", password="x")

    response = APIClient().get(reverse("accounts_api:user-list"))

    assert response.status_code == 200
    usernames = {item["username"] for item in response.json()["results"]}
    assert {"alice", "bob"} <= usernames
