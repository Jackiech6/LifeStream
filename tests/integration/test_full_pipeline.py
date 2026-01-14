"""Integration test for the full pipeline.

This test verifies that all phases work together correctly.
"""

import pytest
from pathlib import Path
import tempfile
import subprocess
from datetime import datetime

from src.models.data_models import AudioSegment, VideoFrame, SynchronizedContext
from src.processing.synchronization import ContextSynchronizer
from src.processing.summarization import LLMSummarizer
from config.settings import Settings


@pytest.mark.integration
class TestFullPipeline:
    """Test the complete pipeline integration."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def synchronizer(self, settings):
        """Create ContextSynchronizer."""
        return ContextSynchronizer(settings)
    
    @pytest.fixture
    def summarizer(self, settings):
        """Create LLMSummarizer."""
        if not settings.openai_api_key:
            pytest.skip("OpenAI API key not configured")
        return LLMSummarizer(settings)
    
    def test_synchronization_basic(self, synchronizer):
        """Test basic synchronization functionality."""
        # Create sample audio segments
        audio_segments = [
            AudioSegment(
                start_time=0.0,
                end_time=10.0,
                speaker_id="Speaker_01",
                transcript_text="Hello, this is a test."
            ),
            AudioSegment(
                start_time=10.0,
                end_time=20.0,
                speaker_id="Speaker_02",
                transcript_text="How are you doing?"
            ),
        ]
        
        # Create sample video frames
        video_frames = [
            VideoFrame(timestamp=5.0, frame_path="/tmp/frame1.jpg"),
            VideoFrame(timestamp=15.0, frame_path="/tmp/frame2.jpg"),
        ]
        
        # Synchronize
        contexts = synchronizer.synchronize_contexts(
            audio_segments,
            video_frames,
            chunk_size=15.0
        )
        
        # Verify
        assert len(contexts) > 0
        assert all(isinstance(ctx, SynchronizedContext) for ctx in contexts)
        
        # Check that contexts have data
        assert any(len(ctx.audio_segments) > 0 for ctx in contexts)
        assert any(len(ctx.video_frames) > 0 for ctx in contexts)
    
    def test_summarizer_initialization(self, summarizer):
        """Test that summarizer is properly initialized."""
        assert summarizer is not None
        assert summarizer.client is not None
        assert summarizer.model is not None
    
    def test_format_markdown(self, summarizer):
        """Test Markdown formatting."""
        from src.models.data_models import DailySummary, TimeBlock, Participant
        
        time_block = TimeBlock(
            start_time="00:00",
            end_time="00:10",
            activity="Test Activity",
            participants=[Participant(speaker_id="Speaker_01")],
            transcript_summary="Test summary",
            action_items=["Test action item"]
        )
        
        daily_summary = DailySummary(
            date="2026-01-09",
            time_blocks=[time_block],
            total_duration=600.0
        )
        
        markdown = summarizer.format_markdown_output(daily_summary)
        
        assert isinstance(markdown, str)
        assert "Daily Summary" in markdown
        assert "Test Activity" in markdown
        assert "Speaker_01" in markdown
    
    def test_synchronization_edge_cases(self, synchronizer):
        """Test synchronization edge cases."""
        # Test with empty inputs
        contexts = synchronizer.synchronize_contexts([], [])
        assert isinstance(contexts, list)
        assert len(contexts) == 0  # Empty inputs should return empty list
        
        # Test with audio only
        audio_segments = [
            AudioSegment(start_time=0.0, end_time=10.0, speaker_id="Speaker_01")
        ]
        contexts = synchronizer.synchronize_contexts(audio_segments, [], chunk_size=5.0)
        assert len(contexts) > 0
        assert all(len(ctx.audio_segments) > 0 for ctx in contexts)
        
        # Test with video only (multiple frames to avoid boundary issues)
        video_frames = [
            VideoFrame(timestamp=1.0, frame_path="/tmp/frame1.jpg"),
            VideoFrame(timestamp=3.0, frame_path="/tmp/frame2.jpg"),
        ]
        contexts = synchronizer.synchronize_contexts([], video_frames, chunk_size=5.0)
        assert len(contexts) > 0
        assert all(len(ctx.video_frames) > 0 for ctx in contexts)
    
    def test_summarizer_helper_functions(self, summarizer):
        """Test summarizer helper functions."""
        # Create a context
        context = SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=10.0,
            audio_segments=[
                AudioSegment(
                    start_time=0.0,
                    end_time=10.0,
                    speaker_id="Speaker_01",
                    transcript_text="Test transcript"
                )
            ],
            video_frames=[
                VideoFrame(timestamp=5.0, frame_path="/tmp/frame1.jpg")
            ]
        )
        
        # Test prompt creation
        prompt = summarizer._create_prompt(context)
        assert isinstance(prompt, str)
        assert "Audio Transcript" in prompt
        
        # Test visual context
        visual_context = summarizer._get_visual_context(context)
        assert isinstance(visual_context, str)
        
        # Test default timeblock creation
        timeblock = summarizer._create_default_timeblock(context)
        assert timeblock is not None
        assert timeblock.start_time is not None
        assert timeblock.end_time is not None
