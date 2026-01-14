"""Scene detection and visual sampling module.

This module handles intelligent visual sampling by detecting scene changes
in video files and extracting keyframes at scene boundaries.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
import subprocess

from src.models.data_models import VideoFrame, VideoMetadata
from config.settings import Settings

logger = logging.getLogger(__name__)


class SceneDetector:
    """Handles scene change detection in video files."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize SceneDetector.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._check_dependencies()
    
    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        try:
            from scenedetect import VideoManager, SceneManager
            from scenedetect.detectors import ContentDetector
            import cv2
            logger.info("Scene detection dependencies available")
        except ImportError as e:
            raise ImportError(
                f"Required dependencies not installed: {e}. "
                "Install with: pip install scenedetect opencv-python"
            )
    
    def detect_scene_changes(
        self,
        video_path: str,
        threshold: Optional[float] = None
    ) -> List[float]:
        """Detect scene changes in video file.
        
        Uses PySceneDetect to identify scene boundaries based on visual changes.
        
        Args:
            video_path: Path to the video file.
            threshold: Scene detection threshold (0.0-1.0). If None, uses settings default.
            
        Returns:
            List of timestamps (in seconds) where scene changes occur.
            
        Raises:
            ValueError: If video file cannot be processed.
        """
        if not Path(video_path).exists():
            raise ValueError(f"Video file does not exist: {video_path}")
        
        if threshold is None:
            threshold = self.settings.scene_detection_threshold
        
        try:
            from scenedetect import VideoManager, SceneManager
            from scenedetect.detectors import ContentDetector
            
            logger.info(f"Detecting scene changes in: {video_path} (threshold={threshold})")
            
            # Create video manager and scene manager
            video_manager = VideoManager([video_path])
            scene_manager = SceneManager()
            
            # Add content detector (detects changes in video content)
            scene_manager.add_detector(ContentDetector(threshold=threshold))
            
            # Start video manager
            video_manager.set_duration()
            video_manager.start()
            
            # Detect scenes
            scene_manager.detect_scenes(frame_source=video_manager)
            
            # Get scene list
            scene_list = scene_manager.get_scene_list()
            
            # Extract timestamps (start times of each scene, skip first scene at 0.0)
            timestamps = []
            for start_time, end_time in scene_list:
                # Convert from Timecode to seconds
                start_seconds = start_time.get_seconds()
                if start_seconds > 0:  # Skip first scene start at 0.0
                    timestamps.append(start_seconds)
            
            logger.info(f"Detected {len(timestamps)} scene changes")
            
            return sorted(timestamps)
            
        except Exception as e:
            logger.error(f"Scene detection failed: {e}")
            raise ValueError(f"Could not detect scene changes: {video_path}") from e
        finally:
            # Cleanup
            if 'video_manager' in locals():
                video_manager.release()
    
    def extract_keyframes(
        self,
        video_path: str,
        timestamps: List[float],
        output_dir: Optional[str] = None
    ) -> List[VideoFrame]:
        """Extract keyframes at specified timestamps.
        
        Args:
            video_path: Path to the video file.
            timestamps: List of timestamps (in seconds) to extract frames.
            output_dir: Optional output directory for frames. If None, uses temp directory.
            
        Returns:
            List of VideoFrame objects with scene_change_detected flag set.
            
        Raises:
            ValueError: If video file cannot be processed.
        """
        if not Path(video_path).exists():
            raise ValueError(f"Video file does not exist: {video_path}")
        
        if output_dir is None:
            video_name = Path(video_path).stem
            output_dir = Path(self.settings.temp_dir) / f"{video_name}_keyframes"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            import cv2
            
            logger.info(f"Extracting {len(timestamps)} keyframes to: {output_dir}")
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video file: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = []
            scene_id = 0
            
            for i, timestamp in enumerate(timestamps):
                # Calculate frame number
                frame_number = int(timestamp * fps)
                
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Could not read frame at {timestamp:.3f}s")
                    continue
                
                # Save frame
                frame_filename = f"keyframe_{i:06d}_{timestamp:.3f}s.jpg"
                frame_path = output_dir / frame_filename
                
                # Write frame
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                if frame_path.exists():
                    video_frame = VideoFrame(
                        timestamp=timestamp,
                        frame_path=str(frame_path.absolute()),
                        scene_change_detected=True,
                        scene_id=scene_id
                    )
                    frames.append(video_frame)
                    scene_id += 1
                    logger.debug(f"Extracted keyframe at {timestamp:.3f}s")
            
            cap.release()
            
            logger.info(f"Extracted {len(frames)} keyframes successfully")
            return frames
            
        except Exception as e:
            logger.error(f"Keyframe extraction failed: {e}")
            raise ValueError(f"Could not extract keyframes: {video_path}") from e
    
    def extract_keyframes_with_scene_detection(
        self,
        video_path: str,
        threshold: Optional[float] = None,
        output_dir: Optional[str] = None
    ) -> List[VideoFrame]:
        """Detect scenes and extract keyframes at scene boundaries.
        
        This is a convenience method that combines scene detection and keyframe extraction.
        
        Args:
            video_path: Path to the video file.
            threshold: Scene detection threshold. If None, uses settings default.
            output_dir: Optional output directory for frames.
            
        Returns:
            List of VideoFrame objects extracted at scene boundaries.
        """
        # Detect scene changes
        timestamps = self.detect_scene_changes(video_path, threshold)
        
        # Extract keyframes at scene boundaries
        frames = self.extract_keyframes(video_path, timestamps, output_dir)
        
        return frames
    
    def extract_keyframes_at_intervals(
        self,
        video_path: str,
        interval: float = 5.0,
        output_dir: Optional[str] = None
    ) -> List[VideoFrame]:
        """Extract keyframes at regular intervals.
        
        Fallback method when scene detection doesn't find many scene changes.
        
        Args:
            video_path: Path to the video file.
            interval: Interval in seconds between keyframes.
            output_dir: Optional output directory for frames.
            
        Returns:
            List of VideoFrame objects.
        """
        try:
            import cv2
            
            # Get video duration
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video file: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            # Generate timestamps at intervals
            timestamps = [i * interval for i in range(int(duration / interval) + 1)]
            timestamps = [t for t in timestamps if t < duration]
            
            # Extract frames
            return self.extract_keyframes(video_path, timestamps, output_dir)
            
        except Exception as e:
            logger.error(f"Interval keyframe extraction failed: {e}")
            raise ValueError(f"Could not extract keyframes at intervals: {video_path}") from e
