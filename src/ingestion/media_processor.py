"""Media ingestion and track splitting module.

This module handles video file ingestion, format validation, and extraction
of audio and video tracks for parallel processing.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import logging

from src.models.data_models import VideoMetadata, VideoFrame
from config.settings import Settings

logger = logging.getLogger(__name__)


class MediaProcessor:
    """Handles media file ingestion and track splitting."""
    
    # Supported video formats
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.m4v', '.flv', '.wmv', '.webm'}
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize MediaProcessor.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("FFmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "FFmpeg is not installed or not in PATH. "
                "Please install FFmpeg: brew install ffmpeg"
            )
    
    def validate_video_format(self, file_path: str) -> bool:
        """Validate if the video file format is supported.
        
        Args:
            file_path: Path to the video file.
            
        Returns:
            True if format is supported, False otherwise.
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            logger.error(f"File does not exist: {file_path}")
            return False
        
        extension = file_path_obj.suffix.lower()
        is_supported = extension in self.SUPPORTED_FORMATS
        
        if not is_supported:
            logger.warning(f"Unsupported format: {extension}. Supported: {self.SUPPORTED_FORMATS}")
        
        return is_supported
    
    def get_video_metadata(self, video_path: str) -> VideoMetadata:
        """Extract metadata from video file.
        
        Args:
            video_path: Path to the video file.
            
        Returns:
            VideoMetadata object with video information.
            
        Raises:
            ValueError: If video file cannot be processed.
        """
        if not self.validate_video_format(video_path):
            raise ValueError(f"Unsupported video format: {video_path}")
        
        try:
            # Use ffprobe to get video metadata
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
                '-show_entries', 'format=duration,size,format_name',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            import json
            probe_data = json.loads(result.stdout)
            
            # Extract video stream info
            video_stream = probe_data.get('streams', [{}])[0]
            format_info = probe_data.get('format', {})
            
            # Parse frame rate (e.g., "30/1" -> 30.0)
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = map(float, fps_str.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(fps_str)
            
            # Get resolution
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            
            # Get duration
            duration = float(format_info.get('duration', 0))
            
            # Get file size
            file_size = int(format_info.get('size', 0))
            
            # Get codecs
            video_codec = video_stream.get('codec_name', 'unknown')
            
            # Get audio codec
            audio_cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'json',
                video_path
            ]
            
            audio_codec = None
            try:
                audio_result = subprocess.run(
                    audio_cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                audio_data = json.loads(audio_result.stdout)
                audio_streams = audio_data.get('streams', [])
                if audio_streams:
                    audio_codec = audio_streams[0].get('codec_name')
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                logger.warning("Could not extract audio codec")
            
            # Get file format
            file_format = Path(video_path).suffix.lower().lstrip('.')
            
            metadata = VideoMetadata(
                file_path=str(Path(video_path).absolute()),
                duration=duration,
                fps=fps,
                resolution=(width, height),
                format=file_format,
                file_size=file_size,
                codec=video_codec,
                audio_codec=audio_codec
            )
            
            logger.info(f"Extracted metadata: {duration:.2f}s, {width}x{height}, {fps:.2f}fps")
            return metadata
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe error: {e.stderr}")
            raise ValueError(f"Could not extract metadata from video: {video_path}") from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error parsing video metadata: {e}")
            raise ValueError(f"Could not parse video metadata: {video_path}") from e
    
    def extract_audio_track(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """Extract audio track from video file.
        
        Args:
            video_path: Path to the video file.
            output_path: Optional output path for audio file. If None, uses temp directory.
            
        Returns:
            Path to the extracted audio file (WAV format, 16kHz mono).
            
        Raises:
            ValueError: If video file cannot be processed.
        """
        if not self.validate_video_format(video_path):
            raise ValueError(f"Unsupported video format: {video_path}")
        
        if output_path is None:
            video_name = Path(video_path).stem
            output_path = os.path.join(
                self.settings.temp_dir,
                f"{video_name}_audio.wav"
            )
        
        output_path = str(Path(output_path).absolute())
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract audio as WAV, 16kHz mono (optimal for diarization)
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
                '-ar', '16000',  # Sample rate: 16kHz
                '-ac', '1',  # Mono channel
                '-y',  # Overwrite output file
                output_path
            ]
            
            logger.info(f"Extracting audio track to: {output_path}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            
            if not Path(output_path).exists():
                raise RuntimeError(f"Audio extraction failed: output file not created")
            
            file_size = Path(output_path).stat().st_size
            logger.info(f"Audio extracted successfully: {file_size / 1024 / 1024:.2f} MB")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            logger.error("Audio extraction timed out")
            raise RuntimeError("Audio extraction timed out (>5 minutes)") from None
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise ValueError(f"Could not extract audio from video: {video_path}") from e
    
    def extract_video_frames(
        self,
        video_path: str,
        output_dir: Optional[str] = None,
        timestamps: Optional[List[float]] = None
    ) -> List[VideoFrame]:
        """Extract video frames at specified timestamps.
        
        Args:
            video_path: Path to the video file.
            output_dir: Optional output directory for frames. If None, uses temp directory.
            timestamps: List of timestamps (in seconds) to extract frames. 
                       If None, extracts frames at regular intervals.
            
        Returns:
            List of VideoFrame objects.
            
        Raises:
            ValueError: If video file cannot be processed.
        """
        if not self.validate_video_format(video_path):
            raise ValueError(f"Unsupported video format: {video_path}")
        
        if output_dir is None:
            video_name = Path(video_path).stem
            output_dir = os.path.join(self.settings.temp_dir, f"{video_name}_frames")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get video metadata to determine frame extraction strategy
        metadata = self.get_video_metadata(video_path)
        
        # If no timestamps provided, extract frames at regular intervals (every 5 seconds)
        if timestamps is None:
            interval = 5.0  # Extract frame every 5 seconds
            timestamps = [i * interval for i in range(int(metadata.duration / interval))]
        
        frames = []
        
        try:
            for i, timestamp in enumerate(timestamps):
                if timestamp > metadata.duration:
                    logger.warning(f"Timestamp {timestamp}s exceeds video duration {metadata.duration}s")
                    continue
                
                # Format timestamp for FFmpeg (HH:MM:SS.mmm)
                hours = int(timestamp // 3600)
                minutes = int((timestamp % 3600) // 60)
                seconds = timestamp % 60
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
                
                # Output frame filename
                frame_filename = f"frame_{i:06d}_{timestamp:.3f}s.jpg"
                frame_path = output_dir / frame_filename
                
                # Extract single frame
                cmd = [
                    'ffmpeg',
                    '-ss', time_str,  # Seek to timestamp
                    '-i', video_path,
                    '-vframes', '1',  # Extract only 1 frame
                    '-q:v', '2',  # High quality JPEG
                    '-y',  # Overwrite
                    str(frame_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30  # 30 second timeout per frame
                )
                
                if frame_path.exists():
                    frame = VideoFrame(
                        timestamp=timestamp,
                        frame_path=str(frame_path.absolute()),
                        scene_change_detected=False  # Will be set by scene detection
                    )
                    frames.append(frame)
                    logger.debug(f"Extracted frame at {timestamp:.3f}s: {frame_path.name}")
                else:
                    logger.warning(f"Frame extraction failed at {timestamp:.3f}s")
            
            logger.info(f"Extracted {len(frames)} frames to {output_dir}")
            return frames
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error extracting frames: {e.stderr}")
            raise ValueError(f"Could not extract frames from video: {video_path}") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting frames: {e}")
            raise
    
    def split_media_tracks(
        self,
        video_path: str,
        audio_output: Optional[str] = None,
        frames_output_dir: Optional[str] = None
    ) -> Tuple[str, List[VideoFrame], VideoMetadata]:
        """Split video into audio track and video frames.
        
        This is a convenience method that extracts both audio and frames.
        
        Args:
            video_path: Path to the video file.
            audio_output: Optional output path for audio file.
            frames_output_dir: Optional output directory for frames.
            
        Returns:
            Tuple of (audio_path, video_frames, video_metadata).
        """
        logger.info(f"Processing video: {video_path}")
        
        # Get metadata
        metadata = self.get_video_metadata(video_path)
        
        # Extract audio
        audio_path = self.extract_audio_track(video_path, audio_output)
        
        # Extract frames (at regular intervals for now, scene detection will refine this)
        frames = self.extract_video_frames(video_path, frames_output_dir)
        
        logger.info(f"Media splitting complete: audio={audio_path}, frames={len(frames)}")
        
        return audio_path, frames, metadata
