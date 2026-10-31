from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Max, Min
from django.utils import timezone
from loguru import logger
from rest_framework.exceptions import NotFound, ValidationError

from .exceptions import AnswerConflict, ConflictError
from .models import (
    Answer,
    OptionAnswer,
    OptionAnswerStatistics,
    Question,
    QuestionStatistics,
    Survey,
    SurveyStatistics,
    SurveyStatus,
)


def _clean_text(value: str, field: str = "text") -> str:
    """Проверка на то что текст опроса не пустой"""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError({field: "Текст не может быть пустым."})
    return cleaned


def _get_survey_by_id(survey_id: int) -> Survey:
    survey = Survey.objects.filter(id=survey_id).first()
    if not survey:
        raise ValidationError("Опрос не найден.")
    return survey


def _sync_question_count(survey: Survey) -> None:
    """Пересчитывает и записывает денормализованный счётчик вопросов."""
    survey.question_count = Question.objects.filter(survey=survey).count()
    survey.save(update_fields=("question_count", "updated_at"))


def _get_questions(survey: Survey) -> list[Question]:
    """Упорядоченные вопросы с предзагруженными вариантами."""
    return list(
        Question.objects.filter(survey=survey)
        .prefetch_related("options")
        .order_by("position", "id")
    )


def _get_answered_ids(survey_id: int, user_id: int) -> set[int]:
    """id вопросов, на которые пользователь уже ответил в этом опросе."""
    return set(
        Answer.objects.filter(
            user_id=user_id, question__survey_id=survey_id
        ).values_list("question_id", flat=True)
    )


def _answers_time_diff(survey_id: int, user_id: int) -> tuple:
    """Вычсиляем разницу  времени между первым и последним ответом"""
    values = Answer.objects.filter(
        user_id=user_id, question__survey_id=survey_id
    ).aggregate(
        first=Min("created_at"),
        last=Max("created_at"),
    )
    return values["first"], values["last"]


def _progress(answered: int, total: int) -> dict:
    """Прогресс прохождения (отвечено, всего, процент)."""
    percent = 100 if total == 0 else min(100, round(answered / total * 100))
    return {"answered": answered, "total": total, "percent": percent}


def _get_state(survey: Survey, user, submitted_answer: Answer | None = None) -> dict:
    """Собирает текущее состояние прохождения опроса из сохранённых ответов."""
    logger.info(f">>>>>>>> _get_state: {survey.id=}, {user.id=}")
    questions = _get_questions(survey)
    answered_ids = _get_answered_ids(survey_id=survey.id, user_id=user.id)
    answered = sum(1 for question in questions if question.id in answered_ids)
    total = len(questions)
    question = next((item for item in questions if item.id not in answered_ids), None)
    completed = total > 0 and question is None
    started_at, last_answer_at = _answers_time_diff(
        survey_id=survey.id, user_id=user.id
    )
    logger.info(
        f">>>>>>>> _get_state: {answered_ids=}, {answered=}, {total=}, {question=}, {completed=}, {started_at=}, {last_answer_at=}"
    )

    duration_ms = 0
    if completed and started_at is not None and last_answer_at is not None:
        duration_ms = max(0, int((last_answer_at - started_at).total_seconds() * 1000))

    return {
        "survey": survey,
        "question": question,
        "progress": _progress(answered=answered, total=total),
        "completed": completed,
        "started_at": started_at,
        "completed_at": last_answer_at if completed else None,
        "duration_ms": duration_ms,
        "submitted_answer": submitted_answer,
    }


def _validate_answer(
    question: Question,
    option_id: int | None,
    custom_text: str,
) -> tuple:
    """Проверяет ответ: ровно одно из «вариант» и «свой текст», вариант должен относиться к вопросу."""
    logger.info(f">>>>>>>> _validate_answer: {question=}, {option_id=}, {custom_text=}")
    text = (custom_text or "").strip()

    if option_id and text:
        # Свой ответ и вариант ответа одновременно
        raise ValidationError(
            "Выберите вариант или введите свой ответ, но не оба сразу."
        )

    if not option_id and not text:
        # Не выбран вариант и не ввел свой текст
        raise ValidationError("Выберите вариант ответа или введите свой.")

    if text:
        if not question.allow_custom_answer:
            raise ValidationError(
                {"custom_text": "Для этого вопроса свой ответ недоступен."}
            )
        if len(text) > settings.SURVEY_CUSTOM_ANSWER_MAX_LENGTH:
            raise ValidationError(
                {
                    "custom_text": f"Не больше {settings.SURVEY_CUSTOM_ANSWER_MAX_LENGTH} символов."
                }
            )
        return None, text
    option = OptionAnswer.objects.filter(pk=option_id, question=question).first()
    if not option:
        raise ValidationError(
            {
                "option_id": f"Вариант ответа {option_id=} не относится к  вопросу {question.id=}. "
            }
        )
    return option, ""


def _calculate_duration_ms(now: datetime, previous: Answer | None) -> int:
    """Возвращает время, прошедшее с предыдущего ответа, в миллисекундах."""
    return (
        0
        if not previous
        else max(0, int((now - previous.created_at).total_seconds() * 1000))
    )


