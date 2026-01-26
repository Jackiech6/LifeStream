"""LLM summarization and synthesis module.

This module handles LLM-based summarization of synchronized contexts
into structured daily summaries.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from src.models.data_models import SynchronizedContext, TimeBlock, DailySummary
from src.utils.openai_retry import with_429_retry
from config.settings import Settings

logger = logging.getLogger(__name__)


class LLMSummarizer:
    """Handles LLM-based summarization of synchronized contexts."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize LLMSummarizer.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self.model = self.settings.llm_model
        self._check_dependencies()
        self._initialize_client()
    
    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        try:
            import openai
            logger.info("OpenAI library available")
        except ImportError:
            raise ImportError(
                "OpenAI library not installed. "
                "Install with: pip install openai"
            )
    
    def _initialize_client(self) -> None:
        """Initialize the LLM client."""
        try:
            from openai import OpenAI
            
            if not self.settings.openai_api_key:
                logger.warning("OpenAI API key not configured. Summarization will fail.")
                self.client = None
            else:
                self.client = OpenAI(api_key=self.settings.openai_api_key)
                logger.info(f"OpenAI client initialized (model: {self.model})")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def summarize_context(
        self,
        context: SynchronizedContext,
        model: Optional[str] = None
    ) -> TimeBlock:
        """Summarize a synchronized context into a TimeBlock.
        
        Args:
            context: SynchronizedContext to summarize.
            model: LLM model to use. If None, uses settings default.
            
        Returns:
            TimeBlock object with summarized information.
            
        Raises:
            ValueError: If summarization fails or API key is missing.
        """
        if model is None:
            model = self.model
        
        if not self.client:
            raise ValueError(
                "OpenAI client not initialized. "
                "Set OPENAI_API_KEY in .env file."
            )
        
        has_audio = bool(context.audio_segments)
        has_visual = bool(context.video_frames)

        # Empty 5-minute window (no speech, no overlapping keyframes): create minimal block
        if not has_audio and not has_visual:
            logger.info(
                "Context %.2fs–%.2fs has no audio or keyframes; creating minimal time block",
                context.start_timestamp,
                context.end_timestamp,
            )
            return self._create_default_timeblock(context)

        prompt = self._create_prompt(context)
        visual_context = self._get_visual_context(context)

        # Get meeting context
        is_meeting = context.metadata.get('is_meeting')
        context_type = context.metadata.get('context_type', 'unknown')
        
        # Call LLM with 429 retry
        logger.info(f"Summarizing context: {context.start_timestamp:.2f}s - {context.end_timestamp:.2f}s "
                   f"(type: {context_type})")
        messages = [
            {"role": "system", "content": self._get_system_prompt(is_meeting=is_meeting)},
            {"role": "user", "content": prompt + "\n\nVisual Context:\n" + visual_context},
        ]

        def _create():
            return self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

        try:
            response = with_429_retry(_create, max_retries=5, log=logger)
            summary_text = response.choices[0].message.content
            time_block = self._parse_llm_response(summary_text, context)
            logger.info(f"Summarization complete: {time_block.activity}")
            return time_block
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise RuntimeError(
                f"LLM summarization failed (mandatory feature): {e}. "
                "Ensure OpenAI API key is configured and API is accessible."
            ) from e
    
    def _get_system_prompt(self, is_meeting: Optional[bool] = None) -> str:
        """Get the system prompt for LLM (Stage 1/2: per-speaker, scene-aware, action items)."""
        base_prompt = """You are a diary summarization system. For each 5-minute chunk you receive:
1) Diarized transcript (speech merged with deterministic speaker IDs)
2) Scene-aware visual context (significant scene changes overlapping the chunk)

Produce a structured Markdown entry with these sections. Use EXACT headers and bullets.

## [START_TIME] - [END_TIME]: [Activity Title]
* **Location:** [inferred from visuals, or "Unknown"]
* **Activity:** [specific description, never the word "Activity"]
* **Source Reliability:** [High/Medium/Low]
* **Participants:**
  * **Speaker_01:** [name if known, else "Speaker_01"]
  (list each speaker present in the transcript)

* **Per-Speaker Summary:**
  * **Speaker_01:** [Concise summary of what this speaker said during the time window. Attribute content clearly.]
  * **Speaker_02:** [Same for each speaker. Explicitly list speakers and their contributions.]

* **Visual Summary:** [Describe dominant activities or environmental changes suggested by scene changes. Do NOT list raw frame-level details. Only significant scene changes should influence this. If no relevant scenes: "No significant visual changes in this window."]

* **Action Items:**
  * [ ] **Speaker_01:** [item]   (attribute to responsible speaker when possible)
  * [ ] [item]   (use unattributed if no clear owner)

RULES:
- Use deterministic speaker IDs from the transcript (Speaker_01, Speaker_02, etc.). Never invent speakers.
- Per-Speaker Summary: exactly one bullet per speaker, concise summary of their contributions in this window.
- Visual Summary: scene-aware only; dominant activities/env changes, not frame filenames or timestamps.
- Action Items: infer from transcript; attribute to speaker whenever possible. Use "**Speaker_XX:** item" format."""
        if is_meeting is True:
            base_prompt += """

CONTEXT: MEETING. Emphasize agenda, decisions, action items, and explicit per-speaker contributions."""
        elif is_meeting is False:
            base_prompt += """

CONTEXT: NON-MEETING (lecture, tutorial, solo). Focus on content covered; fewer action items unless explicit."""
        return base_prompt
    
    def _create_prompt(self, context: SynchronizedContext) -> str:
        """Create the prompt for LLM: diarized transcript (deterministic speaker IDs)."""
        lines = [
            "Diarized transcript for this 5-minute chunk (speech merged with deterministic speaker diarization).",
            "Provide a per-speaker summary and attribute action items to speakers when possible.",
            "",
            "Transcript:",
        ]
        if context.audio_segments:
            for seg in context.audio_segments:
                start_str = self._format_timestamp(seg.start_time)
                end_str = self._format_timestamp(seg.end_time)
                transcript = (seg.transcript_text or "").strip() or "[no transcript]"
                lines.append(f"[{seg.speaker_id}] ({start_str}-{end_str}): {transcript}")
        else:
            lines.append("[No speech in this time window]")
        return "\n".join(lines)

    def _get_visual_context(self, context: SynchronizedContext) -> str:
        """Scene-aware visual context: significant scene changes overlapping the chunk.

        Describe dominant activities or environmental changes; no raw frame-level details.
        """
        if not context.video_frames:
            return "No scene changes overlap this 5-minute chunk. Use 'No significant visual changes in this window.' in Visual Summary if appropriate."
        timestamps = sorted({f.timestamp for f in context.video_frames})
        ts_str = ", ".join(self._format_timestamp(t) for t in timestamps)
        return (
            f"Significant scene changes at: {ts_str}. "
            "Summarize dominant activities or environmental changes implied by these scene boundaries. "
            "Do NOT list frame filenames or raw frame-level details."
        )
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format timestamp in seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _activity_from_transcript(self, context: SynchronizedContext, max_chars: int = 80) -> Optional[str]:
        """Derive a short activity description from context transcript. Used as fallback when LLM returns generic 'Activity'."""
        if not context.audio_segments:
            return None
        parts = []
        for seg in context.audio_segments[:5]:
            t = (seg.transcript_text or "").strip()
            if t and t != "[no transcript]":
                parts.append(t)
        if not parts:
            return None
        combined = " ".join(parts)
        if len(combined) <= max_chars:
            return combined.strip()
        return combined[: max_chars].rsplit(maxsplit=1)[0].strip() + "…"

    def _parse_llm_response(self, response_text: str, context: SynchronizedContext) -> TimeBlock:
        """Parse LLM response into TimeBlock (per-speaker, visual summary, action items)."""
        from src.models.data_models import Participant
        import re

        start_time_str = self._format_time_string(context.start_timestamp)
        end_time_str = self._format_time_string(context.end_timestamp)

        # Activity (## START - END: Activity; use last colon to avoid splitting timestamps)
        activity: Optional[str] = None
        if "##" in response_text:
            first = response_text.split("##")[1].split("\n")[0].strip()
            if ":" in first:
                activity = first.rsplit(":", 1)[-1].strip()
        if (not activity or activity.lower() == "activity") and "**Activity:**" in response_text:
            for line in response_text.split("\n"):
                if "**Activity:**" in line:
                    activity = line.split("**Activity:**", 1)[-1].strip()
                    break
        if not activity or activity.strip().lower() == "activity":
            activity = self._activity_from_transcript(context)
        if not activity:
            activity = "No speech detected" if not context.audio_segments else "Activity"

        # Location
        location = None
        if "**Location:**" in response_text:
            for line in response_text.split("\n"):
                if "**Location:**" in line:
                    location = line.split("**Location:**", 1)[-1].strip()
                    break

        # Per-Speaker Summary: **Speaker_01:** ... per line (stop at next section)
        per_speaker_summary: Dict[str, str] = {}
        transcript_summary: Optional[str] = None
        if "**Per-Speaker Summary:**" in response_text:
            in_block = False
            for line in response_text.split("\n"):
                if "**Per-Speaker Summary:**" in line:
                    in_block = True
                    continue
                if "**Visual Summary:**" in line or "**Action Items:**" in line:
                    in_block = False
                if not in_block:
                    continue
                if line.strip().startswith("*") and "**" in line:
                    m = re.search(r"\*\*([^*]+):\*\*\s*(.*)", line.strip())
                    if m:
                        sid, summary = m.group(1).strip(), m.group(2).strip()
                        if sid and (sid.startswith("Speaker") or "Speaker" in sid):
                            per_speaker_summary[sid] = summary
                elif line.strip() and not line.strip().startswith("*"):
                    break
        if not per_speaker_summary and "**Transcript Summary:**" in response_text:
            for line in response_text.split("\n"):
                if "**Transcript Summary:**" in line:
                    transcript_summary = line.split("**Transcript Summary:**", 1)[-1].strip()
                    break

        # Visual Summary
        visual_summary = None
        if "**Visual Summary:**" in response_text:
            for line in response_text.split("\n"):
                if "**Visual Summary:**" in line:
                    visual_summary = line.split("**Visual Summary:**", 1)[-1].strip()
                    break
            if not visual_summary:
                in_block = False
                vs_lines = []
                for line in response_text.split("\n"):
                    if "**Visual Summary:**" in line:
                        in_block = True
                        continue
                    if in_block and line.strip() and not line.strip().startswith("*"):
                        vs_lines.append(line.strip())
                    elif in_block and line.strip().startswith("*"):
                        break
                if vs_lines:
                    visual_summary = " ".join(vs_lines)

        # Participants
        participants = []
        if context.audio_segments:
            speaker_ids = list(set(seg.speaker_id for seg in context.audio_segments))
            for speaker_id in speaker_ids:
                name = speaker_id if speaker_id not in ("unknown", "Speaker_Unknown") else "Unidentified speaker"
                participants.append(Participant(speaker_id=speaker_id, real_name=name))

        # Action items (allow "**Speaker_XX:** item" or "item")
        action_items: List[str] = []
        if "**Action Items:**" in response_text:
            in_block = False
            for line in response_text.split("\n"):
                if "**Action Items:**" in line:
                    in_block = True
                    continue
                if in_block and line.strip().startswith("*"):
                    raw = line.strip().lstrip("*").strip().lstrip("[ ]").strip()
                    if raw:
                        action_items.append(raw)
                elif in_block and line.strip() and not line.strip().startswith("*"):
                    break

        source_reliability = "Medium"
        if len(context.audio_segments) > 5 and len(context.video_frames) > 3:
            source_reliability = "High"
        elif len(context.audio_segments) < 2 or len(context.video_frames) < 1:
            source_reliability = "Low"

        context_type = context.metadata.get("context_type")
        is_meeting = context.metadata.get("is_meeting")

        return TimeBlock(
            start_time=start_time_str,
            end_time=end_time_str,
            activity=activity,
            location=location,
            source_reliability=source_reliability,
            context_type=context_type,
            is_meeting=is_meeting,
            participants=participants,
            transcript_summary=transcript_summary,
            per_speaker_summary=per_speaker_summary,
            visual_summary=visual_summary,
            action_items=action_items,
            audio_segments=context.audio_segments,
            video_frames=context.video_frames,
        )
    
    def _format_time_string(self, seconds: float) -> str:
        """Format timestamp in seconds to HH:MM:SS format."""
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _create_default_timeblock(self, context: SynchronizedContext) -> TimeBlock:
        """Create a default TimeBlock when summarization fails."""
        from src.models.data_models import Participant

        start_time_str = self._format_time_string(context.start_timestamp)
        end_time_str = self._format_time_string(context.end_timestamp)

        activity = self._activity_from_transcript(context)
        if not activity:
            activity = "No speech detected" if not context.audio_segments else "Visual segment only"

        participants = []
        if context.audio_segments:
            speaker_ids = list(set(seg.speaker_id for seg in context.audio_segments))
            for speaker_id in speaker_ids:
                name = speaker_id if speaker_id not in ("unknown", "Speaker_Unknown") else "Unidentified speaker"
                participants.append(Participant(speaker_id=speaker_id, real_name=name))

        # Get meeting context from metadata
        context_type = context.metadata.get('context_type')
        is_meeting = context.metadata.get('is_meeting')

        return TimeBlock(
            start_time=start_time_str,
            end_time=end_time_str,
            activity=activity,
            source_reliability="Low",
            context_type=context_type,
            is_meeting=is_meeting,
            participants=participants,
            per_speaker_summary={},
            visual_summary=None,
            audio_segments=context.audio_segments,
            video_frames=context.video_frames,
        )
    
    def format_markdown_output(self, daily_summary: DailySummary) -> str:
        """Format DailySummary as Markdown.
        
        Args:
            daily_summary: DailySummary to format.
            
        Returns:
            Markdown-formatted string.
        """
        return daily_summary.to_markdown()
    
    def create_daily_summary(
        self,
        contexts: List[SynchronizedContext],
        date: Optional[str] = None,
        video_source: Optional[str] = None
    ) -> DailySummary:
        """Create a DailySummary from synchronized contexts.
        
        Args:
            contexts: List of SynchronizedContext objects.
            date: Date in YYYY-MM-DD format. If None, uses today's date.
            video_source: Source video file path.
            
        Returns:
            DailySummary object.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Summarize each context (exactly one ChatGPT call per 5‑min chunk)
        time_blocks = []
        for context in contexts:
            try:
                time_block = self.summarize_context(context)
                time_blocks.append(time_block)
            except Exception as e:
                logger.error(f"Failed to summarize context {context.start_timestamp:.2f}s: {e}")
                time_block = self._create_default_timeblock(context)
                time_blocks.append(time_block)
        
        # Calculate total duration
        total_duration = 0.0
        if contexts:
            total_duration = max(ctx.end_timestamp for ctx in contexts)
        
        return DailySummary(
            date=date,
            video_source=video_source,
            time_blocks=time_blocks,
            total_duration=total_duration,
            created_at=datetime.now()
        )
