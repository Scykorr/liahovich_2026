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


@dataclass
class PipelineConfig:
    seed: int = 42
    missing_rule: str = "error_blocks"
    outlier_rule: str = "mark_only"
    min_unique: int = 3
    min_variance: float = 1e-12
    corr_threshold: float = 0.80
    vif_threshold: float = 5.0
    feature_combo_min: int = 2
    feature_combo_max: int = 4
    k_min: int = 2
    k_max: int = 6
    scaler: ScalerName = "standard"
    n_init: int = 20
    min_cluster_share: float = 0.05
    bootstrap_repeats: int = 100
    bootstrap_fraction: float = 0.80
    bootstrap_top_n: int = 10
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
            "feature_combo_min": self.feature_combo_min,
            "feature_combo_max": self.feature_combo_max,
            "k_min": self.k_min,
            "k_max": self.k_max,
            "scaler": self.scaler,
            "n_init": self.n_init,
            "min_cluster_share": self.min_cluster_share,
            "bootstrap_repeats": self.bootstrap_repeats,
            "bootstrap_fraction": self.bootstrap_fraction,
            "bootstrap_top_n": self.bootstrap_top_n,
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
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {key: value for key, value in data.items() if key in known}
        return cls(**payload)


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
    ari_percentile: float | None = None
    total_score: float | None = None
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
    warnings: list[str] = field(default_factory=list)
