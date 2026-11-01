import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from ..models import (
    Answer,
    OptionAnswer,
    QuestionStatistics,
    SurveyStatistics,
    SurveyStatus,
)
from ..services import (
    add_option,
    add_question,
    create_survey,
    delete_question,
    get_next_question,
    publish_survey,
    submit_answer,
)


def test_question_and_option_order(content):
    assert list(content.survey.questions.values_list("id", flat=True)) == [
        content.first.id,
        content.second.id,
    ]
    assert list(content.first.options.values_list("id", flat=True)) == [
        content.first_options[0].id,
        content.first_options[1].id,
    ]


def test_positions_increment_on_add(author):
    survey = create_survey(author=author, title="Порядок")
    q1 = add_question(survey_id=survey.id, text="Вопрос 1")
    q2 = add_question(survey_id=survey.id, text="Вопрос 2")
    q3 = add_question(survey_id=survey.id, text="Вопрос 3")
    assert [q1.position, q2.position, q3.position] == [0, 1, 2]

    o1 = add_option(question=q1, text="А")
    o2 = add_option(question=q1, text="Б")
    o3 = add_option(question=q1, text="В")
    assert [o1.position, o2.position, o3.position] == [0, 1, 2]


def test_one_answer_per_user_and_question(respondent, content):
    Answer.objects.create(user=respondent, question=content.first, custom_text="Первый")
    with pytest.raises(IntegrityError), transaction.atomic():
        Answer.objects.create(
            user=respondent, question=content.first, custom_text="Второй"
        )


def test_statistics_rows_are_created_with_content(content):
    assert SurveyStatistics.objects.filter(survey=content.survey).exists()
    assert QuestionStatistics.objects.filter(question=content.first).exists()
    assert content.first.options.count() == 2


def test_delete_question_compacts_positions(author, content):
    delete_question(question=content.first)
    remaining = list(content.survey.questions.values_list("position", flat=True))
    assert remaining == [0]
    content.survey.refresh_from_db()
    assert content.survey.question_count == 1


def test_publish_requires_two_options(author):
    survey = create_survey(author=author, title="Пустой")
    question = add_question(survey_id=survey.id, text="Один вариант")
    add_option(question=question, text="Да")
    with pytest.raises(ValidationError):
        publish_survey(survey_id=survey.id)
    survey.refresh_from_db()
    assert survey.status == SurveyStatus.DRAFT


def test_questions_can_be_added_and_deleted_after_first_answer(respondent, content):
    submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.first.id,
        option_id=content.first_options[0].id,
    )
    added = add_question(survey_id=content.survey.id, text="Поздний вопрос")
    assert added.survey_id == content.survey.id
    delete_question(question=content.second)
    assert not content.survey.questions.filter(pk=content.second.id).exists()


def test_progress_and_stats(respondent, content):
    state = get_next_question(survey_id=content.survey.id, user=respondent)
    assert state["question"].id == content.first.id
    assert state["progress"]["answered"] == 0

    state = submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.first.id,
        option_id=content.first_options[0].id,
    )
    assert state["question"].id == content.second.id
    assert state["progress"]["answered"] == 1
    assert not state["completed"]

    state = submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.second.id,
        custom_text="  Некий текст  ",
    )
    assert state["completed"]
    assert state["question"] is None
    assert state["progress"]["percent"] == 100
    assert state["submitted_answer"].custom_text == "Некий текст"

    stats = SurveyStatistics.objects.get(survey=content.survey)
    assert stats.started_count == 1
    assert stats.completed_count == 1
    assert stats.answer_count == 2
    assert stats.custom_answer_count == 1
    assert stats.average_duration_ms >= 0


def test_custom_answer_can_be_disabled(author, respondent):
    from ..services import create_survey, update_question

    survey = create_survey(author=author, title="Без своего ответа")
    question = add_question(
        survey_id=survey.id, text="Выберите", allow_custom_answer=True
    )
    update_question(question=question, allow_custom_answer=False)
    add_option(question=question, text="Да")
    add_option(question=question, text="Нет")
    publish_survey(survey_id=survey.id)

    get_next_question(survey_id=survey.id, user=respondent)
    with pytest.raises(ValidationError):
        submit_answer(
            survey_id=survey.id,
            user=respondent,
            question_id=question.id,
            custom_text="Свой",
        )


def test_option_must_belong_to_question(respondent, content):
    get_next_question(survey_id=content.survey.id, user=respondent)
    with pytest.raises(ValidationError):
        submit_answer(
            survey_id=content.survey.id,
            user=respondent,
            question_id=content.first.id,
            option_id=content.second_options[0].id,
        )


def test_option_and_custom_are_mutually_exclusive(respondent, content):
    get_next_question(survey_id=content.survey.id, user=respondent)
    with pytest.raises(ValidationError):
        submit_answer(
            survey_id=content.survey.id,
            user=respondent,
            question_id=content.first.id,
            option_id=content.first_options[0].id,
            custom_text="Свой",
        )


def test_option_belongs_to_deleted_question_is_protected(author, content, respondent):
    get_next_question(survey_id=content.survey.id, user=respondent)
    submit_answer(
        survey_id=content.survey.id,
        user=respondent,
        question_id=content.first.id,
        option_id=content.first_options[0].id,
    )
    assert OptionAnswer.objects.filter(pk=content.first_options[0].pk).exists()
