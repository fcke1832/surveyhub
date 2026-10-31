"""Statistics endpoint tests."""

from __future__ import annotations

from django.urls import reverse
from rest_framework.test import APIClient

from surveys.models import SurveyStatistics


def stats_url(survey_id: int) -> str:
    return reverse("surveys_api:survey-statistics", kwargs={"pk": survey_id})


def complete_survey(client, content, *, custom: bool = False) -> None:
    client.get(reverse("surveys_api:next-question", kwargs={"survey_id": content.survey.id}))
    client.post(
        reverse("surveys_api:submit-answer", kwargs={"survey_id": content.survey.id}),
        {"question_id": content.first.id, "option_id": content.first_options[0].id},
        format="json",
    )
    answer = {"custom_text": "Свой ответ"} if custom else {"option_id": content.second_options[0].id}
    client.post(
        reverse("surveys_api:submit-answer", kwargs={"survey_id": content.survey.id}),
        {"question_id": content.second.id, **answer},
        format="json",
    )


def test_stats_require_author(respondent_client, api_client, content):
    assert respondent_client.get(stats_url(content.survey.id)).status_code == 403
    assert api_client.get(stats_url(content.survey.id)).status_code in {401, 403}


def test_stats_are_aggregated(author_client, respondent_client, content):
    complete_survey(respondent_client, content, custom=True)

    response = author_client.get(stats_url(content.survey.id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["survey"]["id"] == content.survey.id
    assert payload["started_count"] == 1
    assert payload["completed_count"] == 1
    assert payload["completion_rate"] == 100.0
    assert payload["answer_count"] == 2
    assert payload["custom_answer_count"] == 1
    assert payload["average_duration_ms"] >= 0
    assert len(payload["questions"]) == 2

    first = payload["questions"][0]
    assert first["id"] == content.first.id
    assert first["answer_count"] == 1
    assert first["options"][0]["answer_count"] == 1
    assert first["options"][0]["share"] == 100.0

    assert payload["popular_options"][0]["text"] == "Да"
    assert payload["popular_options"][0]["answer_count"] == 1


def test_stats_include_partial_runs(author_client, respondent_client, content):
    respondent_client.get(reverse("surveys_api:next-question", kwargs={"survey_id": content.survey.id}))
    respondent_client.post(
        reverse("surveys_api:submit-answer", kwargs={"survey_id": content.survey.id}),
        {"question_id": content.first.id, "option_id": content.first_options[1].id},
        format="json",
    )
    payload = author_client.get(stats_url(content.survey.id)).json()
    assert payload["started_count"] == 1
    assert payload["completed_count"] == 0
    assert payload["completion_rate"] == 0.0
    assert payload["answer_count"] == 1
    options = {item["id"]: item for item in payload["questions"][0]["options"]}
    assert options[content.first_options[1].id]["answer_count"] == 1
    assert options[content.first_options[0].id]["answer_count"] == 0


def test_stats_for_unknown_survey_is_404(author_client):
    assert author_client.get(stats_url(999_999)).status_code == 404


def test_stats_persisted_counters_survive_multiple_respondents(author_client, respondent_client, content, db):
    from accounts.models import User

    complete_survey(respondent_client, content)

    other = User.objects.create_user(username="second-reader", password="x")
    other_client = APIClient()
    other_client.force_authenticate(user=other)
    complete_survey(other_client, content)

    payload = author_client.get(stats_url(content.survey.id)).json()
    assert payload["started_count"] == 2
    assert payload["completed_count"] == 2
    assert payload["answer_count"] == 4
    stats = SurveyStatistics.objects.get(survey=content.survey)
    assert stats.started_count == 2
    assert stats.completed_count == 2
