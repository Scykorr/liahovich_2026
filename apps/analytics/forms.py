from __future__ import annotations

from django import forms

from analytics_core.types import PipelineConfig
from apps.common.forms import apply_bootstrap


class AnalysisConfigForm(forms.Form):
    seed = forms.IntegerField(label="Зерно генератора", min_value=0, initial=42)
    scaler = forms.ChoiceField(
        label="Масштабирование",
        choices=[("standard", "стандартное"), ("robust", "устойчивое")],
        initial="standard",
    )
    k_min = forms.IntegerField(label="Кластеров мин.", min_value=2, max_value=12, initial=2)
    k_max = forms.IntegerField(label="Кластеров макс.", min_value=2, max_value=12, initial=6)
    feature_combo_min = forms.IntegerField(label="Признаков мин.", min_value=2, max_value=8, initial=2)
    feature_combo_max = forms.IntegerField(label="Признаков макс.", min_value=2, max_value=8, initial=4)
    corr_threshold = forms.FloatField(label="Порог |корреляции Пирсона|", min_value=0.5, max_value=1.0, initial=0.80)
    vif_threshold = forms.FloatField(label="Порог VIF", min_value=1.0, max_value=20.0, initial=5.0)
    min_unique = forms.IntegerField(label="Мин. уникальных значений", min_value=2, initial=3)
    min_variance = forms.FloatField(label="Мин. дисперсия", min_value=0.0, initial=1e-12)
    min_cluster_share = forms.FloatField(label="Мин. доля кластера", min_value=0.0, max_value=0.5, initial=0.05)
    n_init = forms.IntegerField(label="Инициализаций KMeans", min_value=20, initial=20)
    bootstrap_repeats = forms.IntegerField(label="Повторы бутстрэпа", min_value=5, max_value=500, initial=100)
    bootstrap_fraction = forms.FloatField(label="Доля подвыборки", min_value=0.5, max_value=0.95, initial=0.80)
    bootstrap_top_n = forms.IntegerField(label="Топ моделей для индекса Рэнда", min_value=1, max_value=50, initial=10)
    sil_weight = forms.FloatField(label="Вес силуэта", min_value=0, max_value=1, initial=0.45)
    ch_weight = forms.FloatField(label="Вес Калински–Харабаша", min_value=0, max_value=1, initial=0.30)
    db_weight = forms.FloatField(label="Вес Дэвиса–Болдина (инв.)", min_value=0, max_value=1, initial=0.25)
    internal_weight = forms.FloatField(label="Вес внутренней оценки", min_value=0, max_value=1, initial=0.65)
    ari_weight = forms.FloatField(label="Вес индекса Рэнда", min_value=0, max_value=1, initial=0.35)
    simplicity_delta = forms.FloatField(label="Порог упрощения модели", min_value=0, max_value=0.2, initial=0.02)
    outlier_zscore = forms.FloatField(label="Z-оценка выбросов", min_value=2.0, max_value=10.0, initial=4.0)
    missing_rule = forms.ChoiceField(
        label="Пропуски/ошибки строк",
        choices=[("error_blocks", "Ошибки строк блокируют расчёт")],
        initial="error_blocks",
    )
    outlier_rule = forms.ChoiceField(
        label="Выбросы",
        choices=[("mark_only", "Только помечать")],
        initial="mark_only",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("k_min") and cleaned.get("k_max") and cleaned["k_min"] > cleaned["k_max"]:
            self.add_error("k_max", "Максимум кластеров должен быть не меньше минимума")
        if (
            cleaned.get("feature_combo_min")
            and cleaned.get("feature_combo_max")
            and cleaned["feature_combo_min"] > cleaned["feature_combo_max"]
        ):
            self.add_error("feature_combo_max", "Максимум признаков должен быть не меньше минимума")
        return cleaned

    def to_config(self) -> PipelineConfig:
        return PipelineConfig.from_dict(self.cleaned_data)
