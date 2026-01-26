"""Per-stage timing instrumentation for the video processing pipeline."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@contextmanager
def stage_timing(stage: str, timings: Optional[Dict[str, int]] = None):
    """Context manager that records wall-clock duration for a stage in ms.

    If timings is provided, sets timings[stage] = duration_ms and logs
    a structured line. Use for download, audio_extraction, diarization,
    asr, scene_detection, keyframes, sync, summarization, upload, indexing.
    """
    start = time.perf_counter()
    out: Dict[str, int] = timings if timings is not None else {}
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        out[stage] = elapsed_ms
        logger.info("stage_timing %s=%d ms", stage, elapsed_ms)
