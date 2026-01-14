"""LLM summarization and synthesis module.

This module handles LLM-based summarization of synchronized contexts
into structured daily summaries.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import base64
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
        
        # Prepare prompt
        prompt = self._create_prompt(context)
        
        # Get visual context (keyframe descriptions or images)
        visual_context = self._get_visual_context(context)
        
        # Call LLM
        try:
            logger.info(f"Summarizing context: {context.start_timestamp:.2f}s - {context.end_timestamp:.2f}s")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
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
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM."""
        return """You are a diary summarization system. Given audio transcripts and visual context, 
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

Be concise and factual. Infer locations from visual context when possible."""
    
    def _create_prompt(self, context: SynchronizedContext) -> str:
        """Create the prompt for LLM summarization."""
        lines = ["Audio Transcript:"]
        
        if context.audio_segments:
            for seg in context.audio_segments:
                start_str = self._format_timestamp(seg.start_time)
                end_str = self._format_timestamp(seg.end_time)
                transcript = seg.transcript_text or "[no transcript]"
                lines.append(f"[{seg.speaker_id}] ({start_str}-{end_str}): {transcript}")
        else:
            lines.append("[No audio segments in this time window]")
        
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
    
    def _parse_llm_response(self, response_text: str, context: SynchronizedContext) -> TimeBlock:
        """Parse LLM response into TimeBlock.
        
        This is a simplified parser. In production, you'd want more robust parsing.
        """
        # Extract basic information from response
        # For now, create a simple TimeBlock from the context
        
        start_time_str = self._format_time_string(context.start_timestamp)
        end_time_str = self._format_time_string(context.end_timestamp)
        
        # Extract activity from response (first line after ##)
        activity = "Activity"  # Default
        if "##" in response_text:
            first_line = response_text.split("##")[1].split("\n")[0].strip()
            if ":" in first_line:
                activity = first_line.split(":")[-1].strip()
        
        # Extract location if present
        location = None
        if "**Location:**" in response_text:
            loc_line = [line for line in response_text.split("\n") if "**Location:**" in line]
            if loc_line:
                location = loc_line[0].split("**Location:**")[-1].strip()
        
        # Extract transcript summary
        transcript_summary = None
        if "**Transcript Summary:**" in response_text:
            summary_lines = []
            in_summary = False
            for line in response_text.split("\n"):
                if "**Transcript Summary:**" in line:
                    in_summary = True
                    continue
                if in_summary and line.strip() and not line.startswith("*"):
                    summary_lines.append(line.strip())
                elif in_summary and line.startswith("*"):
                    break
            if summary_lines:
                transcript_summary = " ".join(summary_lines)
        
        # Extract participants
        participants = []
        if context.audio_segments:
            speaker_ids = list(set(seg.speaker_id for seg in context.audio_segments))
            from src.models.data_models import Participant
            for speaker_id in speaker_ids:
                participants.append(Participant(speaker_id=speaker_id))
        
        # Extract action items
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
                elif in_action_items and line.strip() and not line.startswith("*"):
                    break
        
        # Determine source reliability
        source_reliability = "Medium"
        if len(context.audio_segments) > 5 and len(context.video_frames) > 3:
            source_reliability = "High"
        elif len(context.audio_segments) < 2 or len(context.video_frames) < 1:
            source_reliability = "Low"
        
        return TimeBlock(
            start_time=start_time_str,
            end_time=end_time_str,
            activity=activity,
            location=location,
            source_reliability=source_reliability,
            participants=participants,
            transcript_summary=transcript_summary,
            action_items=action_items,
            audio_segments=context.audio_segments,
            video_frames=context.video_frames
        )
    
    def _format_time_string(self, seconds: float) -> str:
        """Format timestamp in seconds to HH:MM format."""
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    
    def _create_default_timeblock(self, context: SynchronizedContext) -> TimeBlock:
        """Create a default TimeBlock when summarization fails."""
        start_time_str = self._format_time_string(context.start_timestamp)
        end_time_str = self._format_time_string(context.end_timestamp)
        
        from src.models.data_models import Participant
        
        participants = []
        if context.audio_segments:
            speaker_ids = list(set(seg.speaker_id for seg in context.audio_segments))
            for speaker_id in speaker_ids:
                participants.append(Participant(speaker_id=speaker_id))
        
        return TimeBlock(
            start_time=start_time_str,
            end_time=end_time_str,
            activity="Activity",
            source_reliability="Low",
            participants=participants,
            audio_segments=context.audio_segments,
            video_frames=context.video_frames
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
