from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import OptionAnswer, Question, Survey


def survey_author_id(obj: object) -> int | None:
    """Идентификатор автора опроса."""
    if isinstance(obj, Survey):
        return obj.author_id
    if isinstance(obj, Question):
        return obj.survey.author_id
    if isinstance(obj, OptionAnswer):
        return obj.question.survey.author_id
    return None


class IsSurveyRespondent(BasePermission):
    """Идентификация респондента"""

    message = "Для прохождения опроса нужно идентифицировать пользователя."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        return survey_author_id(obj) == request.user.id


class IsSurveyAuthor(BasePermission):
    """Опрос может менять только его автор."""

    message = "Менять опрос может только его автор."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)


class IsSurveyRespondent(BasePermission):
    """Опрос может пройти только авторизованный респондент."""

    message = "Для прохождения опроса нужно идентифицировать пользователя."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)


class IsAuthorOrReadOnly(IsSurveyAuthor):
    """Публичное чтение, запись только автор может"""

    def has_permission(self, request, view) -> bool:
        """Разрешает безопасные методы всем, а запись только автору."""
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj) -> bool:
        """Разрешает чтение объекта всм, а изменение только автору."""
        if request.method in SAFE_METHODS:
            return True
        return super().has_object_permission(request, view, obj)
