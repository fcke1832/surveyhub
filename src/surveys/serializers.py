from rest_framework import serializers

from .models import Answer, OptionAnswer, Question, Survey


def _author_name(survey: Survey) -> str:
    return survey.author.username


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionAnswer
        fields = ("id", "text", "position")
        read_only_fields = fields


class OptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionAnswer
        fields = ("id", "text", "position")
        read_only_fields = fields


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)
    answer_count = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            "id",
            "text",
            "position",
            "allow_custom_answer",
            "options",
            "answer_count",
        )
        read_only_fields = fields

    def get_answer_count(self, obj: Question) -> int:
        stats = getattr(obj, "statistics", None)
        return stats.answer_count if stats else 0


class QuestionPublicSerializer(serializers.ModelSerializer):
    options = OptionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "text", "position", "allow_custom_answer", "options")
        read_only_fields = fields


class QuestionWriteSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)
    allow_custom_answer = serializers.BooleanField(required=False, default=True)


class OptionWriteSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class SurveyWriteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Survey
        fields = (
            "id",
            "title",
            "description",
            "status",
            "status_display",
            "author",
            "author_name",
            "is_owner",
            "question_count",
            "created_at",
            "updated_at",
            "published_at",
        )
        read_only_fields = (
            "id",
            "status",
            "status_display",
            "author",
            "author_name",
            "is_owner",
            "question_count",
            "created_at",
            "updated_at",
            "published_at",
        )

    def get_author_name(self, obj: Survey) -> str:
        return _author_name(obj)

    def get_is_owner(self, obj: Survey) -> bool:
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and obj.author_id == request.user.id
        )

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Название не может быть пустым.")
        return value


class SurveyListSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    started_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    my_progress_status = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = (
            "id",
            "title",
            "description",
            "status",
            "status_display",
            "author",
            "author_name",
            "is_owner",
            "question_count",
            "started_count",
            "completed_count",
            "my_progress_status",
            "created_at",
            "published_at",
        )

    def get_author_name(self, obj: Survey) -> str:
        return _author_name(obj)

    def get_is_owner(self, obj: Survey) -> bool:
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and obj.author_id == request.user.id
        )

    def get_started_count(self, obj: Survey) -> int:
        stats = getattr(obj, "statistics", None)
        return stats.started_count if stats else 0

    def get_completed_count(self, obj: Survey) -> int:
        stats = getattr(obj, "statistics", None)
        return stats.completed_count if stats else 0

    def get_my_progress_status(self, obj: Survey) -> str | None:
        """Статус прохождения опроса текущим пользователем."""
        answered = getattr(obj, "my_answered_count", 0) or 0
        if not answered:
            return None
        if answered >= obj.question_count:
            return "completed"
        return "in_progress"


class SurveyDetailSerializer(SurveyListSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(SurveyListSerializer.Meta):
        fields = (*SurveyListSerializer.Meta.fields, "questions")


class SurveyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ("id", "title")
        read_only_fields = fields


class ProgressSerializer(serializers.Serializer):
    answered = serializers.IntegerField()
    total = serializers.IntegerField()
    percent = serializers.IntegerField()


class AnswerPublicSerializer(serializers.ModelSerializer):
    answered_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Answer
        fields = ("question", "option", "custom_text", "answered_at", "duration_ms")
        read_only_fields = fields


class TakingStateSerializer(serializers.Serializer):
    survey = SurveyBriefSerializer(read_only=True)
    question = QuestionPublicSerializer(read_only=True, allow_null=True)
    progress = ProgressSerializer(read_only=True)
    completed = serializers.BooleanField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    duration_ms = serializers.IntegerField(read_only=True)
    submitted_answer = AnswerPublicSerializer(read_only=True, allow_null=True)


class SubmitAnswerSerializer(serializers.Serializer):
    """Input for submitting one answer."""

    question_id = serializers.IntegerField(min_value=1)
    option_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    custom_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs: dict) -> dict:
        option_id = attrs.get("option_id")
        custom_text = (attrs.get("custom_text") or "").strip()
        if option_id is not None and custom_text:
            raise serializers.ValidationError(
                "Выберите вариант или введите свой ответ, но не оба сразу."
            )
        if option_id is None and not custom_text:
            raise serializers.ValidationError(
                "Выберите вариант ответа или введите свой."
            )
        return attrs
