from django.contrib import admin

from apps.datasets.models import ColumnMapping, Dataset, PrecinctRecord


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("project", "version", "status", "sha256", "row_count")
    readonly_fields = ("sha256", "schema_json")


@admin.register(ColumnMapping)
class ColumnMappingAdmin(admin.ModelAdmin):
    list_display = ("dataset",)


@admin.register(PrecinctRecord)
class PrecinctRecordAdmin(admin.ModelAdmin):
    list_display = ("dataset", "territory_code", "precinct_code", "row_number")
