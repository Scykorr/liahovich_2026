"""Один поток для BLAS/OpenMP. Вызывать до первого импорта NumPy."""

from __future__ import annotations

import os

THREAD_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def configure_threads() -> None:
    for name in THREAD_VARS:
        os.environ.setdefault(name, "1")


def thread_mode() -> dict[str, str]:
    return {name: os.environ.get(name, "") for name in THREAD_VARS}


configure_threads()
