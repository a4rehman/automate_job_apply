"""Structured error classification for external operations (Phase 16).

Distinguishes retryable (transient) failures from permanent ones so the system
never endlessly retries an error that can never succeed (bad credentials,
malformed payloads, unsupported platforms).
"""
from typing import Optional
import httpx
from app.core.logging_config import logger


class ErrorType:
    TRANSIENT = "TRANSIENT_ERROR"
    PERMANENT = "PERMANENT_ERROR"
    AUTH = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    VALIDATION = "VALIDATION_ERROR"
    NETWORK = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN_ERROR"


# HTTP status codes we will retry
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
# HTTP status codes we will never retry
PERMANENT_STATUS = {400, 401, 403, 404, 405, 410, 422}


def classify_error(exc: BaseException, status_code: Optional[int] = None) -> str:
    """Classify an exception/HTTP status into an ErrorType."""
    if status_code is not None:
        if status_code == 429:
            return ErrorType.RATE_LIMITED
        if status_code in (401, 403):
            return ErrorType.AUTH
        if status_code in PERMANENT_STATUS:
            return ErrorType.PERMANENT
        if status_code in RETRYABLE_STATUS:
            return ErrorType.TRANSIENT
        if 400 <= status_code < 500:
            return ErrorType.PERMANENT
        if status_code >= 500:
            return ErrorType.TRANSIENT

    if isinstance(exc, httpx.TimeoutException):
        return ErrorType.TRANSIENT
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, ConnectionError)):
        return ErrorType.NETWORK
    if isinstance(exc, (httpx.HTTPStatusError,)):
        return classify_error(exc, exc.response.status_code)
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return ErrorType.VALIDATION
    if isinstance(exc, PermissionError):
        return ErrorType.AUTH

    return ErrorType.UNKNOWN


def is_retryable(error_type: str) -> bool:
    """Only transient conditions are retried. Everything else fails fast."""
    return error_type in (ErrorType.TRANSIENT, ErrorType.NETWORK, ErrorType.RATE_LIMITED)


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Exponential backoff with cap: 0.5, 1, 2, 4, 8, 8, ..."""
    return min(cap, base * (2 ** max(0, attempt - 1)))


def log_classified_error(context: str, exc: BaseException, status_code: Optional[int] = None) -> str:
    """Log an error with its classification, never leaking secrets."""
    etype = classify_error(exc, status_code)
    logger.error(f"[{context}] {etype}: {type(exc).__name__}: {exc}")
    return etype