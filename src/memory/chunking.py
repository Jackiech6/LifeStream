"""Chunking utilities for Stage 2 RAG indexing.

This module converts high-level `DailySummary` objects produced by Stage 1
into semantically meaningful "chunks" that can be embedded and stored in a
vector index.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

from src.models.data_models import DailySummary, TimeBlock, AudioSegment


@dataclass
class Chunk:
    """A unit of text to be embedded and indexed."""

    chunk_id: str
    video_id: str
    date: str
    start_time: float  # seconds from start of day
    end_time: float
    speakers: List[str]
    source_type: str  # e.g. "summary_block", "transcript_block", "action_item"
    text: str
    metadata: Dict[str, Any]

    def to_metadata_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable metadata dict for vector store."""
        data = asdict(self)
        # The vector itself is not part of metadata; keep everything else.
        return {
            "id": data["chunk_id"],
            "video_id": data["video_id"],
            "date": data["date"],
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "speakers": data["speakers"],
            "source_type": data["source_type"],
            "metadata": data["metadata"],
            "text": data["text"],
        }


def _parse_time_to_seconds(time_str: str) -> float:
    """Parse a simple time string into seconds since midnight.

    Supports formats like:
    - "HH:MM"
    - "HH:MM:SS"
    - "HH:MM AM"
    - "HH:MM PM"
    """
    if not time_str:
        return 0.0

    raw = time_str.strip()
    suffix = None
    if raw.upper().endswith("AM") or raw.upper().endswith("PM"):
        parts = raw.split()
        if len(parts) == 2:
            time_part, suffix = parts
        else:
            time_part = raw
    else:
        time_part = raw

    try:
        comps = time_part.split(":")
        hours = int(comps[0])
        minutes = int(comps[1]) if len(comps) > 1 else 0
        seconds = int(comps[2]) if len(comps) > 2 else 0
    except Exception:
        return 0.0

    if suffix:
        suf = suffix.upper()
        if suf == "PM" and hours < 12:
            hours += 12
        if suf == "AM" and hours == 12:
            hours = 0

    return float(hours * 3600 + minutes * 60 + seconds)


def _collect_speakers(block: TimeBlock) -> List[str]:
    """Collect unique speaker IDs from a TimeBlock."""
    speaker_ids = set()

    # Prefer explicit audio segments when available
    for seg in block.audio_segments:
        speaker_ids.add(seg.speaker_id)

    # Also consider participants field
    for participant in block.participants:
        if participant.speaker_id:
            speaker_ids.add(participant.speaker_id)

    return sorted(speaker_ids)


def _build_summary_text(block: TimeBlock) -> str:
    """Create a concise summary text for a time block."""
    lines = [
        f"{block.start_time} - {block.end_time}: {block.activity}",
    ]
    if block.location:
        lines.append(f"Location: {block.location}")
    if block.per_speaker_summary:
        lines.append("Per-speaker summary:")
        for sid, s in block.per_speaker_summary.items():
            lines.append(f"  {sid}: {s}")
    elif block.transcript_summary:
        lines.append(f"Summary: {block.transcript_summary}")
    if block.visual_summary:
        lines.append(f"Visual: {block.visual_summary}")
    if block.action_items:
        lines.append("Action items:")
        for item in block.action_items:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _build_transcript_text(block: TimeBlock, max_segments: int = 10) -> str:
    """Create a transcript-oriented text from audio segments."""
    if not block.audio_segments:
        return ""

    segments: List[AudioSegment] = block.audio_segments[:max_segments]
    lines = ["Transcript excerpts:"]
    for seg in segments:
        content = seg.transcript_text or "[no transcript]"
        lines.append(f"[{seg.speaker_id}] {content}")
    return "\n".join(lines)


def _deterministic_chunk_id(
    video_id: str,
    date: str,
    start_time: float,
    end_time: float,
    source_type: str,
    index: int,
) -> str:
    """Create a deterministic chunk ID based on core fields."""
    base = f"{video_id}|{date}|{start_time:.2f}|{end_time:.2f}|{source_type}|{index}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
    return f"chunk_{digest}"


def make_chunks_from_daily_summary(
    summary: DailySummary,
    *,
    max_chars: int = 1000,
) -> List[Chunk]:
    """Convert a DailySummary into a list of Chunks.

    The current implementation creates up to two chunks per TimeBlock:
    one summary-oriented chunk and, when audio is present, one
    transcript-oriented chunk. More sophisticated splitting (by fixed
    time windows or token counts) can be added later without changing
    the public interface.
    """
    chunks: List[Chunk] = []

    video_id = summary.video_source or "unknown_video"
    date = summary.date

    for idx, block in enumerate(summary.time_blocks):
        start_sec = _parse_time_to_seconds(block.start_time)
        end_sec = _parse_time_to_seconds(block.end_time)
        speakers = _collect_speakers(block)

        base_metadata: Dict[str, Any] = {
            "activity": block.activity,
            "location": block.location,
            "source_reliability": block.source_reliability,
            "participant_count": len(block.participants),
            "audio_segment_count": len(block.audio_segments),
            "video_frame_count": len(block.video_frames),
        }

        # Summary-style chunk ---------------------------------------------------
        summary_text = _build_summary_text(block)
        if summary_text:
            if len(summary_text) > max_chars:
                summary_text = summary_text[: max_chars - 3] + "..."

            chunk_id = _deterministic_chunk_id(
                video_id,
                date,
                start_sec,
                end_sec,
                "summary_block",
                idx * 2,
            )
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    video_id=video_id,
                    date=date,
                    start_time=start_sec,
                    end_time=end_sec,
                    speakers=speakers,
                    source_type="summary_block",
                    text=summary_text,
                    metadata=base_metadata.copy(),
                )
            )

        # Transcript-style chunk ------------------------------------------------
        transcript_text = _build_transcript_text(block)
        if transcript_text:
            if len(transcript_text) > max_chars:
                transcript_text = transcript_text[: max_chars - 3] + "..."

            chunk_id = _deterministic_chunk_id(
                video_id,
                date,
                start_sec,
                end_sec,
                "transcript_block",
                idx * 2 + 1,
            )
            meta_with_flag = base_metadata.copy()
            meta_with_flag["has_transcript"] = True

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    video_id=video_id,
                    date=date,
                    start_time=start_sec,
                    end_time=end_sec,
                    speakers=speakers,
                    source_type="transcript_block",
                    text=transcript_text,
                    metadata=meta_with_flag,
                )
            )

        # Dedicated action item chunks ------------------------------------------
        if block.action_items:
            for ai_idx, item in enumerate(block.action_items):
                text = f"Action item: {item}"
                if len(text) > max_chars:
                    text = text[: max_chars - 3] + "..."

                chunk_id = _deterministic_chunk_id(
                    video_id,
                    date,
                    start_sec,
                    end_sec,
                    "action_item",
                    (idx + 1) * 100 + ai_idx,
                )
                meta_ai = base_metadata.copy()
                meta_ai["is_action_item"] = True

                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        video_id=video_id,
                        date=date,
                        start_time=start_sec,
                        end_time=end_sec,
                        speakers=speakers,
                        source_type="action_item",
                        text=text,
                        metadata=meta_ai,
                    )
                )

    return chunks


__all__ = ["Chunk", "make_chunks_from_daily_summary"]

