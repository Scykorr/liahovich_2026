from __future__ import annotations

import pandas as pd

from analytics_core.features import correlation_screen, drop_low_information, iterative_vif


def test_drop_low_unique_and_variance() -> None:
    df = pd.DataFrame(
        {
            "const": [1.0, 1.0, 1.0, 1.0],
            "almost": [1.0, 1.0, 1.0, 1.000000000001],
            "ok": [1.0, 2.0, 3.0, 10.0],
            "ok2": [4.0, 5.0, 9.0, 1.0],
        }
    )
    kept, dropped = drop_low_information(df, min_unique=3, min_variance=1e-8)
    names = {item.name for item in dropped}
    assert "const" in names
    assert "ok" in kept.columns
    assert "ok2" in kept.columns


def test_correlation_screen_drops_one_of_pair() -> None:
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [2.0, 4.0, 6.0, 8.0, 10.0],
            "c": [9.0, 1.0, 4.0, 8.0, 0.0],
        }
    )
    kept, dropped = correlation_screen(df, threshold=0.80)
    assert dropped
    assert "c" in kept.columns
    assert len(kept.columns) == 2


def test_iterative_vif_drops_collinear() -> None:
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "b": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
            "c": [3.0, 1.0, 4.0, 2.0, 8.0, 0.0],
        }
    )
    kept, dropped, vifs = iterative_vif(df, threshold=5.0)
    assert dropped
    assert len(kept.columns) < 3
    assert vifs
