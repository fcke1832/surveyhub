from django.contrib.auth.models import AbstractUser

from src.core.models import BaseTimeStampedModel


class User(AbstractUser, BaseTimeStampedModel):
    """Пользователь - автор или респондент"""

    class Meta:
        ordering = ("id",)
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.username
