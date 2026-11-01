from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from users.models import User

from ..services import (
    add_option,
    add_question,
    create_survey,
    publish_survey,
)


@pytest.fixture
def author(db):
    return User.objects.create_user(username="author", password="password")


@pytest.fixture
def respondent(db):
    return User.objects.create_user(username="respondent", password="password")


@pytest.fixture
def content(author, db) -> SimpleNamespace:
    """Публикуем 2 вопроса по 2 ответа в каждом"""
    survey = create_survey(author=author, title="Опрос 1", description="Тестовый опрос")
    first = add_question(survey_id=survey.id, text="Вопрос 1?")
    first_yes = add_option(question=first, text="Да")
    first_no = add_option(question=first, text="Нет")
    second = add_question(survey_id=survey.id, text="Вопрос 2?")
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
