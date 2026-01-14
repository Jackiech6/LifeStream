"""Unit tests for data models."""

import pytest
from datetime import datetime
from src.models.data_models import (
    VideoMetadata,
    AudioSegment,
    VideoFrame,
    Participant,
    TimeBlock,
    DailySummary,
    SynchronizedContext,
)


class TestVideoMetadata:
    """Test VideoMetadata model."""
    
    def test_video_metadata_creation(self):
        """Test creating a VideoMetadata instance."""
        metadata = VideoMetadata(
            file_path="/path/to/video.mp4",
            duration=3600.0,
            fps=30.0,
            resolution=(1920, 1080),
            format="mp4"
        )
        assert metadata.file_path == "/path/to/video.mp4"
        assert metadata.duration == 3600.0
        assert metadata.fps == 30.0
        assert metadata.resolution == (1920, 1080)
        assert metadata.format == "mp4"
    
    def test_video_metadata_json_serializable(self):
        """Test that VideoMetadata is JSON serializable."""
        metadata = VideoMetadata(
            file_path="/path/to/video.mp4",
            duration=3600.0,
            fps=30.0,
            resolution=(1920, 1080),
            format="mp4",
            created_at=datetime(2026, 1, 9, 12, 0, 0)
        )
        # Should not raise an error
        json_str = metadata.model_dump_json()
        assert "video.mp4" in json_str


class TestAudioSegment:
    """Test AudioSegment model."""
    
    def test_audio_segment_creation(self):
        """Test creating an AudioSegment instance."""
        segment = AudioSegment(
            start_time=0.0,
            end_time=5.0,
            speaker_id="Speaker_01",
            transcript_text="Hello world"
        )
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0
        assert segment.duration == 5.0
        assert segment.speaker_id == "Speaker_01"
        assert segment.transcript_text == "Hello world"
    
    def test_audio_segment_to_dict(self):
        """Test converting AudioSegment to dictionary."""
        segment = AudioSegment(
            start_time=0.0,
            end_time=5.0,
            speaker_id="Speaker_01",
            transcript_text="Hello world"
        )
        segment_dict = segment.to_dict()
        assert segment_dict["start_time"] == 0.0
        assert segment_dict["duration"] == 5.0
        assert segment_dict["speaker_id"] == "Speaker_01"


class TestVideoFrame:
    """Test VideoFrame model."""
    
    def test_video_frame_creation(self):
        """Test creating a VideoFrame instance."""
        frame = VideoFrame(
            timestamp=10.5,
            scene_change_detected=True,
            scene_id=1
        )
        assert frame.timestamp == 10.5
        assert frame.scene_change_detected is True
        assert frame.scene_id == 1


class TestParticipant:
    """Test Participant model."""
    
    def test_participant_creation(self):
        """Test creating a Participant instance."""
        participant = Participant(
            speaker_id="Speaker_01",
            real_name="John Doe",
            role="Host"
        )
        assert participant.speaker_id == "Speaker_01"
        assert participant.real_name == "John Doe"
        assert participant.role == "Host"


class TestTimeBlock:
    """Test TimeBlock model."""
    
    def test_time_block_creation(self):
        """Test creating a TimeBlock instance."""
        block = TimeBlock(
            start_time="09:00 AM",
            end_time="09:45 AM",
            activity="Commute",
            location="Car"
        )
        assert block.start_time == "09:00 AM"
        assert block.end_time == "09:45 AM"
        assert block.activity == "Commute"
        assert block.location == "Car"
        assert len(block.participants) == 0
        assert len(block.action_items) == 0


class TestSynchronizedContext:
    """Test SynchronizedContext model."""
    
    def test_synchronized_context_creation(self):
        """Test creating a SynchronizedContext instance."""
        context = SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=300.0
        )
        assert context.start_timestamp == 0.0
        assert context.end_timestamp == 300.0
        assert context.duration == 300.0
        assert len(context.audio_segments) == 0
        assert len(context.video_frames) == 0


class TestDailySummary:
    """Test DailySummary model."""
    
    def test_daily_summary_creation(self):
        """Test creating a DailySummary instance."""
        summary = DailySummary(
            date="2026-01-09",
            video_source="/path/to/video.mp4"
        )
        assert summary.date == "2026-01-09"
        assert summary.video_source == "/path/to/video.mp4"
        assert len(summary.time_blocks) == 0
    
    def test_daily_summary_to_markdown(self):
        """Test converting DailySummary to Markdown."""
        summary = DailySummary(
            date="2026-01-09",
            video_source="/path/to/video.mp4"
        )
        
        block = TimeBlock(
            start_time="09:00 AM",
            end_time="09:45 AM",
            activity="Commute",
            location="Car"
        )
        summary.time_blocks.append(block)
        
        markdown = summary.to_markdown()
        assert "# Daily Summary: 2026-01-09" in markdown
        assert "## 09:00 AM - 09:45 AM: Commute" in markdown
        assert "**Location:** Car" in markdown
    
    def test_daily_summary_json_serializable(self):
        """Test that DailySummary is JSON serializable."""
        summary = DailySummary(
            date="2026-01-09",
            video_source="/path/to/video.mp4",
            created_at=datetime(2026, 1, 9, 12, 0, 0)
        )
        # Should not raise an error
        json_str = summary.model_dump_json()
        assert "2026-01-09" in json_str
