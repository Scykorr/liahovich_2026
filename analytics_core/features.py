from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor

from analytics_core.types import DroppedFeature


def drop_low_information(
    df: pd.DataFrame,
    min_unique: int = 3,
    min_variance: float = 1e-12,
) -> tuple[pd.DataFrame, list[DroppedFeature]]:
    dropped: list[DroppedFeature] = []
    keep: list[str] = []
    for column in df.columns:
        series = df[column].astype(float)
        n_unique = int(series.nunique(dropna=True))
        variance = float(series.var(ddof=0)) if len(series) else 0.0
        if n_unique < min_unique:
            dropped.append(
                DroppedFeature(
                    name=column,
                    reason=f"Менее {min_unique} уникальных значений",
                    details={"n_unique": n_unique},
                )
            )
            continue
        if variance < min_variance:
            dropped.append(
                DroppedFeature(
                    name=column,
                    reason="Практически нулевая дисперсия",
                    details={"variance": variance},
                )
            )
            continue
        keep.append(column)
    return df[keep].copy(), dropped


def correlation_screen(
    df: pd.DataFrame,
    threshold: float = 0.80,
    min_keep: int = 2,
) -> tuple[pd.DataFrame, list[DroppedFeature]]:
    remaining = list(df.columns)
    dropped: list[DroppedFeature] = []
    if len(remaining) < 2:
        return df.copy(), dropped

    work = df[remaining].astype(float)
    while len(remaining) > 1:
        corr = work[remaining].corr(method="pearson").abs()
        np.fill_diagonal(corr.values, 0.0)
        max_val = float(corr.max().max())
        if np.isnan(max_val) or max_val < threshold or len(remaining) <= min_keep:
            break
        pair = corr.stack().idxmax()
        left, right = str(pair[0]), str(pair[1])
        mean_corr = corr.mean()
        drop_name = left if float(mean_corr[left]) >= float(mean_corr[right]) else right
        keep_name = right if drop_name == left else left
        remaining.remove(drop_name)
        dropped.append(
            DroppedFeature(
                name=drop_name,
                reason=(
                    f"|Pearson r|={max_val:.3f} >= {threshold} с «{keep_name}»; "
                    f"удалён признак с большей средней |корреляцией|"
                ),
                details={
                    "peer": keep_name,
                    "abs_r": max_val,
                    "threshold": threshold,
                    "decision": "drop_higher_mean_abs_correlation",
                },
            )
        )
    return work[remaining].copy(), dropped


def iterative_vif(
    df: pd.DataFrame,
    threshold: float = 5.0,
    min_keep: int = 2,
) -> tuple[pd.DataFrame, list[DroppedFeature], dict[str, float]]:
    remaining = list(df.columns)
    dropped: list[DroppedFeature] = []
    work = df.astype(float)
    final_vifs: dict[str, float] = {}
    if len(remaining) < 2:
        return work.copy(), dropped, {col: 1.0 for col in remaining}

    while len(remaining) > 1:
        matrix = work[remaining].to_numpy(dtype=float)
        vifs: list[float] = []
        for index in range(len(remaining)):
            try:
                value = float(variance_inflation_factor(matrix, index))
            except (ValueError, ZeroDivisionError):
                value = float("inf")
            if np.isnan(value):
                value = float("inf")
            vifs.append(value)
        final_vifs = dict(zip(remaining, vifs, strict=True))
        max_vif = max(vifs)
        if max_vif < threshold or len(remaining) <= min_keep:
            break
        drop_index = int(np.argmax(vifs))
        drop_name = remaining.pop(drop_index)
        dropped.append(
            DroppedFeature(
                name=drop_name,
                reason=f"VIF={max_vif:.3f} >= {threshold}",
                details={"vif": max_vif, "threshold": threshold},
            )
        )
    if remaining:
        matrix = work[remaining].to_numpy(dtype=float)
        vifs = []
        for index in range(len(remaining)):
            try:
                vifs.append(float(variance_inflation_factor(matrix, index)))
            except (ValueError, ZeroDivisionError):
                vifs.append(float("inf"))
        final_vifs = dict(zip(remaining, vifs, strict=True))
    return work[remaining].copy(), dropped, final_vifs
