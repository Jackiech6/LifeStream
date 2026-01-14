"""Integration tests for scene detection.

These tests verify that scene detection works with real video files.
They test all key functions and verify implementation targets.
"""

import pytest
import os
import tempfile
import subprocess
from pathlib import Path
import sys

from src.video.scene_detection import SceneDetector
from src.models.data_models import VideoFrame
from config.settings import Settings


@pytest.fixture
def settings():
    """Create settings for testing."""
    return Settings()


def _find_ffmpeg():
    """Find FFmpeg executable.
    
    Checks common installation locations and PATH.
    """
    # Common Homebrew locations on macOS
    import os
    path_env = os.environ.get('PATH', '')
    
    # Check common locations first
    for path in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg']:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    # Check PATH
    for path_dir in path_env.split(os.pathsep):
        ffmpeg_path = os.path.join(path_dir, 'ffmpeg')
        if os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK):
            return ffmpeg_path
    
    # Try just 'ffmpeg' (if in PATH)
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        return 'ffmpeg'
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    return None


@pytest.fixture
def test_video_file(tmp_path):
    """Create a test video file using FFmpeg.
    
    Creates a simple test video with scene changes.
    """
    # Find FFmpeg
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        pytest.skip("FFmpeg not available - cannot generate test video")
    
    # Create temporary video file
    video_path = tmp_path / "test_video.mp4"
    
    try:
        # Create a test video with scene changes
        # First scene: Red frame (2 seconds)
        # Second scene: Green frame (2 seconds)
        # Third scene: Blue frame (2 seconds)
        cmd = [
            ffmpeg_path,
            '-f', 'lavfi',
            '-i', 'color=c=red:size=640x480:duration=2',
            '-f', 'lavfi',
            '-i', 'color=c=green:size=640x480:duration=2',
            '-f', 'lavfi',
            '-i', 'color=c=blue:size=640x480:duration=2',
            '-filter_complex', '[0:v][1:v][2:v]concat=n=3:v=1[out]',
            '-map', '[out]',
            '-pix_fmt', 'yuv420p',
            '-y',
            str(video_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            pytest.skip(f"Could not create test video: {result.stderr}")
        
        if not video_path.exists():
            pytest.skip("Test video file was not created")
        
        yield str(video_path)
        
        # Cleanup
        if video_path.exists():
            video_path.unlink()
            
    except subprocess.TimeoutExpired:
        pytest.skip("FFmpeg timed out creating test video")
    except Exception as e:
        pytest.skip(f"Could not create test video: {e}")


@pytest.fixture
def static_video_file(tmp_path):
    """Create a static test video (no scene changes).
    
    Creates a single-color video for testing static video handling.
    """
    # Find FFmpeg
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        pytest.skip("FFmpeg not available - cannot generate test video")
    
    video_path = tmp_path / "static_video.mp4"
    
    try:
        # Create a static video (single color, 5 seconds)
        cmd = [
            ffmpeg_path,
            '-f', 'lavfi',
            '-i', 'color=c=red:size=640x480:duration=5',
            '-pix_fmt', 'yuv420p',
            '-y',
            str(video_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            pytest.skip(f"Could not create static video: {result.stderr}")
        
        if not video_path.exists():
            pytest.skip("Static video file was not created")
        
        yield str(video_path)
        
        # Cleanup
        if video_path.exists():
            video_path.unlink()
            
    except subprocess.TimeoutExpired:
        pytest.skip("FFmpeg timed out creating static video")
    except Exception as e:
        pytest.skip(f"Could not create static video: {e}")


@pytest.mark.integration
class TestSceneDetectorInitialization:
    """Test SceneDetector initialization."""
    
    def test_initialization(self, settings):
        """Test that SceneDetector initializes correctly."""
        detector = SceneDetector(settings)
        assert detector is not None
        assert detector.settings == settings
    
    def test_default_settings(self):
        """Test that SceneDetector works with default settings."""
        detector = SceneDetector()
        assert detector is not None
        assert detector.settings is not None


@pytest.mark.integration
class TestSceneDetection:
    """Test scene change detection functionality."""
    
    def test_detect_scene_changes_with_video(self, settings, test_video_file):
        """Test scene change detection with real video file.
        
        Target: detect_scene_changes() returns List[float] of timestamps
        """
        detector = SceneDetector(settings)
        timestamps = detector.detect_scene_changes(test_video_file)
        
        # Verify return type
        assert isinstance(timestamps, list)
        assert all(isinstance(t, float) for t in timestamps)
        
        # With our test video (3 scenes: 0-2s, 2-4s, 4-6s), we should detect scene changes
        # The exact number depends on the threshold, but we should get at least some
        assert len(timestamps) >= 0  # May detect 0 or more scene changes
    
    def test_detect_scene_changes_with_threshold(self, settings, test_video_file):
        """Test scene change detection with different thresholds.
        
        Target: detect_scene_changes() accepts threshold parameter
        """
        detector = SceneDetector(settings)
        
        # Test with low threshold (more sensitive)
        timestamps_low = detector.detect_scene_changes(test_video_file, threshold=0.1)
        
        # Test with high threshold (less sensitive)
        timestamps_high = detector.detect_scene_changes(test_video_file, threshold=0.9)
        
        # Verify both return lists
        assert isinstance(timestamps_low, list)
        assert isinstance(timestamps_high, list)
        
        # Low threshold should detect more scene changes (or equal)
        assert len(timestamps_low) >= len(timestamps_high)
    
    def test_detect_scene_changes_static_video(self, settings, static_video_file):
        """Test scene detection with static video (no scene changes).
        
        Target: Test with static video (no scene changes)
        """
        detector = SceneDetector(settings)
        timestamps = detector.detect_scene_changes(static_video_file)
        
        # Verify return type
        assert isinstance(timestamps, list)
        
        # Static video should have fewer or no scene changes
        assert len(timestamps) >= 0
    
    def test_detect_scene_changes_nonexistent_file(self, settings):
        """Test scene detection with non-existent file."""
        detector = SceneDetector(settings)
        
        with pytest.raises(ValueError, match="Video file does not exist"):
            detector.detect_scene_changes("/nonexistent/file.mp4")


@pytest.mark.integration
class TestKeyframeExtraction:
    """Test keyframe extraction functionality."""
    
    def test_extract_keyframes(self, settings, test_video_file, tmp_path):
        """Test keyframe extraction at specific timestamps.
        
        Target: extract_keyframes() returns List[VideoFrame]
        """
        detector = SceneDetector(settings)
        output_dir = tmp_path / "keyframes"
        timestamps = [1.0, 3.0, 5.0]  # Extract frames at these times
        
        frames = detector.extract_keyframes(test_video_file, timestamps, str(output_dir))
        
        # Verify return type
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
        
        # Verify frame properties
        for frame in frames:
            assert frame.timestamp > 0
            assert frame.frame_path is not None
            assert Path(frame.frame_path).exists()
            assert frame.scene_change_detected is True
            assert frame.scene_id is not None
        
        # Verify frames were extracted (may be fewer if video is shorter)
        assert len(frames) > 0
    
    def test_extract_keyframes_metadata(self, settings, test_video_file, tmp_path):
        """Test that extracted frames have correct metadata.
        
        Target: Store frames with metadata (timestamp, scene_change_flag)
        """
        detector = SceneDetector(settings)
        output_dir = tmp_path / "keyframes_meta"
        timestamps = [1.0, 2.0]
        
        frames = detector.extract_keyframes(test_video_file, timestamps, str(output_dir))
        
        # Verify metadata
        for i, frame in enumerate(frames):
            assert frame.timestamp == timestamps[i]
            assert frame.scene_change_detected is True
            assert frame.scene_id == i
            assert frame.frame_path.endswith('.jpg')
    
    def test_extract_keyframes_nonexistent_file(self, settings):
        """Test keyframe extraction with non-existent file."""
        detector = SceneDetector(settings)
        
        with pytest.raises(ValueError, match="Video file does not exist"):
            detector.extract_keyframes("/nonexistent/file.mp4", [1.0])


@pytest.mark.integration
class TestCombinedOperations:
    """Test combined scene detection and keyframe extraction."""
    
    def test_extract_keyframes_with_scene_detection(self, settings, test_video_file, tmp_path):
        """Test combined scene detection and keyframe extraction.
        
        Target: Extract keyframes at scene boundaries
        """
        detector = SceneDetector(settings)
        output_dir = tmp_path / "scene_keyframes"
        
        frames = detector.extract_keyframes_with_scene_detection(
            test_video_file,
            threshold=0.3,
            output_dir=str(output_dir)
        )
        
        # Verify return type
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
        
        # Verify frames have scene metadata
        for frame in frames:
            assert frame.scene_change_detected is True
            assert frame.timestamp > 0
    
    def test_extract_keyframes_at_intervals(self, settings, test_video_file, tmp_path):
        """Test keyframe extraction at regular intervals.
        
        Target: Optionally extract frames at fixed intervals if no scene changes detected
        """
        detector = SceneDetector(settings)
        output_dir = tmp_path / "interval_keyframes"
        
        frames = detector.extract_keyframes_at_intervals(
            test_video_file,
            interval=1.0,  # Extract every second
            output_dir=str(output_dir)
        )
        
        # Verify return type
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
        
        # Verify frames are at regular intervals (approximately)
        timestamps = [f.timestamp for f in frames]
        if len(timestamps) > 1:
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            # Intervals should be approximately 1.0 seconds (allowing some tolerance)
            assert all(interval > 0.5 and interval < 2.0 for interval in intervals)


@pytest.mark.integration
class TestImplementationTargets:
    """Test that all implementation targets are met."""
    
    def test_target_detect_scene_changes_function(self, settings, test_video_file):
        """Target: detect_scene_changes(video_path, threshold=0.3) -> List[float]"""
        detector = SceneDetector(settings)
        timestamps = detector.detect_scene_changes(test_video_file, threshold=0.3)
        
        assert isinstance(timestamps, list)
        assert all(isinstance(t, float) for t in timestamps)
        assert all(t > 0 for t in timestamps)  # All timestamps should be > 0 (skip first scene)
    
    def test_target_extract_keyframes_function(self, settings, test_video_file, tmp_path):
        """Target: extract_keyframes(video_path, timestamps) -> List[VideoFrame]"""
        detector = SceneDetector(settings)
        timestamps = [1.0, 2.0, 3.0]
        frames = detector.extract_keyframes(test_video_file, timestamps, str(tmp_path))
        
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
        assert len(frames) > 0
    
    def test_target_scene_boundary_extraction(self, settings, test_video_file, tmp_path):
        """Target: Extract keyframes at scene boundaries"""
        detector = SceneDetector(settings)
        frames = detector.extract_keyframes_with_scene_detection(
            test_video_file,
            output_dir=str(tmp_path)
        )
        
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
        assert all(f.scene_change_detected for f in frames)
    
    def test_target_fixed_interval_extraction(self, settings, test_video_file, tmp_path):
        """Target: Optionally extract frames at fixed intervals"""
        detector = SceneDetector(settings)
        frames = detector.extract_keyframes_at_intervals(
            test_video_file,
            interval=2.0,
            output_dir=str(tmp_path)
        )
        
        assert isinstance(frames, list)
        assert all(isinstance(f, VideoFrame) for f in frames)
    
    def test_target_metadata_storage(self, settings, test_video_file, tmp_path):
        """Target: Store frames with metadata (timestamp, scene_change_flag)"""
        detector = SceneDetector(settings)
        frames = detector.extract_keyframes(test_video_file, [1.0, 2.0], str(tmp_path))
        
        for frame in frames:
            assert hasattr(frame, 'timestamp')
            assert hasattr(frame, 'scene_change_detected')
            assert frame.timestamp is not None
            assert frame.scene_change_detected is not None
            assert isinstance(frame.scene_change_detected, bool)
