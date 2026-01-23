"""Temporal context synchronization module.

This module handles synchronization of audio segments and video frames
into time-aligned contexts for summarization.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.models.data_models import AudioSegment, VideoFrame, SynchronizedContext
from config.settings import Settings

logger = logging.getLogger(__name__)


class ContextSynchronizer:
    """Handles synchronization of audio segments and video frames."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize ContextSynchronizer.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self.chunk_size = self.settings.chunk_size_seconds  # Default: 300 seconds (5 minutes)
    
    def synchronize_contexts(
        self,
        audio_segments: List[AudioSegment],
        video_frames: List[VideoFrame],
        chunk_size: Optional[float] = None,
        scene_boundaries: Optional[List[float]] = None
    ) -> List[SynchronizedContext]:
        """Synchronize audio segments and video frames into time-aligned contexts.
        
        This function creates SynchronizedContext objects based on scene boundaries
        (if provided) or fixed time windows. According to project guidelines, summary
        chunks should be based on scene detection boundaries.
        
        Args:
            audio_segments: List of AudioSegment objects with timestamps.
            video_frames: List of VideoFrame objects with timestamps.
            chunk_size: Size of time window in seconds (used only if scene_boundaries is None).
            scene_boundaries: List of scene boundary timestamps in seconds. If provided,
                            contexts are created based on these boundaries instead of fixed chunks.
            
        Returns:
            List of SynchronizedContext objects, one for each scene/time window.
            
        Raises:
            ValueError: If no audio segments or video frames provided.
        """
        if not audio_segments and not video_frames:
            raise ValueError("No audio segments or video frames provided - cannot synchronize contexts")
        
        # Find the overall time range
        all_timestamps = []
        if audio_segments:
            all_timestamps.extend([seg.start_time for seg in audio_segments])
            all_timestamps.extend([seg.end_time for seg in audio_segments])
        if video_frames:
            all_timestamps.extend([frame.timestamp for frame in video_frames])
        
        if not all_timestamps:
            raise ValueError("No timestamps found in audio or video data - cannot synchronize contexts")
        
        start_time = min(all_timestamps)
        end_time = max(all_timestamps)
        
        # Use scene boundaries if provided (project guideline: chunks based on scene detection)
        if scene_boundaries is not None and len(scene_boundaries) > 0:
            logger.info(f"Synchronizing contexts based on {len(scene_boundaries)} scene boundaries: "
                       f"{start_time:.2f}s to {end_time:.2f}s")
            
            # Create boundaries list: [start_time, scene_boundaries..., end_time]
            boundaries = [start_time] + sorted(scene_boundaries) + [end_time]
            # Remove duplicates and ensure sorted
            boundaries = sorted(list(set(boundaries)))
            
            contexts = []
            for i in range(len(boundaries) - 1):
                current_start = boundaries[i]
                current_end = boundaries[i + 1]
                
                # Find audio segments in this scene window
                window_audio_segments = [
                    seg for seg in audio_segments
                    if self._segment_overlaps_window(seg, current_start, current_end)
                ]
                
                # Find video frames in this scene window
                window_video_frames = [
                    frame for frame in video_frames
                    if current_start <= frame.timestamp < current_end
                ]
                
                # Create context for each scene (even if empty, to maintain scene structure)
                context = SynchronizedContext(
                    start_timestamp=current_start,
                    end_timestamp=current_end,
                    audio_segments=window_audio_segments,
                    video_frames=window_video_frames,
                    metadata={
                        "chunk_type": "scene_based",
                        "scene_index": i,
                        "audio_segment_count": len(window_audio_segments),
                        "video_frame_count": len(window_video_frames),
                    }
                )
                contexts.append(context)
                logger.debug(f"Created scene-based context {i+1}: {current_start:.2f}s - {current_end:.2f}s "
                           f"({len(window_audio_segments)} audio segments, "
                           f"{len(window_video_frames)} video frames)")
        else:
            # Fallback to fixed chunk size (should not be used in production per project guidelines)
            if chunk_size is None:
                chunk_size = self.chunk_size
            
            logger.warning(f"No scene boundaries provided - using fixed chunk size {chunk_size}s "
                          f"(not recommended per project guidelines)")
            logger.info(f"Synchronizing contexts: {start_time:.2f}s to {end_time:.2f}s (chunk size: {chunk_size}s)")
            
            # Create time windows
            contexts = []
            current_start = start_time
            
            while current_start < end_time:
                current_end = min(current_start + chunk_size, end_time)
                
                # Find audio segments in this window
                window_audio_segments = [
                    seg for seg in audio_segments
                    if self._segment_overlaps_window(seg, current_start, current_end)
                ]
                
                # Find video frames in this window
                window_video_frames = [
                    frame for frame in video_frames
                    if current_start <= frame.timestamp < current_end
                ]
                
                # Only create context if there's data in the window
                if window_audio_segments or window_video_frames:
                    context = SynchronizedContext(
                        start_timestamp=current_start,
                        end_timestamp=current_end,
                        audio_segments=window_audio_segments,
                        video_frames=window_video_frames,
                        metadata={
                            "chunk_type": "fixed_size",
                            "chunk_size": chunk_size,
                            "audio_segment_count": len(window_audio_segments),
                            "video_frame_count": len(window_video_frames),
                        }
                    )
                    contexts.append(context)
                    logger.debug(f"Created context: {current_start:.2f}s - {current_end:.2f}s "
                               f"({len(window_audio_segments)} audio segments, "
                               f"{len(window_video_frames)} video frames)")
                
                current_start = current_end
        
        logger.info(f"Created {len(contexts)} synchronized contexts")
        return contexts
    
    def _segment_overlaps_window(
        self,
        segment: AudioSegment,
        window_start: float,
        window_end: float
    ) -> bool:
        """Check if an audio segment overlaps with a time window.
        
        Args:
            segment: AudioSegment to check.
            window_start: Start of time window.
            window_end: End of time window.
            
        Returns:
            True if segment overlaps with window, False otherwise.
        """
        # Segment overlaps if it starts before window ends and ends after window starts
        return segment.start_time < window_end and segment.end_time > window_start
    
    def map_frame_to_segments(
        self,
        frame_timestamp: float,
        segments: List[AudioSegment],
        tolerance: float = 1.0
    ) -> List[AudioSegment]:
        """Map a video frame timestamp to overlapping audio segments.
        
        Args:
            frame_timestamp: Timestamp of video frame in seconds.
            segments: List of AudioSegment objects to search.
            tolerance: Time tolerance in seconds for matching (default: 1.0s).
            
        Returns:
            List of AudioSegment objects that overlap with the frame timestamp.
        """
        matching_segments = [
            seg for seg in segments
            if seg.start_time <= frame_timestamp <= seg.end_time
            or abs(seg.start_time - frame_timestamp) <= tolerance
            or abs(seg.end_time - frame_timestamp) <= tolerance
        ]
        return matching_segments
    
    def get_overlapping_segments(
        self,
        start_time: float,
        end_time: float,
        segments: List[AudioSegment]
    ) -> List[AudioSegment]:
        """Get all audio segments that overlap with a time range.
        
        Args:
            start_time: Start of time range.
            end_time: End of time range.
            segments: List of AudioSegment objects to search.
            
        Returns:
            List of AudioSegment objects that overlap with the time range.
        """
        return [
            seg for seg in segments
            if self._segment_overlaps_window(seg, start_time, end_time)
        ]
