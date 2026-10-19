from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IssueLevel = Literal["error", "warning"]
ScalerName = Literal["standard", "robust"]


@dataclass(frozen=True)
class PrecinctRow:
    row_number: int
    territory_code: str
    precinct_code: str
    registered_voters: int
    ballots_in_boxes: int
    outside_ballots: int
    valid_ballots: int
    invalid_ballots: int
    candidate_votes: dict[str, int]


@dataclass
class ValidationIssue:
    level: IssueLevel
    code: str
    field: str
    message: str
    row_number: int | None = None
    territory_code: str = ""
    precinct_code: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DroppedFeature:
    name: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


FeatureScreenMode = Literal["diagnostic", "strict"]

_CONFIG_ALIASES = {
    "bootstrap_repeats": "subsample_repeats",
    "bootstrap_fraction": "subsample_fraction",
    "bootstrap_top_n": "subsample_top_n",
}


@dataclass
class PipelineConfig:
    seed: int = 42
    missing_rule: str = "error_blocks"
    outlier_rule: str = "mark_only"
    min_unique: int = 2
    min_variance: float = 1e-12
    corr_threshold: float = 0.80
    vif_threshold: float = 5.0
    feature_screen_mode: FeatureScreenMode = "diagnostic"
    feature_combo_min: int = 2
    feature_combo_max: int = 4
    combo_must_include: list[str] = field(default_factory=list)
    combo_must_include_any: list[str] = field(default_factory=list)
    k_min: int = 2
    k_max: int = 6
    scaler: ScalerName = "standard"
    n_init: int = 20
    min_cluster_share: float = 0.05
    subsample_repeats: int = 100
    subsample_fraction: float = 0.80
    subsample_top_n: int = 5
    silhouette_max_rows: int = 2000
    stability_ari_mean_min: float = 0.75
    stability_ari_p10_min: float = 0.60
    sil_weight: float = 0.45
    ch_weight: float = 0.30
    db_weight: float = 0.25
    internal_weight: float = 0.65
    ari_weight: float = 0.35
    simplicity_delta: float = 0.02
    selected_features: list[str] | None = None
    outlier_zscore: float = 4.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "missing_rule": self.missing_rule,
            "outlier_rule": self.outlier_rule,
            "min_unique": self.min_unique,
            "min_variance": self.min_variance,
            "corr_threshold": self.corr_threshold,
            "vif_threshold": self.vif_threshold,
            "feature_screen_mode": self.feature_screen_mode,
            "feature_combo_min": self.feature_combo_min,
            "feature_combo_max": self.feature_combo_max,
            "combo_must_include": list(self.combo_must_include),
            "combo_must_include_any": list(self.combo_must_include_any),
            "k_min": self.k_min,
            "k_max": self.k_max,
            "scaler": self.scaler,
            "n_init": self.n_init,
            "min_cluster_share": self.min_cluster_share,
            "subsample_repeats": self.subsample_repeats,
            "subsample_fraction": self.subsample_fraction,
            "subsample_top_n": self.subsample_top_n,
            "silhouette_max_rows": self.silhouette_max_rows,
            "stability_ari_mean_min": self.stability_ari_mean_min,
            "stability_ari_p10_min": self.stability_ari_p10_min,
            "sil_weight": self.sil_weight,
            "ch_weight": self.ch_weight,
            "db_weight": self.db_weight,
            "internal_weight": self.internal_weight,
            "ari_weight": self.ari_weight,
            "simplicity_delta": self.simplicity_delta,
            "selected_features": self.selected_features,
            "outlier_zscore": self.outlier_zscore,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
        payload = dict(data)
        for old, new in _CONFIG_ALIASES.items():
            if old in payload and new not in payload:
                payload[new] = payload[old]
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        cleaned = {key: value for key, value in payload.items() if key in known}
        return cls(**cleaned)


@dataclass
class StabilityReport:
    ari_mean: float | None
    ari_p10: float | None
    ari_p90: float | None
    ari_sd: float | None
    successes: int
    repeats: int
    indices: list[list[int]]


@dataclass
class CandidateResult:
    features: list[str]
    k: int
    scaler: str
    silhouette: float | None
    calinski_harabasz: float | None
    davies_bouldin: float | None
    min_cluster_share: float
    internal_score: float | None = None
    ari_mean: float | None = None
    ari_p10: float | None = None
    ari_p90: float | None = None
    ari_sd: float | None = None
    ari_percentile: float | None = None
    total_score: float | None = None
    stability_successes: int | None = None
    stability_repeats: int = 0
    stability_indices: list[list[int]] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    passes_stability: bool = False
    is_alternative: bool = False
    silhouette_rows: int = 0
    rejected: bool = False
    reject_reason: str = ""
    n_used: int = 0
    n_excluded: int = 0
    labels: list[int] = field(default_factory=list)
    distances: list[float] = field(default_factory=list)
    precinct_ids: list[str] = field(default_factory=list)
    centers: dict[int, dict[str, float]] = field(default_factory=dict)
    sizes: dict[int, int] = field(default_factory=dict)
    boxplot: dict[str, Any] = field(default_factory=dict)
    silhouette_samples: list[float] = field(default_factory=list)
    tik_distribution: dict[str, dict[int, int]] = field(default_factory=dict)
    feature_matrix: list[list[float]] = field(default_factory=list)

    @property
    def complexity(self) -> int:
        return len(self.features) * self.k


@dataclass
class PipelineResult:
    config: PipelineConfig
    n_input: int
    n_used: int
    n_excluded: int
    excluded_ids: list[str]
    outlier_ids: list[str]
    feature_columns: list[str]
    dropped_features: list[DroppedFeature]
    candidates: list[CandidateResult]
    recommended_index: int | None
    library_versions: dict[str, str]
    fixed_leader: str = ""
    models_calculated: int = 0
    models_admissible: int = 0
    models_stability_checked: int = 0
    models_stability_passed: int = 0
    warnings: list[str] = field(default_factory=list)
