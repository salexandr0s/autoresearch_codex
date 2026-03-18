class AutoresearchError(Exception):
    """Base error for the autoresearch runner."""


class ValidationError(AutoresearchError):
    """Raised when configuration or runtime inputs are invalid."""


class BlockedRunError(AutoresearchError):
    """Raised when a run cannot safely continue."""
