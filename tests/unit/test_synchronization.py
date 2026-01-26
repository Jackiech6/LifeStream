"""Unit tests for synchronization."""

import pytest
from src.processing.synchronization import ContextSynchronizer
from src.models.data_models import AudioSegment, VideoFrame, SynchronizedContext
from config.settings import Settings


class TestContextSynchronizer:
    """Test ContextSynchronizer class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def synchronizer(self, settings):
        """Create ContextSynchronizer instance."""
        return ContextSynchronizer(settings)
    
    @pytest.fixture
    def sample_audio_segments(self):
        """Create sample audio segments."""
        return [
            AudioSegment(start_time=0.0, end_time=5.0, speaker_id="Speaker_01"),
            AudioSegment(start_time=5.0, end_time=10.0, speaker_id="Speaker_02"),
            AudioSegment(start_time=10.0, end_time=15.0, speaker_id="Speaker_01"),
        ]
    
    @pytest.fixture
    def sample_video_frames(self):
        """Create sample video frames."""
        return [
            VideoFrame(timestamp=2.5, frame_path="/tmp/frame1.jpg"),
            VideoFrame(timestamp=7.5, frame_path="/tmp/frame2.jpg"),
            VideoFrame(timestamp=12.5, frame_path="/tmp/frame3.jpg"),
        ]
    
    def test_initialization(self, settings):
        """Test that ContextSynchronizer initializes correctly."""
        synchronizer = ContextSynchronizer(settings)
        assert synchronizer is not None
        assert synchronizer.settings == settings
        assert synchronizer.chunk_size == settings.chunk_size_seconds
    
    def test_synchronize_contexts_basic(self, synchronizer, sample_audio_segments, sample_video_frames):
        """Test basic context synchronization."""
        contexts = synchronizer.synchronize_contexts(
            sample_audio_segments,
            sample_video_frames,
            chunk_size=10.0
        )
        
        assert isinstance(contexts, list)
        assert len(contexts) > 0
        assert all(isinstance(ctx, SynchronizedContext) for ctx in contexts)
    
    def test_synchronize_contexts_empty(self, synchronizer):
        """Test synchronization with empty inputs (no timeline)."""
        with pytest.raises(ValueError, match="No audio, video, or video_duration"):
            synchronizer.synchronize_contexts([], [])
    
    def test_synchronize_contexts_audio_only(self, synchronizer, sample_audio_segments):
        """Test synchronization with audio only."""
        contexts = synchronizer.synchronize_contexts(sample_audio_segments, [], chunk_size=10.0)
        
        assert len(contexts) > 0
        assert all(len(ctx.audio_segments) > 0 for ctx in contexts)
        assert all(len(ctx.video_frames) == 0 for ctx in contexts)
    
    def test_synchronize_contexts_video_only(self, synchronizer, sample_video_frames):
        """Test synchronization with video only."""
        contexts = synchronizer.synchronize_contexts([], sample_video_frames, chunk_size=10.0)
        
        assert len(contexts) > 0
        assert all(len(ctx.video_frames) > 0 for ctx in contexts)
        assert all(len(ctx.audio_segments) == 0 for ctx in contexts)
    
    def test_map_frame_to_segments(self, synchronizer, sample_audio_segments):
        """Test mapping frame timestamp to segments."""
        matching = synchronizer.map_frame_to_segments(2.5, sample_audio_segments)
        assert isinstance(matching, list)
        assert len(matching) > 0
        assert all(isinstance(seg, AudioSegment) for seg in matching)
    
    def test_get_overlapping_segments(self, synchronizer, sample_audio_segments):
        """Test getting overlapping segments."""
        overlapping = synchronizer.get_overlapping_segments(3.0, 8.0, sample_audio_segments)
        assert isinstance(overlapping, list)
        assert len(overlapping) > 0
    
    def test_segment_overlaps_window(self, synchronizer):
        """Test segment overlap detection."""
        segment = AudioSegment(start_time=5.0, end_time=10.0, speaker_id="Speaker_01")
        
        # Overlapping cases
        assert synchronizer._segment_overlaps_window(segment, 3.0, 7.0) is True
        assert synchronizer._segment_overlaps_window(segment, 7.0, 12.0) is True
        assert synchronizer._segment_overlaps_window(segment, 6.0, 8.0) is True
        
        # Non-overlapping cases
        assert synchronizer._segment_overlaps_window(segment, 0.0, 3.0) is False
        assert synchronizer._segment_overlaps_window(segment, 12.0, 15.0) is False
