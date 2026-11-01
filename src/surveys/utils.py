from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from loguru import logger
from rest_framework.exceptions import NotFound

from .models import (
    Answer,
    OptionAnswer,
    Question,
    Survey,
    SurveyStatistics,
    SurveyStatus,
)


def with_my_answered_count(queryset, *, user):
    if not (user and user.is_authenticated):
        return queryset
    answered = (
        Answer.objects.filter(user_id=user.id, question__survey=OuterRef("pk"))
        .order_by()
        .values("question__survey_id")
        .annotate(total=Count("id"))
        .values("total")
    )
    return queryset.annotate(
        my_answered_count=Coalesce(
            Subquery(answered, output_field=IntegerField()), Value(0)
        )
    )


def catalogue_surveys(*, user, mine: bool = False):
    queryset = Survey.objects.select_related("author", "statistics")
    logger.info(f">>>>>>> catalogue_surveys: {mine=}")
    if mine:
        if not (user and user.is_authenticated):
            return queryset.none()
        queryset = queryset.filter(author=user)
    else:
        queryset = queryset.filter(status=SurveyStatus.PUBLISHED)

    if user and user.is_authenticated:
        queryset = with_my_answered_count(queryset, user=user)
    return queryset


def survey_detail_queryset(user):
    return (
        Survey.objects.visible_to(user)
        .select_related("author", "statistics")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=Question.objects.select_related("statistics").prefetch_related(
                    Prefetch(
                        "options",
                        queryset=OptionAnswer.objects.select_related(
                            "statistics"
                        ).order_by("position", "id"),
                    )
                ),
            )
        )
    )


def survey_statistics_payload(survey: Survey) -> dict:
    """Собирает статистику из инкрементальных счётчиков."""
    stats = getattr(survey, "statistics", None)
    logger.info(f">>>>>>> survey_statistics_payload: {stats=}")
    if stats is None:
        stats = SurveyStatistics.objects.filter(survey=survey).first()
        logger.info(f">>>>>>> survey_statistics_payload2: {stats=}")

    questions = list(
        Question.objects.filter(survey=survey)
        .select_related("statistics")
        .prefetch_related(
            Prefetch(
                "options",
                queryset=OptionAnswer.objects.select_related("statistics").order_by(
                    "position", "id"
                ),
            )
        )
        .order_by("position", "id")
    )
    logger.info(f">>>>>>> survey_statistics_payload: {questions=}")

    # Статистика по вопросам
    question_payload = []
    popular = []
    for question in questions:
        question_stats = getattr(question, "statistics", None)
        answer_count = question_stats.answer_count if question_stats else 0
        options_payload = []
        for option in question.options.all():
            option_stats = getattr(option, "statistics", None)
            count = option_stats.answer_count if option_stats else 0
            item = {
                "id": option.id,
                "text": option.text,
                "answer_count": count,
                "share": round(count / answer_count * 100, 2)
                if answer_count
                else 0.0,  # % ответов на вопрос
            }
            options_payload.append(item)
            popular.append(
                {**item, "question_id": question.id, "question_text": question.text}
            )
        options_payload.sort(key=lambda item: (-item["answer_count"], item["id"]))

        question_payload.append(
            {
                "id": question.id,
                "text": question.text,
                "answer_count": answer_count,
                "custom_answer_count": question_stats.custom_answer_count
                if question_stats
                else 0,
                "average_duration_ms": question_stats.average_duration_ms
                if question_stats
                else 0.0,
                "options": options_payload,
            }
        )

    popular.sort(
        key=lambda item: (-item["answer_count"], item["question_id"], item["id"])
    )
    popular = popular[:5]  # берем top-5 популярныых ответов

    return {
        "survey": {"id": survey.id, "title": survey.title, "status": survey.status},
        "started_count": stats.started_count if stats else 0,
        "completed_count": stats.completed_count if stats else 0,
        "completion_rate": stats.completion_rate if stats else 0.0,
        "answer_count": stats.answer_count if stats else 0,
        "custom_answer_count": stats.custom_answer_count if stats else 0,
        "average_duration_ms": stats.average_duration_ms if stats else 0.0,
        "questions": question_payload,
        "popular_options": popular,
    }


def get_visible_survey(survey_id: int, user) -> Survey:
    """Возвращает видимый пользователю опрос или выбрасывает 404."""
    survey = survey_detail_queryset(user=user).filter(pk=survey_id).first()
    if not survey:
        raise NotFound("Опрос не найден.")
    return survey


def get_visible_question(*, question_id: int, user) -> Question:
    """Возвращает видимый пользователю вопрос или выбрасывает 404."""
    visibility = Q(survey__status=SurveyStatus.PUBLISHED)
    if user and user.is_authenticated:
        visibility |= Q(survey__author=user)
    question = (
        Question.objects.select_related("survey", "survey__author")
        .filter(visibility, pk=question_id)
        .first()
    )
    if not question:
        raise NotFound("Вопрос не найден.")
    return question


def get_visible_option(*, option_id: int, user) -> OptionAnswer:
    """Возвращает видимый пользователю вариант ответа или выбрасывает 404."""
    visibility = Q(question__survey__status=SurveyStatus.PUBLISHED)
    if user and user.is_authenticated:
        visibility |= Q(question__survey__author=user)
    option = (
        OptionAnswer.objects.select_related("question", "question__survey")
        .filter(visibility, pk=option_id)
        .first()
    )
    if not option:
        raise NotFound("Вариант ответа не найден.")
    return option
