"""LLM summarization and synthesis module.

This module handles LLM-based summarization of synchronized contexts
into structured daily summaries.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from src.models.data_models import SynchronizedContext, TimeBlock, DailySummary
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
        
        prompt = self._create_prompt(context)
        visual_context = self._get_visual_context(context)
        has_audio = bool(context.audio_segments)
        has_visual = bool(context.video_frames)

        # Fast path: no audio and no visual → use default timeblock (avoids LLM call)
        if not has_audio and not has_visual:
            logger.info("No audio or video in context; using default timeblock")
            return self._create_default_timeblock(context)

        # Get meeting context
        is_meeting = context.metadata.get('is_meeting')
        context_type = context.metadata.get('context_type', 'unknown')
        
        # Call LLM
        try:
            logger.info(f"Summarizing context: {context.start_timestamp:.2f}s - {context.end_timestamp:.2f}s "
                       f"(type: {context_type})")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(is_meeting=is_meeting)
                    },
                    {
                        "role": "user",
                        "content": prompt + "\n\nVisual Context:\n" + visual_context
                    }
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            summary_text = response.choices[0].message.content
            
            # Parse response into TimeBlock
            time_block = self._parse_llm_response(summary_text, context)
            
            logger.info(f"Summarization complete: {time_block.activity}")
            return time_block
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Return a default TimeBlock on failure
            return self._create_default_timeblock(context)
    
    def _get_system_prompt(self, is_meeting: Optional[bool] = None) -> str:
        """Get the system prompt for LLM.
        
        Args:
            is_meeting: True if this is a meeting context, False if non-meeting, None if unknown.
        """
        base_prompt = """You are a diary summarization system. Given audio transcripts and visual context, 
generate a structured daily log entry in Markdown format.

Required format:
## [START_TIME] - [END_TIME]: [Activity Title]
* **Location:** [inferred from visuals]
* **Activity:** [brief description]
* **Source Reliability:** [High/Medium/Low]
* **Participants:**
  * **Speaker_01:** [name if known, else "Speaker_01"]
* **Transcript Summary:** [concise summary]
* **Action Items:**
  * [ ] [item description]

Be concise and factual. Infer locations from visual context when possible.
CRITICAL: Never use the generic word "Activity" as the Activity Title or **Activity:** value.
- If there is speech: summarize what was discussed (e.g. "Team standup", "Code review discussion").
- If there is no speech: use "No speech detected" and briefly describe any visual context (e.g. "Silent footage: screen recording").
- Always extract a specific, descriptive activity from the transcript or visuals."""
        
        if is_meeting is True:
            base_prompt += """

CONTEXT: This is a MEETING. Focus on:
- Meeting agenda, topics discussed, decisions made
- Action items and next steps
- Participant contributions and questions
- Key outcomes and follow-ups"""
        elif is_meeting is False:
            base_prompt += """

CONTEXT: This is a NON-MEETING setting (e.g., lecture, tutorial, solo work, casual conversation).
Focus on:
- Main topics or content covered
- Educational or informational content
- Key points or takeaways
- Less emphasis on action items unless explicitly mentioned"""
        
        return base_prompt
    
    def _create_prompt(self, context: SynchronizedContext) -> str:
        """Create the prompt for LLM summarization."""
        lines = ["Audio Transcript:"]
        
        if context.audio_segments:
            for seg in context.audio_segments:
                start_str = self._format_timestamp(seg.start_time)
                end_str = self._format_timestamp(seg.end_time)
                transcript = (seg.transcript_text or "").strip() or "[no transcript]"
                lines.append(f"[{seg.speaker_id}] ({start_str}-{end_str}): {transcript}")
        else:
            lines.append("[No audio segments in this time window — no speech detected]")
        
        return "\n".join(lines)
    
    def _get_visual_context(self, context: SynchronizedContext) -> str:
        """Get visual context description from video frames."""
        if not context.video_frames:
            return "[No video frames in this time window]"
        
        lines = []
        for frame in context.video_frames:
            timestamp_str = self._format_timestamp(frame.timestamp)
            scene_info = "Scene change detected" if frame.scene_change_detected else "Keyframe"
            lines.append(f"* {timestamp_str}: {scene_info} (frame: {Path(frame.frame_path).name})")
        
        return "\n".join(lines)
    
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
        """Parse LLM response into TimeBlock."""
        from src.models.data_models import Participant

        start_time_str = self._format_time_string(context.start_timestamp)
        end_time_str = self._format_time_string(context.end_timestamp)

        # Extract activity: try ## title first, then **Activity:** line
        activity: Optional[str] = None
        if "##" in response_text:
            first = response_text.split("##")[1].split("\n")[0].strip()
            if ":" in first:
                activity = first.split(":", 1)[-1].strip()
        if (not activity or activity.lower() == "activity") and "**Activity:**" in response_text:
            for line in response_text.split("\n"):
                if "**Activity:**" in line:
                    activity = line.split("**Activity:**", 1)[-1].strip()
                    break
        # Reject generic "Activity"; use transcript fallback when available
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

        # Transcript summary: allow same-line or following lines
        transcript_summary = None
        if "**Transcript Summary:**" in response_text:
            for line in response_text.split("\n"):
                if "**Transcript Summary:**" in line:
                    rest = line.split("**Transcript Summary:**", 1)[-1].strip()
                    if rest:
                        transcript_summary = rest
                        break
            if not transcript_summary:
                in_summary = False
                summary_lines = []
                for line in response_text.split("\n"):
                    if "**Transcript Summary:**" in line:
                        in_summary = True
                        continue
                    if in_summary and line.strip() and not line.strip().startswith("*"):
                        summary_lines.append(line.strip())
                    elif in_summary and line.strip().startswith("*"):
                        break
                if summary_lines:
                    transcript_summary = " ".join(summary_lines)

        # Participants: use real_name=speaker_id so we don't show "unknown: unknown"
        participants = []
        if context.audio_segments:
            speaker_ids = list(set(seg.speaker_id for seg in context.audio_segments))
            for speaker_id in speaker_ids:
                name = speaker_id if speaker_id not in ("unknown", "Speaker_Unknown") else "Unidentified speaker"
                participants.append(Participant(speaker_id=speaker_id, real_name=name))

        # Action items
        action_items = []
        if "**Action Items:**" in response_text:
            in_action_items = False
            for line in response_text.split("\n"):
                if "**Action Items:**" in line:
                    in_action_items = True
                    continue
                if in_action_items and line.strip().startswith("*"):
                    item = line.strip().lstrip("*").strip().lstrip("[ ]").strip()
                    if item:
                        action_items.append(item)
                elif in_action_items and line.strip() and not line.strip().startswith("*"):
                    break

        source_reliability = "Medium"
        if len(context.audio_segments) > 5 and len(context.video_frames) > 3:
            source_reliability = "High"
        elif len(context.audio_segments) < 2 or len(context.video_frames) < 1:
            source_reliability = "Low"

        # Get meeting context from metadata
        context_type = context.metadata.get('context_type')
        is_meeting = context.metadata.get('is_meeting')

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
        
        # Summarize each context
        time_blocks = []
        for context in contexts:
            try:
                time_block = self.summarize_context(context)
                time_blocks.append(time_block)
            except Exception as e:
                logger.error(f"Failed to summarize context {context.start_timestamp:.2f}s: {e}")
                # Create default timeblock on failure
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
