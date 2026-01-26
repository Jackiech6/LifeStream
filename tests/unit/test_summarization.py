"""Unit tests for summarization."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

from src.models.data_models import SynchronizedContext, TimeBlock, DailySummary, AudioSegment, VideoFrame
from config.settings import Settings

# Mock OpenAI before importing LLMSummarizer
mock_openai = MagicMock()
sys.modules['openai'] = mock_openai

from src.processing.summarization import LLMSummarizer


class TestLLMSummarizer:
    """Test LLMSummarizer class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock SynchronizedContext."""
        audio_segments = [
            AudioSegment(
                start_time=0.0,
                end_time=5.0,
                speaker_id="Speaker_01",
                transcript_text="Hello, how are you?"
            )
        ]
        video_frames = [
            VideoFrame(timestamp=2.5, frame_path="/tmp/frame1.jpg")
        ]
        return SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=5.0,
            audio_segments=audio_segments,
            video_frames=video_frames
        )
    
    def test_initialization(self, settings):
        """Test that LLMSummarizer initializes correctly."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        assert summarizer is not None
        assert summarizer.settings == settings
    
    def test_format_markdown_output(self, settings, mock_context):
        """Test Markdown formatting."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        
        from datetime import datetime
        from src.models.data_models import DailySummary, TimeBlock
        from src.models.data_models import Participant
        
        time_block = TimeBlock(
            start_time="00:00",
            end_time="00:05",
            activity="Test Activity",
            participants=[Participant(speaker_id="Speaker_01")]
        )
        
        daily_summary = DailySummary(
            date="2026-01-09",
            time_blocks=[time_block]
        )
        
        markdown = summarizer.format_markdown_output(daily_summary)
        assert isinstance(markdown, str)
        assert "Daily Summary" in markdown
        assert "Test Activity" in markdown
    
    def test_create_default_timeblock(self, settings, mock_context):
        """Test default timeblock creation."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        timeblock = summarizer._create_default_timeblock(mock_context)
        
        assert isinstance(timeblock, TimeBlock)
        assert timeblock.start_time is not None
        assert timeblock.end_time is not None
        # Uses transcript-derived activity when available (mock has "Hello, how are you?")
        assert timeblock.activity
        assert "Hello" in timeblock.activity
    
    def test_format_timestamp(self, settings):
        """Test timestamp formatting."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        
        # Test various timestamps
        assert summarizer._format_timestamp(0.0) == "00:00:00"
        assert summarizer._format_timestamp(3661.0) == "01:01:01"
        assert summarizer._format_timestamp(125.5) == "00:02:05"
    
    def test_format_time_string(self, settings):
        """Test time string formatting (HH:MM:SS)."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        
        assert summarizer._format_time_string(0.0) == "00:00:00"
        assert summarizer._format_time_string(3661.0) == "01:01:01"
        assert summarizer._format_time_string(125.5) == "00:02:05"
    
    def test_create_prompt(self, settings, mock_context):
        """Test prompt creation (diarized transcript)."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        prompt = summarizer._create_prompt(mock_context)

        assert isinstance(prompt, str)
        assert "Transcript" in prompt and "Speaker_01" in prompt

    def test_get_visual_context(self, settings, mock_context):
        """Test scene-aware visual context."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        visual_context = summarizer._get_visual_context(mock_context)

        assert isinstance(visual_context, str)
        assert len(visual_context) > 0

    def test_parse_llm_response_per_speaker_visual_action_items(self, settings, mock_context):
        """Test parsing LLM response with Per-Speaker Summary, Visual Summary, Action Items."""
        mock_openai.OpenAI = MagicMock()
        summarizer = LLMSummarizer(settings)
        mock_context.metadata = {"context_type": "meeting", "is_meeting": True}

        response = """## 00:00:00 - 00:05:00: Team standup
* **Location:** Conference room
* **Activity:** Team standup
* **Source Reliability:** High
* **Participants:**
  * **Speaker_01:** Speaker_01
  * **Speaker_02:** Speaker_02
* **Per-Speaker Summary:**
  * **Speaker_01:** Reviewed sprint progress and blockers.
  * **Speaker_02:** Raised API auth blocker; will follow up.
* **Visual Summary:** Screen share of Jira; camera view of attendees.
* **Action Items:**
  * [ ] **Speaker_01:** Send recap by EOD
  * [ ] **Speaker_02:** Unblock API auth
"""
        block = summarizer._parse_llm_response(response, mock_context)
        assert block.activity == "Team standup"
        assert block.per_speaker_summary
        assert "Speaker_01" in block.per_speaker_summary
        assert "sprint" in block.per_speaker_summary["Speaker_01"].lower()
        assert block.visual_summary
        assert "Jira" in block.visual_summary or "Screen" in block.visual_summary
        assert len(block.action_items) >= 2
        assert any("Speaker" in item for item in block.action_items)
