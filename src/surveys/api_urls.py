"""Survey API URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NextQuestionView, SurveyViewSet

app_name = "surveys_api"

router = DefaultRouter()
router.register("surveys", SurveyViewSet, basename="survey")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "surveys/<int:survey_id>/next-question/",
        NextQuestionView.as_view(),
        name="next-question",
    ),
    # path("surveys/<int:survey_id>/answers/", SubmitAnswerView.as_view(), name="submit-answer"),
    # path(
    #     "surveys/<int:survey_id>/questions/",
    #     SurveyQuestionListCreateView.as_view(),
    #     name="survey-questions",
    # ),
    # path(
    #     "questions/<int:question_id>/",
    #     QuestionDetailView.as_view(),
    #     name="question-detail",
    # ),
    # path(
    #     "questions/<int:question_id>/options/",
    #     QuestionOptionListCreateView.as_view(),
    #     name="question-options",
    # ),
    # path("options/<int:option_id>/", OptionDetailView.as_view(), name="option-detail"),
]
