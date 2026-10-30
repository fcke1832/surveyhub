from django.conf import settings
from django.db import models

from src.core.models import BaseTimeStampedModel


class Survey(BaseTimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="surveys",
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.title


class Question(BaseTimeStampedModel):
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
