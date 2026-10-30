from django.contrib import admin

from .models import (
    Answer,
    OptionAnswer,
    Question,
    QuestionStatistics,
    Survey,
    SurveyStatistics,
)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    can_delete = False
    fields = ("position", "text", "allow_custom_answer")
    readonly_fields = fields
    ordering = ("position", "id")
    show_change_link = True


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "status", "published_at", "created_at")
    list_filter = ("status", "author", "created_at")
    search_fields = ("title", "author__username")
    readonly_fields = (
        "author",
        "status",
        "published_at",
        "created_at",
        "updated_at",
    )
    inlines = (QuestionInline,)


class OptionAnswerInline(admin.TabularInline):
    model = OptionAnswer
    extra = 0
    can_delete = False
    fields = ("position", "text")
    readonly_fields = fields
    ordering = ("position", "id")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "survey", "position", "text", "allow_custom_answer")
    list_filter = ("survey", "position", "allow_custom_answer")
    search_fields = ("survey__title", "survey__author__username", "text")
    readonly_fields = (
        "survey",
        "position",
        "text",
        "allow_custom_answer",
        "created_at",
        "updated_at",
    )
    inlines = (OptionAnswerInline,)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "position", "text", "is_active")
    list_filter = ("question", "position", "is_active", "created_at")
    search_fields = (
        "question__survey__title",
        "question__survey__author__username",
        "text",
    )
    readonly_fields = (
        "question",
        "position",
        "text",
        "is_active",
        "created_at",
        "updated_at",
    )


@admin.register(SurveyStatistics)
class SurveyStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        "survey",
        "started_count",
        "completed_count",
        "answer_count",
        "custom_answer_count",
        "total_duration_ms",
        "updated_at",
    )
    list_filter = ("survey", "updated_at")
    readonly_fields = [field.name for field in SurveyStatistics._meta.fields]


@admin.register(QuestionStatistics)
class QuestionStatisticsAdmin(admin.ModelAdmin):
    list_display = ("question", "answer_count", "custom_answer_count")
    list_filter = ("question",)
    readonly_fields = [field.name for field in QuestionStatistics._meta.fields]
