"""OpenAI API retry helpers for 429 rate limit errors."""

from __future__ import annotations

import logging
import re
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Match "try again in 446ms" or "in 30s" from OpenAI 429 messages
_RETRY_AFTER_RE = re.compile(r"try again in (\d+)(ms|s)?", re.I)

# TPM limits use a 1-minute rolling window. Sub-minute retries keep hitting the limit.
# Enforce minimum wait so the window can recover; use parsed retry-after only if larger.
MIN_RETRY_DELAY_429_SEC = 15.0
MAX_RETRY_DELAY_SEC = 90.0


def _is_rate_limit(exc: BaseException) -> bool:
    s = str(exc).lower()
    return "429" in str(exc) or "rate_limit" in s or "rate limit" in s


def _retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    m = _RETRY_AFTER_RE.search(str(exc))
    parsed = None
    if m:
        val, unit = int(m.group(1)), (m.group(2) or "s").lower()
        if unit == "ms":
            parsed = val / 1000.0
        else:
            parsed = float(val)
    if parsed is not None:
        delay = max(MIN_RETRY_DELAY_429_SEC, min(MAX_RETRY_DELAY_SEC, parsed))
    else:
        # Exponential backoff: 16, 32, 60, ... (never below MIN)
        delay = max(MIN_RETRY_DELAY_429_SEC, min(MAX_RETRY_DELAY_SEC, 2.0 ** (attempt + 4)))
    return delay


def with_429_retry(
    fn: Callable[[], T],
    max_retries: int = 8,
    log: logging.Logger | None = None,
) -> T:
    """Execute fn(); on 429 rate limit, sleep and retry up to max_retries times.

    Uses retry-after from error message when present (capped by MIN/MAX), else
    exponential backoff. Always waits at least MIN_RETRY_DELAY_429_SEC so TPM
    rolling window can recover.
    """
    log = log or logger
    last: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last = e
            if not _is_rate_limit(e):
                raise
            if attempt >= max_retries - 1:
                raise
            delay = _retry_delay_seconds(e, attempt)
            log.warning(
                "OpenAI rate limit (429), retrying in %.1fs (attempt %d/%d): %s",
                delay,
                attempt + 1,
                max_retries,
                str(e)[:200],
            )
            time.sleep(delay)
    if last is not None:
        raise last
    raise RuntimeError("with_429_retry unreachable")
