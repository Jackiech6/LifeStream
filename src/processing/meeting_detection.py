"""Meeting detection module.

This module uses LLM to classify video segments as meetings vs non-meeting contexts.
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
    """Detects whether a context represents a meeting or non-meeting setting."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize MeetingDetector.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the OpenAI client for meeting detection."""
        try:
            from openai import OpenAI
            
            if not self.settings.openai_api_key:
                logger.warning("OpenAI API key not configured. Meeting detection will use heuristics.")
                self.client = None
            else:
                self.client = OpenAI(api_key=self.settings.openai_api_key)
                logger.info("OpenAI client initialized for meeting detection")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client for meeting detection: {e}")
            self.client = None
    
    def detect_context_type(
        self,
        context: SynchronizedContext
    ) -> ContextType:
        """Detect if a context is a meeting or non-meeting.
        
        Uses LLM to analyze transcript and visual context, with heuristic fallback.
        
        Args:
            context: SynchronizedContext to analyze.
            
        Returns:
            ContextType enum value.
        """
        # Heuristic-based detection first (fast, no API cost)
        heuristic_type = self._heuristic_detection(context)
        
        # If we have LLM and sufficient context, use LLM for more accurate detection
        if self.client and self._has_sufficient_context(context):
            try:
                llm_type = self._llm_detection(context)
                logger.debug(f"LLM detected: {llm_type}, Heuristic: {heuristic_type}")
                return llm_type
            except Exception as e:
                logger.warning(f"LLM meeting detection failed: {e}, using heuristic")
                return heuristic_type
        
        return heuristic_type
    
    def _has_sufficient_context(self, context: SynchronizedContext) -> bool:
        """Check if context has enough information for LLM detection."""
        has_transcript = any(
            seg.transcript_text and seg.transcript_text.strip() and seg.transcript_text.strip() != "[no transcript]"
            for seg in context.audio_segments
        )
        has_multiple_speakers = len(set(seg.speaker_id for seg in context.audio_segments)) > 1
        has_visual = len(context.video_frames) > 0
        
        # Need at least transcript or multiple speakers
        return has_transcript or has_multiple_speakers or has_visual
    
    def _heuristic_detection(self, context: SynchronizedContext) -> ContextType:
        """Use heuristics to detect meeting vs non-meeting.
        
        Heuristics:
        - Multiple distinct speakers (>1) suggests meeting
        - Meeting keywords in transcript
        - Duration and speaker patterns
        """
        if not context.audio_segments:
            return ContextType.UNKNOWN
        
        # Count distinct speakers
        speaker_ids = set(seg.speaker_id for seg in context.audio_segments)
        num_speakers = len(speaker_ids)
        
        # Check for meeting keywords in transcript
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
        
        meeting_score = sum(1 for keyword in meeting_keywords if keyword in all_transcript)
        non_meeting_score = sum(1 for keyword in non_meeting_keywords if keyword in all_transcript)
        
        # Multiple speakers strongly suggests meeting
        if num_speakers > 1:
            if meeting_score > 0 or non_meeting_score == 0:
                return ContextType.MEETING
            elif non_meeting_score > meeting_score:
                return ContextType.NON_MEETING
        
        # Single speaker: check keywords
        if meeting_score > non_meeting_score:
            return ContextType.MEETING
        elif non_meeting_score > meeting_score:
            return ContextType.NON_MEETING
        
        # Default: unknown if we can't determine
        return ContextType.UNKNOWN
    
    def _llm_detection(self, context: SynchronizedContext) -> ContextType:
        """Use LLM to detect meeting vs non-meeting.
        
        Args:
            context: SynchronizedContext to analyze.
            
        Returns:
            ContextType enum value.
        """
        # Build prompt
        prompt = self._create_detection_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a context classifier. Analyze the provided transcript and context to determine if this is a MEETING or NON-MEETING setting.

MEETING characteristics:
- Multiple participants discussing topics
- Structured agenda, decisions, action items
- Professional/collaborative setting
- Questions and answers between participants
- Planning, reviews, standups, syncs

NON-MEETING characteristics:
- Single speaker (lecture, tutorial, monologue)
- One-way communication (presentation to audience)
- Casual conversation or interview
- Educational content (lesson, course)
- Solo work or narration

Respond with ONLY one word: "MEETING", "NON-MEETING", or "UNKNOWN"."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            if "MEETING" in result and "NON" not in result:
                return ContextType.MEETING
            elif "NON-MEETING" in result or "NONMEETING" in result:
                return ContextType.NON_MEETING
            else:
                return ContextType.UNKNOWN
                
        except Exception as e:
            logger.error(f"LLM meeting detection failed: {e}")
            return self._heuristic_detection(context)
    
    def _create_detection_prompt(self, context: SynchronizedContext) -> str:
        """Create prompt for LLM meeting detection."""
        lines = []
        
        # Add transcript
        if context.audio_segments:
            lines.append("Transcript:")
            for seg in context.audio_segments[:10]:  # Limit to first 10 segments
                transcript = (seg.transcript_text or "").strip()
                if transcript and transcript != "[no transcript]":
                    lines.append(f"[{seg.speaker_id}]: {transcript}")
        
        # Add speaker count
        speaker_ids = set(seg.speaker_id for seg in context.audio_segments)
        lines.append(f"\nNumber of distinct speakers: {len(speaker_ids)}")
        lines.append(f"Speaker IDs: {', '.join(sorted(speaker_ids))}")
        
        # Add visual context
        if context.video_frames:
            lines.append(f"\nVisual context: {len(context.video_frames)} keyframes detected")
            scene_changes = sum(1 for f in context.video_frames if f.scene_change_detected)
            if scene_changes > 0:
                lines.append(f"Scene changes: {scene_changes}")
        
        return "\n".join(lines)
    
    def get_context_metadata(
        self,
        context: SynchronizedContext
    ) -> Dict[str, Any]:
        """Get metadata about context type and meeting characteristics.
        
        Args:
            context: SynchronizedContext to analyze.
            
        Returns:
            Dictionary with context_type, is_meeting, num_speakers, etc.
        """
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
