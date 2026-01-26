"""Meeting detection module.

Classifies video segments as meetings vs non-meeting using heuristics only.
No ChatGPT/LLM calls; per guideline, LLM is used only for per-chunk summarization and query synthesis.
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

from src.models.data_models import SynchronizedContext
from config.settings import Settings

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Type of context detected."""
    MEETING = "meeting"
    NON_MEETING = "non-meeting"
    UNKNOWN = "unknown"


class MeetingDetector:
    """Detects whether a context represents a meeting or non-meeting setting.

    Uses heuristics only (speaker count, keywords). No LLM/ChatGPT calls.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def detect_context_type(self, context: SynchronizedContext) -> ContextType:
        """Detect if a context is a meeting or non-meeting using heuristics."""
        return self._heuristic_detection(context)

    def _heuristic_detection(self, context: SynchronizedContext) -> ContextType:
        """Use heuristics to detect meeting vs non-meeting.

        Heuristics:
        - Multiple distinct speakers (>1) suggests meeting
        - Meeting vs non-meeting keywords in transcript
        """
        if not context.audio_segments:
            return ContextType.UNKNOWN

        speaker_ids = set(seg.speaker_id for seg in context.audio_segments)
        num_speakers = len(speaker_ids)

        all_transcript = " ".join(
            seg.transcript_text or ""
            for seg in context.audio_segments
            if seg.transcript_text
        ).lower()

        meeting_keywords = [
            "meeting", "agenda", "discuss", "presentation", "team", "call",
            "conference", "standup", "sync", "review", "planning", "update",
            "decision", "action item", "next steps", "follow up", "q&a",
            "questions", "feedback", "proposal", "suggestion"
        ]
        non_meeting_keywords = [
            "tutorial", "lecture", "lesson", "course", "learning", "teaching",
            "solo", "monologue", "narration", "voiceover", "recording",
            "podcast", "interview", "conversation", "chat", "casual"
        ]

        meeting_score = sum(1 for k in meeting_keywords if k in all_transcript)
        non_meeting_score = sum(1 for k in non_meeting_keywords if k in all_transcript)

        if num_speakers > 1:
            if meeting_score > 0 or non_meeting_score == 0:
                return ContextType.MEETING
            if non_meeting_score > meeting_score:
                return ContextType.NON_MEETING

        if meeting_score > non_meeting_score:
            return ContextType.MEETING
        if non_meeting_score > meeting_score:
            return ContextType.NON_MEETING

        return ContextType.UNKNOWN

    def get_context_metadata(self, context: SynchronizedContext) -> Dict[str, Any]:
        """Metadata about context type (heuristic-based)."""
        context_type = self.detect_context_type(context)
        speaker_ids = set(seg.speaker_id for seg in context.audio_segments)
        return {
            "context_type": context_type.value,
            "is_meeting": context_type == ContextType.MEETING,
            "num_speakers": len(speaker_ids),
            "speaker_ids": list(speaker_ids),
            "has_transcript": any(
                seg.transcript_text and seg.transcript_text.strip()
                for seg in context.audio_segments
            ),
            "has_visual": len(context.video_frames) > 0,
        }
