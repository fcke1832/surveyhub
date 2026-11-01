import base64

import pytest
from django.urls import reverse

from ..models import Survey, SurveyStatus
from ..services import submit_answer

pytestmark = pytest.mark.django_db


def test_create_survey_requires_identity(api_client):
    response = api_client.post(
        reverse("surveys_api:survey-list"), {"title": "Анон"}, format="json"
    )
    assert response.status_code in {401, 403}
    assert not Survey.objects.exists()


def test_author_can_create_survey(author_client, author):
    response = author_client.post(
        reverse("surveys_api:survey-list"),
        {"title": "  Новый опрос  ", "description": "Описание"},
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Новый опрос"
    assert payload["status"] == SurveyStatus.DRAFT
    assert payload["author"] == author.id
    survey = Survey.objects.get(pk=payload["id"])
    assert survey.author == author
    assert survey.statistics.started_count == 0


def test_authoring_flow_with_order_and_publish(author_client):
    survey_id = author_client.post(
        reverse("surveys_api:survey-list"), {"title": "Овощи"}, format="json"
    ).json()["id"]

    first = author_client.post(
        reverse("surveys_api:survey-questions", kwargs={"survey_id": survey_id}),
        {"text": "Вопрос 1", "allow_custom_answer": True},
        format="json",
    )
    second = author_client.post(
        reverse("surveys_api:survey-questions", kwargs={"survey_id": survey_id}),
        {"text": "Вопрос 2"},
        format="json",
    )
    assert first.status_code == 201
    assert second.status_code == 201
    first_id, second_id = first.json()["id"], second.json()["id"]

    for question_id in (first_id, second_id):
        for option_text in ("Да", "Нет"):
            response = author_client.post(
                reverse(
                    "surveys_api:question-options", kwargs={"question_id": question_id}
                ),
                {"text": option_text},
                format="json",
            )
            assert response.status_code == 201

    publish = author_client.post(
        reverse("surveys_api:survey-publish", kwargs={"pk": survey_id}), format="json"
    )
    assert publish.status_code == 200
    assert publish.json()["status"] == SurveyStatus.PUBLISHED
    assert publish.json()["questions"][0]["id"] == first_id


def test_publish_validation_rejected(author_client):
    survey_id = author_client.post(
        reverse("surveys_api:survey-list"), {"title": "Черновик"}, format="json"
    ).json()["id"]
    publish = author_client.post(
        reverse("surveys_api:survey-publish", kwargs={"pk": survey_id}), format="json"
    )
    assert publish.status_code == 400
    assert "без вопросов" in publish.json()[0]

    question = author_client.post(
        reverse("surveys_api:survey-questions", kwargs={"survey_id": survey_id}),
        {"text": "Один"},
        format="json",
    ).json()
    author_client.post(
        reverse("surveys_api:question-options", kwargs={"question_id": question["id"]}),
        {"text": "Да"},
        format="json",
    )
    publish = author_client.post(
        reverse("surveys_api:survey-publish", kwargs={"pk": survey_id}), format="json"
    )
    assert publish.status_code == 400
    assert "два варианта" in publish.json()[0]


def test_only_author_can_change_survey(respondent_client, content):
    url = reverse("surveys_api:survey-detail", kwargs={"pk": content.survey.id})
    response = respondent_client.patch(url, {"title": "Взлом"}, format="json")
    assert response.status_code == 403

    response = respondent_client.post(
        reverse(
            "surveys_api:survey-questions", kwargs={"survey_id": content.survey.id}
        ),
        {"text": "Лишний"},
        format="json",
    )
    assert response.status_code == 403


def test_draft_is_not_visible_to_other_users(api_client, respondent_client, author):
    from ..services import create_survey

    draft = create_survey(author=author, title="черновик 1")
    url = reverse("surveys_api:survey-detail", kwargs={"pk": draft.id})
    assert api_client.get(url).status_code == 404
    assert respondent_client.get(url).status_code == 404


def test_author_sees_draft_via_mine_list(author_client, author):
    from ..services import create_survey

    draft = create_survey(author=author, title="черновик 2")
    response = author_client.get(reverse("surveys_api:survey-list") + "?mine=true")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert draft.id in ids


def test_author_can_add_question_and_edit_text_after_answers(
    author_client, respondent, content
):
    submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.first.id,
        option_id=content.first_options[0].id,
    )

    add = author_client.post(
        reverse(
            "surveys_api:survey-questions", kwargs={"survey_id": content.survey.id}
        ),
        {"text": "Поздно"},
        format="json",
    )
    assert add.status_code == 201

    update = author_client.patch(
        reverse(
            "surveys_api:question-detail", kwargs={"question_id": content.first.id}
        ),
        {"text": "Исправленный текст"},
        format="json",
    )
    assert update.status_code == 200
    assert update.json()["text"] == "Исправленный текст"


def test_author_can_delete_survey_with_answers(author_client, respondent, content):
    submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.first.id,
        option_id=content.first_options[0].id,
    )
    response = author_client.delete(
        reverse("surveys_api:survey-detail", kwargs={"pk": content.survey.id})
    )
    assert response.status_code == 204
    assert not Survey.objects.filter(pk=content.survey.id).exists()


@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_rejected(author_client, title):
    response = author_client.post(
        reverse("surveys_api:survey-list"), {"title": title}, format="json"
    )
    assert response.status_code == 400


def test_unknown_basic_credentials_are_rejected(api_client):
    token = base64.b64encode(b"does-not-exist:secret").decode()
    api_client.credentials(HTTP_AUTHORIZATION=f"Basic {token}")
    response = api_client.get(reverse("surveys_api:survey-list"))
    assert response.status_code == 401
