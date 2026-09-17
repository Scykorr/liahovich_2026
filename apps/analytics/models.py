from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimestampedUUIDModel
from apps.datasets.models import Dataset, PrecinctRecord
from apps.projects.models import Project


class AnalysisRun(TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        QUEUED = "queued", "В очереди"
        RUNNING = "running", "Выполняется"
        SUCCEEDED = "succeeded", "Успешно"
        FAILED = "failed", "Ошибка"
        CANCELLED = "cancelled", "Отменён"

    project = models.ForeignKey(Project, related_name="analysis_runs", on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, related_name="runs", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    config_json = models.JSONField(default=dict)
    seed = models.IntegerField(default=42)
    library_versions = models.JSONField(default=dict)
    progress = models.PositiveSmallIntegerField(default=0)
    progress_message = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=64, blank=True)
    recommended_candidate = models.ForeignKey(
        "ModelCandidate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recommended_for",
    )
    selected_candidate = models.ForeignKey(
        "ModelCandidate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="selected_for",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_runs",
    )
    n_used = models.PositiveIntegerField(default=0)
    n_excluded = models.PositiveIntegerField(default=0)
    warnings_json = models.JSONField(default=list)
    outlier_ids = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "запуск анализа"
        verbose_name_plural = "запуски анализа"

    def __str__(self) -> str:
        return f"Run {self.uuid} ({self.status})"


class FeatureDefinition(models.Model):
    run = models.ForeignKey(AnalysisRun, related_name="features", on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    formula = models.CharField(max_length=255, blank=True)
    included = models.BooleanField(default=True)
    drop_reason = models.TextField(blank=True)
    details = models.JSONField(default=dict)

    class Meta:
        verbose_name = "признак"
        verbose_name_plural = "признаки"

    def __str__(self) -> str:
        return self.name


class ModelCandidate(models.Model):
    run = models.ForeignKey(AnalysisRun, related_name="candidates", on_delete=models.CASCADE)
    features = models.JSONField(default=list)
    k = models.PositiveSmallIntegerField()
    scaler = models.CharField(max_length=16)
    silhouette = models.FloatField(null=True, blank=True)
    calinski_harabasz = models.FloatField(null=True, blank=True)
    davies_bouldin = models.FloatField(null=True, blank=True)
    min_cluster_share = models.FloatField(null=True, blank=True)
    internal_score = models.FloatField(null=True, blank=True)
    ari_mean = models.FloatField(null=True, blank=True)
    ari_percentile = models.FloatField(null=True, blank=True)
    total_score = models.FloatField(null=True, blank=True)
    rejected = models.BooleanField(default=False)
    reject_reason = models.TextField(blank=True)
    n_used = models.IntegerField(default=0)
    n_excluded = models.IntegerField(default=0)
    complexity = models.IntegerField(default=0)
    boxplot = models.JSONField(default=dict)
    silhouette_samples = models.JSONField(default=list)
    tik_distribution = models.JSONField(default=dict)
    labels = models.JSONField(default=list)
    precinct_ids = models.JSONField(default=list)

    class Meta:
        ordering = ["-total_score", "-internal_score"]
        verbose_name = "кандидат модели"
        verbose_name_plural = "кандидаты моделей"

    def __str__(self) -> str:
        return f"k={self.k} features={self.features}"


class ClusterAssignment(models.Model):
    candidate = models.ForeignKey(ModelCandidate, related_name="assignments", on_delete=models.CASCADE)
    record = models.ForeignKey(PrecinctRecord, related_name="assignments", on_delete=models.CASCADE)
    cluster_id = models.IntegerField()
    distance_to_center = models.FloatField()

    class Meta:
        unique_together = [("candidate", "record")]
        indexes = [models.Index(fields=["candidate", "cluster_id"])]

    def __str__(self) -> str:
        return f"{self.record_id} -> {self.cluster_id}"


class ClusterProfile(models.Model):
    candidate = models.ForeignKey(ModelCandidate, related_name="profiles", on_delete=models.CASCADE)
    cluster_id = models.IntegerField()
    size = models.IntegerField()
    share = models.FloatField()
    centers = models.JSONField(default=dict)
    stats = models.JSONField(default=dict)

    class Meta:
        unique_together = [("candidate", "cluster_id")]

    def __str__(self) -> str:
        return f"cluster {self.cluster_id}"


class Artifact(TimestampedUUIDModel):
    class Kind(models.TextChoices):
        CHART = "chart", "График"
        EXPORT_CSV = "export_csv", "CSV"
        EXPORT_XLSX = "export_xlsx", "XLSX"
        EXPORT_JSON = "export_json", "JSON"
        REPORT_HTML = "report_html", "HTML-отчёт"
        REPORT_PDF = "report_pdf", "PDF-отчёт"

    run = models.ForeignKey(AnalysisRun, related_name="artifacts", on_delete=models.CASCADE)
    candidate = models.ForeignKey(ModelCandidate, null=True, blank=True, related_name="artifacts", on_delete=models.CASCADE)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    file = models.FileField(upload_to="artifacts/%Y/%m/")
    meta_json = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"{self.kind}:{self.uuid}"
