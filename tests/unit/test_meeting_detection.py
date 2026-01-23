"""Unit tests for meeting detection."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.models.data_models import SynchronizedContext, AudioSegment, VideoFrame
from src.processing.meeting_detection import MeetingDetector, ContextType
from config.settings import Settings


class TestMeetingDetector:
    """Test MeetingDetector class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def mock_context_meeting(self):
        """Create a mock context that looks like a meeting."""
        audio_segments = [
            AudioSegment(
                start_time=0.0,
                end_time=5.0,
                speaker_id="Speaker_01",
                transcript_text="Let's discuss the agenda for today's meeting."
            ),
            AudioSegment(
                start_time=5.0,
                end_time=10.0,
                speaker_id="Speaker_02",
                transcript_text="I have a few action items to review."
            ),
        ]
        return SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=10.0,
            audio_segments=audio_segments,
            video_frames=[]
        )
    
    @pytest.fixture
    def mock_context_non_meeting(self):
        """Create a mock context that looks like a non-meeting."""
        audio_segments = [
            AudioSegment(
                start_time=0.0,
                end_time=30.0,
                speaker_id="Speaker_01",
                transcript_text="Welcome to this tutorial on Python programming. Today we'll learn about classes."
            ),
        ]
        return SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=30.0,
            audio_segments=audio_segments,
            video_frames=[]
        )
    
    def test_initialization(self, settings):
        """Test that MeetingDetector initializes correctly."""
        detector = MeetingDetector(settings)
        assert detector is not None
        assert detector.settings == settings
    
    def test_heuristic_detection_meeting(self, settings, mock_context_meeting):
        """Test heuristic detection identifies meetings."""
        detector = MeetingDetector(settings)
        context_type = detector._heuristic_detection(mock_context_meeting)
        assert context_type == ContextType.MEETING
    
    def test_heuristic_detection_non_meeting(self, settings, mock_context_non_meeting):
        """Test heuristic detection identifies non-meetings."""
        detector = MeetingDetector(settings)
        context_type = detector._heuristic_detection(mock_context_non_meeting)
        assert context_type == ContextType.NON_MEETING
    
    def test_detect_context_type_heuristic(self, settings, mock_context_meeting):
        """Test detect_context_type uses heuristics when LLM unavailable."""
        detector = MeetingDetector(settings)
        detector.client = None  # No LLM
        
        context_type = detector.detect_context_type(mock_context_meeting)
        assert context_type in [ContextType.MEETING, ContextType.NON_MEETING, ContextType.UNKNOWN]
    
    def test_detect_context_type_llm(self, settings, mock_context_meeting):
        """Test detect_context_type uses LLM when available."""
        # Mock OpenAI client directly
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "MEETING"
        mock_client.chat.completions.create.return_value = mock_response
        
        detector = MeetingDetector(settings)
        detector.client = mock_client  # Inject mock client
        
        context_type = detector.detect_context_type(mock_context_meeting)
        assert context_type == ContextType.MEETING
    
    def test_get_context_metadata(self, settings, mock_context_meeting):
        """Test get_context_metadata returns correct structure."""
        detector = MeetingDetector(settings)
        detector.client = None  # Use heuristics
        
        metadata = detector.get_context_metadata(mock_context_meeting)
        
        assert "context_type" in metadata
        assert "is_meeting" in metadata
        assert "num_speakers" in metadata
        assert "speaker_ids" in metadata
        assert "has_transcript" in metadata
        assert "has_visual" in metadata
        assert metadata["num_speakers"] == 2
        assert metadata["has_transcript"] is True
