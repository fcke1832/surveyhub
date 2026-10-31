from rest_framework import status
from rest_framework.exceptions import APIException


class ConflictError(APIException):
    """Запрос конфликтует с текущим состоянием."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Операция конфликтует с текущим состоянием опроса."
    default_code = "conflict"


class AnswerConflict(ConflictError):
    """Присланный вопрос больше не является ожидаемым следующим вопросом."""

    default_detail = "Этот вопрос уже не является текущим. Запросите следующий вопрос."
    default_code = "answer_out_of_order"
