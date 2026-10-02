from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any


_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|otp|authorization|cookie|resume(?:_text)?|oauth[_-]?(?:token|secret|credential))"
)
_SENSITIVE_VALUE = re.compile(r"(?i)(bearer\s+)[^\s]+|((?:token|secret|password|otp)[=:]\s*)[^,\s]+")


def redact_sensitive(value: Any, *, key: str | None = None) -> Any:
    """Return a log-safe representation without exposing credential-like values."""
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub(lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", value)
    if isinstance(value, dict):
        return {str(item_key): redact_sensitive(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return type(value)(redact_sensitive(item) for item in value)
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_sensitive(record.args)
            else:
                record.args = tuple(redact_sensitive(item) for item in record.args)
        return True


def install_log_redaction(loggers: Iterable[logging.Logger]) -> None:
    redactor = RedactingFilter()
    for logger in loggers:
        logger.addFilter(redactor)
        for handler in logger.handlers:
            handler.addFilter(redactor)