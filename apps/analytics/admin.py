from django.contrib import admin

from apps.analytics.models import (
    AnalysisRun,
    Artifact,
    ClusterAssignment,
    ClusterProfile,
    FeatureDefinition,
    ModelCandidate,
)


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("uuid", "project", "status", "seed", "created_at")


@admin.register(ModelCandidate)
class ModelCandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "k", "total_score", "rejected")


admin.site.register(FeatureDefinition)
admin.site.register(ClusterAssignment)
admin.site.register(ClusterProfile)
admin.site.register(Artifact)
