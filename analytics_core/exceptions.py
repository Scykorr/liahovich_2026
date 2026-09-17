from __future__ import annotations


class AnalyticsError(Exception):
    """Base error for analytics_core."""


class DivisionByZeroError(AnalyticsError):
    """Raised when a formula denominator is zero."""


class PipelineError(AnalyticsError):
    """Raised when the analysis pipeline cannot complete."""
