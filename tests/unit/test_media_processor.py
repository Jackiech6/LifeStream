"""Unit tests for media processor."""

import pytest
import tempfile
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from src.ingestion.media_processor import MediaProcessor, _is_url
from src.models.data_models import VideoMetadata, VideoFrame
from config.settings import Settings


class TestMediaProcessor:
    """Test MediaProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a MediaProcessor instance."""
        settings = Settings()
        with patch('src.ingestion.media_processor.subprocess.run') as mock_run:
            # Mock FFmpeg version check
            mock_run.return_value = MagicMock(returncode=0)
            return MediaProcessor(settings)
    
    @pytest.fixture
    def mock_video_file(self, tmp_path):
        """Create a mock video file path."""
        video_file = tmp_path / "test_video.mp4"
        video_file.touch()
        return str(video_file)
    
    def test_validate_video_format_supported(self, processor, mock_video_file):
        """Test format validation with supported format."""
        assert processor.validate_video_format(mock_video_file) is True
    
    def test_validate_video_format_unsupported(self, processor, tmp_path):
        """Test format validation with unsupported format."""
        unsupported_file = tmp_path / "test.txt"
        unsupported_file.touch()
        assert processor.validate_video_format(str(unsupported_file)) is False
    
    def test_validate_video_format_nonexistent(self, processor):
        """Test format validation with non-existent file."""
        assert processor.validate_video_format("/nonexistent/file.mp4") is False

    def test_is_url_and_validate_url(self, processor):
        """Test URL detection and that URLs are accepted for streaming pipeline."""
        assert _is_url("https://bucket.s3.region.amazonaws.com/key?X-Amz-") is True
        assert _is_url("http://example.com/v.mp4") is True
        assert _is_url("/local/path/video.mp4") is False
        assert processor.validate_video_format("https://example.com/video.mp4") is True
    
    @patch('src.ingestion.media_processor.subprocess.run')
    def test_get_video_metadata(self, mock_run, processor, mock_video_file):
        """Test video metadata extraction."""
        # Mock ffprobe output
        mock_probe_output = {
            "streams": [{
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "codec_name": "h264"
            }],
            "format": {
                "duration": "3600.5",
                "size": "1000000000",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
            }
        }
        
        # Mock audio codec probe
        mock_audio_output = {
            "streams": [{
                "codec_name": "aac"
            }]
        }
        
        def run_side_effect(*args, **kwargs):
            result = MagicMock()
            if 'a:0' in args[0]:  # Audio probe
                result.stdout = json.dumps(mock_audio_output)
            else:  # Video probe
                result.stdout = json.dumps(mock_probe_output)
            result.returncode = 0
            return result
        
        mock_run.side_effect = run_side_effect
        
        metadata = processor.get_video_metadata(mock_video_file)
        
        assert metadata.duration == 3600.5
        assert metadata.resolution == (1920, 1080)
        assert metadata.fps == 30.0
        assert metadata.format == "mp4"
        assert metadata.codec == "h264"
        assert metadata.audio_codec == "aac"
    
    @patch('src.ingestion.media_processor.subprocess.run')
    def test_extract_audio_track(self, mock_run, processor, mock_video_file, tmp_path):
        """Test audio track extraction."""
        # Mock successful FFmpeg run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Create output file to simulate successful extraction
        output_path = tmp_path / "test_audio.wav"
        output_path.touch()
        
        with patch('src.ingestion.media_processor.Path') as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.stat.return_value.st_size = 1024 * 1024  # 1 MB
            mock_path_instance.absolute.return_value = str(output_path)
            mock_path.return_value = mock_path_instance
            mock_path.side_effect = lambda x: mock_path_instance if str(x) == str(output_path) else Path(x)
            
            audio_path = processor.extract_audio_track(mock_video_file, str(output_path))
            
            assert audio_path is not None
            assert mock_run.called
    
    @patch('src.ingestion.media_processor.subprocess.run')
    def test_extract_video_frames(self, mock_run, processor, mock_video_file, tmp_path):
        """Test video frame extraction."""
        # Mock successful FFmpeg run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock metadata
        metadata = VideoMetadata(
            file_path=mock_video_file,
            duration=100.0,
            fps=30.0,
            resolution=(1920, 1080),
            format="mp4"
        )
        
        # Create actual frame files
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        for i in range(3):
            frame_file = frames_dir / f"frame_{i:06d}_{i*5.0:.3f}s.jpg"
            frame_file.touch()
        
        with patch.object(processor, 'get_video_metadata', return_value=metadata):
            timestamps = [0.0, 5.0, 10.0]
            frames = processor.extract_video_frames(
                mock_video_file,
                str(frames_dir),
                timestamps
            )
            
            assert len(frames) == 3
            assert all(isinstance(frame, VideoFrame) for frame in frames)
            assert frames[0].timestamp == 0.0
            assert frames[1].timestamp == 5.0
            assert frames[2].timestamp == 10.0
    
    @patch('src.ingestion.media_processor.subprocess.run')
    def test_split_media_tracks(self, mock_run, processor, mock_video_file, tmp_path):
        """Test splitting media into audio and video tracks."""
        # Mock successful FFmpeg runs
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock metadata
        metadata = VideoMetadata(
            file_path=mock_video_file,
            duration=100.0,
            fps=30.0,
            resolution=(1920, 1080),
            format="mp4"
        )
        
        with patch.object(processor, 'get_video_metadata', return_value=metadata):
            with patch.object(processor, 'extract_audio_track', return_value=str(tmp_path / "audio.wav")):
                with patch.object(processor, 'extract_video_frames', return_value=[]):
                    audio_path, frames, meta = processor.split_media_tracks(mock_video_file)
                    
                    assert audio_path is not None
                    assert isinstance(frames, list)
                    assert meta == metadata
    
    def test_check_ffmpeg_missing(self):
        """Test error when FFmpeg is not available."""
        with patch('src.ingestion.media_processor.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            with pytest.raises(RuntimeError, match="FFmpeg is not installed"):
                MediaProcessor()
    
    @patch('src.ingestion.media_processor.subprocess.run')
    def test_get_video_metadata_error_handling(self, mock_run, processor, mock_video_file):
        """Test error handling in metadata extraction."""
        # Mock FFprobe failure
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffprobe', stderr="Error")
        
        with pytest.raises(ValueError, match="Could not extract metadata"):
            processor.get_video_metadata(mock_video_file)
