from django.conf import settings
from django.db import models

from src.core.models import BaseTimeStampedModel


class SurveyStatus(models.TextChoices):
    """Статус опроса"""

    DRAFT = "draft", "Черновик"
    PUBLISHED = "published", "Опубликован"
    ARCHIVED = "archived", "В архиве"


class Survey(BaseTimeStampedModel):
    """Опрос"""

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="surveys",
    )
    status = models.CharField(
        max_length=20,
        choices=SurveyStatus.choices,
        default=SurveyStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.title


class Question(BaseTimeStampedModel):
    """Вопрос"""

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()
    position = models.PositiveIntegerField(
        help_text="Позиция отображения внутри опроса.",
    )
    allow_custom_answer = models.BooleanField(
        default=True,
        help_text="Если True, то пользователь может дать свой ответ",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"Вопрос {self.position}: {self.text[:50]}"


class Answer(BaseTimeStampedModel):
    """Ответ на вопрос"""

    id = models.BigAutoField(primary_key=True)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    text = models.TextField()
    position = models.PositiveIntegerField(
        help_text="Позиция отображения внутри опроса.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"Ответ {self.position}: {self.text[:50]}"


class SurveyStatistics(BaseTimeStampedModel):
    """Статистика опроса"""

    survey = models.OneToOneField(
        Survey, on_delete=models.CASCADE, related_name="statistics"
    )
    started_count = models.PositiveBigIntegerField(
        default=0, help_text="Кол-во запусков"
    )
    completed_count = models.PositiveBigIntegerField(
        default=0, help_text="Кол-во завершений"
    )
    answer_count = models.PositiveBigIntegerField(default=0, help_text="Кол-во ответов")
    custom_answer_count = models.PositiveBigIntegerField(
        default=0, help_text="Кол-во ответов с выбором"
    )
    total_duration_ms = models.PositiveBigIntegerField(
        default=0, help_text="Общая продолжительность"
    )
    last_answer_at = models.DateTimeField(
        null=True, blank=True, help_text="Время последнего ответа"
    )

    def __str__(self) -> str:
        return f"Статистика опроса {self.survey_id}"


class QuestionStatistics(BaseTimeStampedModel):
    """Статистика вопроса"""

    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name="statistics"
    )
    answer_count = models.PositiveBigIntegerField(default=0, help_text="Кол-во ответов")
    custom_answer_count = models.PositiveBigIntegerField(
        default=0, help_text="Кол-во ответов с выбором"
    )
    total_duration_ms = models.PositiveBigIntegerField(
        default=0, help_text="Общая продолжительность"
    )
    last_answered_at = models.DateTimeField(
        null=True, blank=True, help_text="Время последнего ответа"
    )

    def __str__(self) -> str:
        return f"Статистика вопроса {self.question_id}"
