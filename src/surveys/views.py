from django.db.models.query_utils import logger
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, Survey
from .pagination import CursorPagination
from .permissions import IsAuthorOrReadOnly, IsSurveyAuthor, IsSurveyRespondent
from .serializers import (
    OptionSerializer,
    OptionWriteSerializer,
    QuestionSerializer,
    QuestionWriteSerializer,
    SubmitAnswerSerializer,
    SurveyDetailSerializer,
    SurveyListSerializer,
    SurveyWriteSerializer,
    TakingStateSerializer,
)
from .services import (
    add_option,
    add_question,
    create_survey,
    delete_option,
    delete_question,
    delete_survey,
    get_next_question,
    publish_survey,
    submit_answer,
    update_question,
    update_survey,
)
from .utils import (
    catalogue_surveys,
    get_visible_option,
    get_visible_question,
    get_visible_survey,
    survey_detail_queryset,
    survey_statistics_payload,
)


class SurveyViewSet(viewsets.ModelViewSet):
    """CRUD для опросов"""

    pagination_class = CursorPagination

    def get_queryset(self):
        """Возвращает list опросов или детальный queryset"""
        if self.action == "list":
            return catalogue_surveys(user=self.request.user, mine=self._mine_only())
        return survey_detail_queryset(user=self.request.user).order_by("-id")

    def _mine_only(self) -> bool:
        """Возвращает True, если клиент запросил только свои опросы (mine=1/true/yes)."""
        return self.request.query_params.get("mine", "").lower() in {"1", "true", "yes"}

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return SurveyWriteSerializer
        if self.action == "retrieve":
            return SurveyDetailSerializer
        return SurveyListSerializer

    def get_permissions(self):
        if self.action in {
            "update",
            "partial_update",
            "destroy",
            "publish",
            "statistics",
        }:
            return [IsAuthenticated(), IsSurveyAuthor()]
        if self.action == "create":
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer: SurveyWriteSerializer) -> None:
        serializer.instance = create_survey(
            author=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer: SurveyWriteSerializer) -> None:
        serializer.instance = update_survey(
            survey=serializer.instance, **serializer.validated_data
        )

    def perform_destroy(self, instance: Survey) -> None:
        delete_survey(survey_id=instance.id)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request: Request, pk: str | None = None) -> Response:
        """Валидирует и публикует опрос"""
        survey = self.get_object()
        survey = publish_survey(survey_id=survey.id)
        survey = survey_detail_queryset(user=request.user).get(pk=survey.pk)
        return Response(
            SurveyDetailSerializer(survey, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["get"], url_path="stats")
    def statistics(self, request: Request, pk: str | None = None) -> Response:
        """Получение статистики по опросу"""
        survey = self.get_object()
        return Response(survey_statistics_payload(survey))


class NextQuestionView(APIView):
    """Возвращает первый неотвеченный вопрос для текущего респондента."""

    permission_classes = (IsSurveyRespondent,)

    @extend_schema(responses=TakingStateSerializer)
    def get(self, request: Request, survey_id: int) -> Response:
        """Возвращает первый неотвеченный вопрос."""
        logger.info(f">>>>>>>>>  NextQuestionView.get {request.user=} / {survey_id=}.")
        state = get_next_question(survey_id=survey_id, user=request.user)
        logger.info(f">>>>>>>>>  NextQuestionView.get {state=}.")
        return Response(TakingStateSerializer(state).data)


class SubmitAnswerView(APIView):
    """Сохраняет ответ и возвращает следующий вопрос или заваершение опроса"""

    permission_classes = (IsSurveyRespondent,)

    @extend_schema(
        request=SubmitAnswerSerializer, responses={201: TakingStateSerializer}
    )
    def post(self, request: Request, survey_id: int) -> Response:
        """Сохраняет ответ и возвращает следующий вопрос или завершение"""
        logger.info(f">>>>>>>>>  SubmitAnswerView.post {request.user=} / {survey_id=}.")
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        state = submit_answer(
            survey_id=survey_id,
            user=request.user,
            **serializer.validated_data,
        )
        return Response(
            TakingStateSerializer(state).data, status=status.HTTP_201_CREATED
        )


class SurveyNestedMixin:
    """Разрешает видимый опрос/вопрос и применяет объектные права."""

    permission_classes = (IsAuthorOrReadOnly,)

    def get_survey(self, survey_id: int) -> Survey:
        """Возвращает видимый опрос и проверяет права."""
        survey = get_visible_survey(survey_id=survey_id, user=self.request.user)
        self.check_object_permissions(self.request, survey)
        return survey

    def get_question(self, question_id: int) -> Question:
        """Возвращает видимый вопрос и проверяет объектные права."""
        question = get_visible_question(question_id=question_id, user=self.request.user)
        self.check_object_permissions(self.request, question)
        return question

    def get_option(self, option_id: int) -> Option:
        """Возвращает видимый вариант ответа и проверяет объектные права."""
        option = get_visible_option(option_id=option_id, user=self.request.user)
        self.check_object_permissions(self.request, option)
        return option


class SurveyQuestionListCreateView(SurveyNestedMixin, APIView):
    """Список вопросов опроса или добавление нового вопроса."""

    @extend_schema(responses=QuestionSerializer(many=True))
    def get(self, request: Request, survey_id: int) -> Response:
        """Возвращает список вопросов опроса."""
        survey = self.get_survey(survey_id)
        return Response(QuestionSerializer(survey.questions.all(), many=True).data)

    @extend_schema(request=QuestionWriteSerializer, responses={201: QuestionSerializer})
    def post(self, request: Request, survey_id: int) -> Response:
        """Добавляет вопрос к опросу."""
        survey = self.get_survey(survey_id)
        serializer = QuestionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = add_question(survey_id=survey.id, **serializer.validated_data)
        return Response(
            QuestionSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


class QuestionDetailView(SurveyNestedMixin, APIView):
    """Чтение, изменение или удаление вопроса."""

    @extend_schema(responses=QuestionSerializer)
    def get(self, request: Request, question_id: int) -> Response:
        """Возвращает вопрос."""
        question = self.get_question(question_id)
        return Response(QuestionSerializer(question).data)

    @extend_schema(request=QuestionWriteSerializer, responses=QuestionSerializer)
    def patch(self, request: Request, question_id: int) -> Response:
        """Частично обновляет вопрос."""
        question = self.get_question(question_id)
        serializer = QuestionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = update_question(question=question, **serializer.validated_data)
        return Response(QuestionSerializer(question).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, question_id: int) -> Response:
        """Удаляет вопрос."""
        question = self.get_question(question_id)
        delete_question(question=question)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestionOptionListCreateView(SurveyNestedMixin, APIView):
    """Список вариантов вопроса или добавление нового варианта."""

    @extend_schema(responses=OptionSerializer(many=True))
    def get(self, request: Request, question_id: int) -> Response:
        """Возвращает список вариантов вопроса."""
        question = self.get_question(question_id)
        return Response(OptionSerializer(question.options.all(), many=True).data)

    @extend_schema(request=OptionWriteSerializer, responses={201: OptionSerializer})
    def post(self, request: Request, question_id: int) -> Response:
        """Добавляет вариант к вопросу."""
        question = self.get_question(question_id)
        serializer = OptionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        option = add_option(question=question, **serializer.validated_data)
        return Response(OptionSerializer(option).data, status=status.HTTP_201_CREATED)


class OptionDetailView(SurveyNestedMixin, APIView):
    """Чтение, изменение или удаление варианта ответа."""

    @extend_schema(responses=OptionSerializer)
    def get(self, request: Request, option_id: int) -> Response:
        """Возвращает вариант ответа."""
        option = self.get_option(option_id)
        return Response(OptionSerializer(option).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, option_id: int) -> Response:
        """Удаляет вариант ответа."""
        option = self.get_option(option_id)
        delete_option(option=option)
        return Response(status=status.HTTP_204_NO_CONTENT)
