from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "project")
    list_filter = ("action",)
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
