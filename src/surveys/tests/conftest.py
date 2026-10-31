"""Shared fixtures for survey tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from surveys.services.authoring import (
    add_option,
    add_question,
    create_survey,
    publish_survey,
)


@pytest.fixture
def author(db):
    """Survey owner."""
    return User.objects.create_user(username="author", password="author-password")


@pytest.fixture
def respondent(db):
    """A user who takes surveys."""
    return User.objects.create_user(username="respondent", password="respondent-password")


@pytest.fixture
def content(author, db) -> SimpleNamespace:
    """A published two-question survey with two options per question."""
    survey = create_survey(author=author, title="Овощи", description="Тестовый опрос")
    first = add_question(survey_id=survey.id, text="Ты любишь помидоры?")
    first_yes = add_option(question=first, text="Да")
    first_no = add_option(question=first, text="Нет")
    second = add_question(survey_id=survey.id, text="Ты любишь огурцы?")
    second_yes = add_option(question=second, text="Да")
    second_no = add_option(question=second, text="Нет")
    publish_survey(survey_id=survey.id)
    survey.refresh_from_db()
    return SimpleNamespace(
        survey=survey,
        first=first,
        second=second,
        first_options=[first_yes, first_no],
        second_options=[second_yes, second_no],
    )


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def author_client(author) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=author)
    return client


@pytest.fixture
def respondent_client(respondent) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=respondent)
    return client
