from django.contrib import admin

from apps.validation.models import ValidationIssue


@admin.register(ValidationIssue)
class ValidationIssueAdmin(admin.ModelAdmin):
    list_display = ("dataset", "level", "code", "field", "row_number")
    list_filter = ("level", "code")
