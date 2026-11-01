import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from ..models import User

pytestmark = pytest.mark.django_db


def test_user_list_returns_all_users():
    User.objects.create_user(username="user1", password="x")
    User.objects.create_user(username="user2", password="x")

    response = APIClient().get(reverse("users_api:user-list"))

    assert response.status_code == 200
    usernames = {item["username"] for item in response.json()["results"]}
    assert {"user1", "user2"} <= usernames
