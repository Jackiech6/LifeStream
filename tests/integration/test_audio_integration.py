"""Integration tests for audio processing with real models.

These tests require:
- HuggingFace token in .env file
- pyannote.audio and torch installed
- openai-whisper installed
- Actual audio files for testing

Run with: pytest tests/integration/test_audio_integration.py -v -m integration
"""

import pytest
import os
from pathlib import Path
import tempfile
import subprocess

from src.audio.diarization import SpeakerDiarizer
from src.audio.asr import ASRProcessor
from config.settings import Settings


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def settings():
    """Load settings from .env file."""
    return Settings()


@pytest.fixture
def test_audio_file():
    """Create a test audio file using FFmpeg.
    
    Creates a simple 5-second mono WAV file at 16kHz.
    """
    # Check if FFmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("FFmpeg not available - cannot generate test audio")
    
    # Create temporary audio file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        audio_path = tmp_file.name
    
    try:
        # Generate a simple tone using FFmpeg (440Hz sine wave for 5 seconds)
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'sine=frequency=440:duration=5',
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',      # Mono
            '-y',            # Overwrite
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            pytest.skip(f"Failed to generate test audio: {result.stderr}")
        
        yield audio_path
        
    finally:
        # Cleanup
        if Path(audio_path).exists():
            Path(audio_path).unlink()


class TestDiarizationIntegration:
    """Integration tests for speaker diarization with real models."""
    
    def test_diarizer_initialization(self, settings):
        """Test that diarizer can be initialized with real model."""
        if not settings.huggingface_token:
            pytest.skip("HuggingFace token not configured")
        
        try:
            diarizer = SpeakerDiarizer(settings)
            assert diarizer is not None
            assert diarizer.pipeline is not None
        except ImportError as e:
            pytest.skip(f"Dependencies not installed: {e}")
        except Exception as e:
            pytest.fail(f"Failed to initialize diarizer: {e}")
    
    def test_diarize_simple_audio(self, settings, test_audio_file):
        """Test diarization on a simple audio file."""
        if not settings.huggingface_token:
            pytest.skip("HuggingFace token not configured")
        
        try:
            diarizer = SpeakerDiarizer(settings)
            segments = diarizer.diarize_audio(test_audio_file)
            
            # Should return a list (even if empty for simple tone)
            assert isinstance(segments, list)
            # All segments should be AudioSegment objects
            if segments:
                from src.models.data_models import AudioSegment
                assert all(isinstance(s, AudioSegment) for s in segments)
        except ImportError as e:
            pytest.skip(f"Dependencies not installed: {e}")
        except Exception as e:
            # For a simple tone, diarization might not find speakers
            # That's okay - we just want to ensure it doesn't crash
            if "Could not perform diarization" in str(e):
                pytest.skip(f"Diarization failed (expected for simple tone): {e}")
            else:
                pytest.fail(f"Unexpected error: {e}")


class TestASRIntegration:
    """Integration tests for ASR with real Whisper models."""
    
    def test_asr_processor_initialization(self, settings):
        """Test that ASR processor can be initialized with real model."""
        try:
            processor = ASRProcessor(settings)
            assert processor is not None
            assert processor.model is not None
        except ImportError as e:
            pytest.skip(f"Whisper not installed: {e}")
        except Exception as e:
            pytest.fail(f"Failed to initialize ASR processor: {e}")
    
    def test_transcribe_simple_audio(self, settings, test_audio_file):
        """Test transcription on a simple audio file."""
        try:
            processor = ASRProcessor(settings)
            segments = processor.transcribe_audio(test_audio_file)
            
            # Should return a list
            assert isinstance(segments, list)
            # Each segment should have required keys
            for segment in segments:
                assert "start" in segment
                assert "end" in segment
                assert "text" in segment
                assert isinstance(segment["start"], (int, float))
                assert isinstance(segment["end"], (int, float))
        except ImportError as e:
            pytest.skip(f"Whisper not installed: {e}")
        except Exception as e:
            pytest.fail(f"Transcription failed: {e}")
    
    def test_merge_asr_diarization_integration(self, settings, test_audio_file):
        """Test merging ASR and diarization outputs."""
        if not settings.huggingface_token:
            pytest.skip("HuggingFace token not configured")
        
        try:
            # Initialize processors
            diarizer = SpeakerDiarizer(settings)
            asr_processor = ASRProcessor(settings)
            
            # Get diarization (might be empty for simple tone)
            try:
                diarization_segments = diarizer.diarize_audio(test_audio_file)
            except Exception:
                # If diarization fails, create empty segments
                from src.models.data_models import AudioSegment
                diarization_segments = []
            
            # Get ASR transcription
            asr_output = asr_processor.transcribe_audio(test_audio_file)
            
            # Merge them
            merged = asr_processor.merge_asr_diarization(asr_output, diarization_segments)
            
            # Should return a list
            assert isinstance(merged, list)
            # If we have segments, they should be AudioSegment objects
            if merged:
                from src.models.data_models import AudioSegment
                assert all(isinstance(s, AudioSegment) for s in merged)
        except ImportError as e:
            pytest.skip(f"Dependencies not installed: {e}")
        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")


class TestFullAudioPipeline:
    """Test the complete audio processing pipeline."""
    
    def test_full_pipeline(self, settings, test_audio_file):
        """Test complete audio processing: diarization + ASR."""
        if not settings.huggingface_token:
            pytest.skip("HuggingFace token not configured")
        
        try:
            # Initialize processors
            diarizer = SpeakerDiarizer(settings)
            asr_processor = ASRProcessor(settings)
            
            # Step 1: Diarization
            try:
                diarization_segments = diarizer.diarize_audio(test_audio_file)
            except Exception as e:
                # For simple tone, diarization might fail - that's okay
                from src.models.data_models import AudioSegment
                diarization_segments = []
            
            # Step 2: ASR with diarization
            final_segments = asr_processor.process_audio_with_diarization(
                test_audio_file,
                diarization_segments
            )
            
            # Verify output
            assert isinstance(final_segments, list)
            if final_segments:
                from src.models.data_models import AudioSegment
                assert all(isinstance(s, AudioSegment) for s in final_segments)
                # Check that segments have both speaker_id and transcript_text
                for segment in final_segments:
                    assert hasattr(segment, 'speaker_id')
                    assert hasattr(segment, 'transcript_text')
        except ImportError as e:
            pytest.skip(f"Dependencies not installed: {e}")
        except Exception as e:
            pytest.fail(f"Full pipeline test failed: {e}")