def _increment_survey_statistics(
    survey_id: int, now: datetime, is_custom_answer: bool
) -> None:
    """Инкрементально обновляет счётчики статистики опроса."""
    updates = {
        "answer_count": F("answer_count") + 1,
        "last_answer_at": now,
        "updated_at": now,
    }
    logger.info(f">>>>>>>> _increment_survey_statistics: {survey_id=}, {updates=}")
    if is_custom_answer:
        updates["custom_answer_count"] = F("custom_answer_count") + 1
    SurveyStatistics.objects.filter(survey_id=survey_id).update(**updates)
    logger.info(f">>>>>>>> _increment_survey_statistics: {survey_id=} was updated")


def _increment_question_statistics(
    question_id: int, now, duration_ms: int, is_custom_answer: bool
) -> None:
    """Инкрементально обновляет счётчики статистики вопроса."""
    updates = {
        "answer_count": F("answer_count") + 1,
        "total_duration_ms": F("total_duration_ms") + duration_ms,
        "last_answered_at": now,
        "updated_at": now,
    }
    if is_custom_answer:
        updates["custom_answer_count"] = F("custom_answer_count") + 1
    QuestionStatistics.objects.filter(question_id=question_id).update(**updates)


def _increment_option_answer_statistics(option_id: int, now: datetime) -> None:
    """Инкрементально обновляет счётчик статистики варианта ответа."""
    OptionAnswerStatistics.objects.filter(option_id=option_id).update(
        answer_count=F("answer_count") + 1,
        last_answered_at=now,
        updated_at=now,
    )


@transaction.atomic
def create_survey(author, title: str, description: str = "") -> Survey:
    survey = Survey.objects.create(
        author=author,
        title=_clean_text(title, field="title"),
        description=(description or "").strip(),
    )
    SurveyStatistics.objects.create(survey=survey)
    return survey


def update_survey(
    survey: Survey, title: str | None = None, description: str | None = None
) -> Survey:
    """Обновляет редактируемые данные опроса."""
    fields = []
    if title is not None:
        survey.title = _clean_text(title, field="title")
        fields.append("title")
    if description is not None:
        survey.description = description.strip()
        fields.append("description")
    if fields:
        survey.save(update_fields=(*fields, "updated_at"))
    return survey


@transaction.atomic
def publish_survey(survey_id: int) -> Survey:
    """Проверяет и публикует опрос."""
    survey = _get_survey_by_id(survey_id)
    logger.info(f">>>>>>>>>>>> publish_survey {survey=}.")
    questions = Question.objects.filter(survey=survey).annotate(
        option_count=Count("options")
    )
    logger.info(f">>>>>>>>>>>> publish_survey {questions=}.")
    if not questions.exists():
        raise ValidationError("Нельзя опубликовать опрос без вопросов.")
    if any(question.option_count < 2 for question in questions):
        raise ValidationError("Должно быть минимум два варианта ответа.")
    survey.question_count = questions.count()
    survey.status = SurveyStatus.PUBLISHED
    survey.published_at = survey.published_at or timezone.now()
    survey.save(
        update_fields=("status", "published_at", "question_count", "updated_at")
    )
    logger.info(f">>>>>>>>>>>> publish_survey {survey.__dict__=}.")
    return survey


def delete_survey(survey_id: int) -> None:
    """Удаляет опрос"""
    survey = _get_survey_by_id(survey_id)
    survey.delete()


@transaction.atomic
def add_question(
    survey_id: int, text: str, allow_custom_answer: bool = True
) -> Question:
    """Добавляет вопрос в конец опроса."""
    survey = _get_survey_by_id(survey_id)
    logger.info(f" >>>>>>>> add_question {survey=}, {text=}, {allow_custom_answer=}")
    max_position = survey.questions.aggregate(value=Max("position"))["value"]
    question = Question.objects.create(
        survey=survey,
        text=_clean_text(text),
        position=0 if max_position is None else max_position + 1,
        allow_custom_answer=allow_custom_answer,
    )
    QuestionStatistics.objects.create(question=question)
    _sync_question_count(survey)
    logger.info(f" >>>>>>>> add_question success {question=}.")
    return question


def update_question(
    question: Question,
    text: str | None = None,
    allow_custom_answer: bool | None = None,
) -> Question:
    """Изменяет текст вопроса или настройку свободного ответа."""
    logger.info(
        f" >>>>>>>> update_question {question=}, {text=}, {allow_custom_answer=}"
    )
    fields = []
    if text:
        question.text = _clean_text(text)
        fields.append("text")
    if allow_custom_answer is not None:
        question.allow_custom_answer = allow_custom_answer
        fields.append("allow_custom_answer")
    if fields:
        question.save(update_fields=fields)
    logger.info(f" >>>>>>>> update_question success {question.__dict__=}.")
    return question


