import base64
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import User

from ..models import (
    Answer,
    OptionAnswerStatistics,
    QuestionStatistics,
    SurveyStatistics,
)


def next_url(survey_id: int) -> str:
    return reverse("surveys_api:next-question", kwargs={"survey_id": survey_id})


def answer_url(survey_id: int) -> str:
    return reverse("surveys_api:submit-answer", kwargs={"survey_id": survey_id})


def test_taking_requires_identity(api_client, content):
    response = api_client.get(next_url(content.survey.id))
    assert response.status_code in {401, 403}
    assert not Answer.objects.filter(question__survey=content.survey).exists()


def test_next_question_returns_first_unanswered_and_is_idempotent(
    respondent_client, content
):
    response = respondent_client.get(next_url(content.survey.id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["completed"] is False
    assert payload["question"]["id"] == content.first.id
    assert [option["id"] for option in payload["question"]["options"]] == [
        option.id for option in content.first_options
    ]
    assert payload["progress"] == {"answered": 0, "total": 2, "percent": 0}
    assert payload["started_at"] is None
    assert payload["completed_at"] is None
    assert payload["duration_ms"] == 0

    again = respondent_client.get(next_url(content.survey.id))
    assert again.status_code == 200
    assert again.json()["question"]["id"] == payload["question"]["id"]
    assert again.json()["progress"] == payload["progress"]
    assert SurveyStatistics.objects.get(survey=content.survey).started_count == 0


def test_full_flow_with_option_and_custom_answer(
    respondent_client, respondent, content
):
    respondent_client.get(next_url(content.survey.id))

    first_answer = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    assert first_answer.status_code == 201
    first_payload = first_answer.json()
    assert first_payload["completed"] is False
    assert first_payload["question"]["id"] == content.second.id
    assert first_payload["progress"]["answered"] == 1
    assert first_payload["started_at"] is not None
    assert first_payload["submitted_answer"]["option"] == content.first_options[0].id

    second_answer = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.second.id, "custom_text": "  Только в коктейлях  "},
        format="json",
    )
    assert second_answer.status_code == 201
    payload = second_answer.json()
    assert payload["completed"] is True
    assert payload["question"] is None
    assert payload["progress"] == {"answered": 2, "total": 2, "percent": 100}
    assert payload["completed_at"] is not None
    assert payload["submitted_answer"]["custom_text"] == "Только в коктейлях"

    assert (
        Answer.objects.filter(user=respondent, question__survey=content.survey).count()
        == 2
    )

    stats = SurveyStatistics.objects.get(survey=content.survey)
    assert stats.started_count == 1
    assert stats.completed_count == 1
    assert stats.answer_count == 2
    assert stats.custom_answer_count == 1
    assert stats.last_answer_at is not None

    question_stats = QuestionStatistics.objects.get(question=content.first)
    assert question_stats.answer_count == 1
    assert (
        OptionAnswerStatistics.objects.get(option=content.first_options[0]).answer_count
        == 1
    )
    assert (
        OptionAnswerStatistics.objects.get(option=content.first_options[1]).answer_count
        == 0
    )

    resumed = respondent_client.get(next_url(content.survey.id))
    assert resumed.status_code == 200
    assert resumed.json()["completed"] is True
    assert resumed.json()["question"] is None
    assert SurveyStatistics.objects.get(survey=content.survey).started_count == 1


def test_answers_must_be_submitted_in_order(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    response = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.second.id, "option_id": content.second_options[0].id},
        format="json",
    )
    assert response.status_code == 409
    assert response.json()["detail"].startswith("Сейчас нужно ответить")


def test_duplicate_answer_is_conflict(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    payload = {
        "question_id": content.first.id,
        "option_id": content.first_options[0].id,
    }
    assert (
        respondent_client.post(
            answer_url(content.survey.id), payload, format="json"
        ).status_code
        == 201
    )
    assert (
        respondent_client.post(
            answer_url(content.survey.id), payload, format="json"
        ).status_code
        == 409
    )


def test_first_answer_can_be_submitted_without_prior_get(respondent_client, content):
    response = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["progress"]["answered"] == 1
    assert SurveyStatistics.objects.get(survey=content.survey).started_count == 1


def test_option_from_another_question_is_rejected(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    response = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.second_options[0].id},
        format="json",
    )
    assert response.status_code == 400
    assert "option_id" in response.json()


def test_both_answer_values_are_rejected(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    response = respondent_client.post(
        answer_url(content.survey.id),
        {
            "question_id": content.first.id,
            "option_id": content.first_options[0].id,
            "custom_text": "Свой",
        },
        format="json",
    )
    assert response.status_code == 400


def test_empty_answer_is_rejected(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    response = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id},
        format="json",
    )
    assert response.status_code == 400


def test_custom_answer_length_is_limited(respondent_client, content):
    respondent_client.get(next_url(content.survey.id))
    response = respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "custom_text": "x" * 2001},
        format="json",
    )
    assert response.status_code == 400
    assert "custom_text" in response.json()


def test_completed_duration_and_average(respondent_client, respondent, content):
    respondent_client.get(next_url(content.survey.id))
    respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    Answer.objects.filter(user=respondent, question__survey=content.survey).update(
        created_at=timezone.now() - timedelta(seconds=5)
    )
    respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.second.id, "option_id": content.second_options[0].id},
        format="json",
    )
    stats = SurveyStatistics.objects.get(survey=content.survey)
    assert stats.completed_count == 1
    assert stats.total_duration_ms >= 4000
    assert stats.average_duration_ms >= 4000


def test_basic_auth_can_take_survey(respondent, content):
    token = base64.b64encode(b"respondent:password").decode()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Basic {token}")
    response = client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    assert response.status_code == 201
    answer = Answer.objects.get(user=respondent, question=content.first)
    assert answer.user_id == respondent.id


def test_draft_cannot_be_started_by_respondent(respondent_client, author):
    from ..services import create_survey

    survey = create_survey(author=author, title="Черновик")
    response = respondent_client.get(next_url(survey.id))
    assert response.status_code == 404


def test_independent_progress_per_user(respondent_client, content, db):
    other = User.objects.create_user(username="other", password="x")
    other_client = APIClient()
    other_client.force_authenticate(user=other)

    assert respondent_client.get(next_url(content.survey.id)).status_code == 200
    assert other_client.get(next_url(content.survey.id)).status_code == 200
    assert Answer.objects.filter(question__survey=content.survey).count() == 0

    payload = {
        "question_id": content.first.id,
        "option_id": content.first_options[0].id,
    }
    assert (
        respondent_client.post(
            answer_url(content.survey.id), payload, format="json"
        ).status_code
        == 201
    )
    assert (
        other_client.post(
            answer_url(content.survey.id), payload, format="json"
        ).status_code
        == 201
    )
    assert Answer.objects.filter(question__survey=content.survey).count() == 2


def test_catalogue_reports_my_progress(respondent_client, content):
    def status() -> str | None:
        results = respondent_client.get(reverse("surveys_api:survey-list")).json()[
            "results"
        ]
        return next(
            item["my_progress_status"]
            for item in results
            if item["id"] == content.survey.id
        )

    assert status() is None
    respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    assert status() == "in_progress"
    respondent_client.post(
        answer_url(content.survey.id),
        {"question_id": content.second.id, "option_id": content.second_options[0].id},
        format="json",
    )
    assert status() == "completed"