def _compact_positions(queryset) -> None:
    """Перенумеровывает position элементов по порядку: 0, 1, 2, …"""
    for index, item in enumerate(queryset.order_by("position", "id")):
        if item.position != index:
            item.position = index
            item.save(update_fields=("position",))


@transaction.atomic
def delete_question(question: Question) -> None:
    """Удаляет вопрос"""
    survey = _get_survey_by_id(question.survey_id)
    question.delete()
    _compact_positions(survey.questions.all())
    _sync_question_count(survey)


@transaction.atomic
def add_option(question: Question, text: str) -> OptionAnswer:
    """Добавляет вариант ответа в конец вопроса."""
    logger.info(f" >>>>>>>> add_option {question=}, {text=}")
    max_position = question.options.aggregate(value=Max("position"))["value"]
    option = OptionAnswer.objects.create(
        question=question,
        text=_clean_text(text),
        position=0 if max_position is None else max_position + 1,
    )
    OptionAnswerStatistics.objects.create(option=option)
    logger.info(f" >>>>>>>> add_option  success {question.__dict__=}")
    return option


def update_option(option: OptionAnswer, text: str | None = None) -> OptionAnswer:
    """Изменяет текст варианта."""
    if text:
        option.text = _clean_text(text)
        option.save(update_fields=("text",))
    return option


@transaction.atomic
def delete_option(option: OptionAnswer) -> None:
    """Удаляет вариант ответа."""
    question_id = option.question_id
    option.delete()
    _compact_positions(OptionAnswer.objects.filter(question_id=question_id))


def get_next_question(survey_id: int, user) -> dict | None:
    """Возвращает первый неотвеченный вопрос для текущего пользователя."""
    survey = Survey.objects.filter(pk=survey_id).first()
    logger.info(f">>>>>>>>>>>>> get_next_question {survey=}, {user=}")
    if not survey:
        raise NotFound("Опрос не найден.")

    has_answers = Answer.objects.filter(
        user_id=user.id, question__survey_id=survey.id
    ).exists()
    if survey.status != SurveyStatus.PUBLISHED and not has_answers:
        raise NotFound("Опрос не найден или ещё не опубликован.")
    if not Question.objects.filter(survey=survey).exists():
        raise NotFound("В опросе пока нет вопросов.")
    return _get_state(survey=survey, user=user)


@transaction.atomic
def submit_answer(
    survey_id: int,
    user,
    question_id: int,
    option_id: int | None = None,
    custom_text: str = "",
) -> dict:
    """Сохраняет ответ и возвращает следующий вопрос или завершает опрос"""
    survey = _get_survey_by_id(survey_id)
    if not survey:
        raise NotFound("Опрос не найден.")

    questions = _get_questions(survey)
    if not questions:
        raise ConflictError("В опросе пока нет вопросов.")

    answered_ids = _get_answered_ids(survey_id=survey.id, user_id=user.id)
    if survey.status != SurveyStatus.PUBLISHED and not answered_ids:
        raise NotFound("Опрос не найден или ещё не опубликован.")

    next_question = next(
        (question for question in questions if question.id not in answered_ids), None
    )
    if not next_question:
        raise ConflictError("Опрос уже завершён.")

    if int(question_id) != next_question.id:
        raise AnswerConflict(
            f"Сейчас нужно ответить на вопрос {next_question.id}, а не {question_id}."
        )

    option, text = _validate_answer(
        question=next_question,
        option_id=option_id,
        custom_text=custom_text,
    )

    now = timezone.now()
    previous = (
        Answer.objects.filter(user_id=user.id, question__survey_id=survey.id)
        .order_by("-created_at", "-id")
        .only("created_at")
        .first()
    )
    is_first = previous is None
    # Вычисляем время выполнения предыдущего вопроса
    duration_ms = _calculate_duration_ms(previous=previous, now=now)

    answer = Answer.objects.create(
        user=user,
        question=next_question,
        option=option,
        custom_text=text,
        duration_ms=duration_ms,
    )

    is_custom_answer = option is None
    _increment_survey_statistics(
        survey_id=survey.id, now=now, is_custom_answer=is_custom_answer
    )
    _increment_question_statistics(
        question_id=next_question.id,
        now=now,
        duration_ms=duration_ms,
        is_custom_answer=is_custom_answer,
    )
    if option:
        _increment_option_answer_statistics(option_id=option.id, now=now)

    if is_first:
        SurveyStatistics.objects.filter(survey_id=survey.id).update(
            started_count=F("started_count") + 1,
            updated_at=now,
        )

    if len(answered_ids) + 1 >= len(questions):
        first_answer_at = Answer.objects.filter(
            user_id=user.id, question__survey_id=survey.id
        ).aggregate(value=Min("created_at"))["value"]
        total_duration_ms = (
            0
            if first_answer_at is None
            else max(0, int((now - first_answer_at).total_seconds() * 1000))
        )
        SurveyStatistics.objects.filter(survey_id=survey.id).update(
            completed_count=F("completed_count") + 1,
            total_duration_ms=F("total_duration_ms") + total_duration_ms,
            updated_at=now,
        )

    return _get_state(survey=survey, user=user, submitted_answer=answer)
