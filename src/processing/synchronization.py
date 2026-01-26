"""Temporal context synchronization module.

This module handles synchronization of audio segments and video frames
into time-aligned contexts for summarization.

Chunking is time-based: contiguous 5-minute windows across the full video
timeline. Scene detection does not affect chunk boundaries; it is used only
to enrich each 5-minute chunk with keyframes from overlapping scenes.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple

from src.models.data_models import AudioSegment, VideoFrame, SynchronizedContext
from config.settings import Settings

logger = logging.getLogger(__name__)

# Default chunk size: 5 minutes per project specification
CHUNK_SIZE_SECONDS = 300


class ContextSynchronizer:
    """Handles synchronization of audio segments and video frames into
    contiguous 5-minute time-based chunks. Keyframes from overlapping
    scenes enrich each chunk as visual context.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize ContextSynchronizer.

        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self.chunk_size = getattr(
            self.settings, "chunk_size_seconds", CHUNK_SIZE_SECONDS
        )

    def synchronize_contexts(
        self,
        audio_segments: List[AudioSegment],
        video_frames: List[VideoFrame],
        chunk_size: Optional[float] = None,
        scene_boundaries: Optional[List[float]] = None,
        video_duration: Optional[float] = None,
    ) -> List[SynchronizedContext]:
        """Create time-aligned contexts as contiguous 5-minute chunks.

        Chunks are fixed-duration windows (default 5 minutes) across the full
        video timeline. The final chunk may be shorter if the video ends
        before the next boundary. Scene detection does not define chunk
        boundaries; scenes are used only to attach overlapping keyframes
        to each chunk.

        Args:
            audio_segments: List of AudioSegment objects with timestamps.
            video_frames: List of VideoFrame objects (keyframes from scene
                detection) with timestamps.
            chunk_size: Size of each chunk in seconds (default 300).
            scene_boundaries: Scene boundary timestamps. Used only to assign
                keyframes to chunks by scene overlap.
            video_duration: Total video duration in seconds. Used for
                timeline end and scene intervals. If None, derived from
                audio/video timestamps.

        Returns:
            List of SynchronizedContext objects, one per 5-minute window.
        """
        size = chunk_size if chunk_size is not None else self.chunk_size

        # Timeline: [0, end_time]
        all_timestamps: List[float] = []
        if audio_segments:
            all_timestamps.extend([s.start_time for s in audio_segments])
            all_timestamps.extend([s.end_time for s in audio_segments])
        if video_frames:
            all_timestamps.extend([f.timestamp for f in video_frames])

        if not all_timestamps and video_duration is None:
            raise ValueError(
                "No audio, video, or video_duration provided - cannot synchronize contexts"
            )

        start_time = 0.0
        end_time = float(video_duration) if video_duration is not None else 0.0
        if all_timestamps:
            end_time = max(end_time, max(all_timestamps))

        if end_time <= 0:
            raise ValueError("Invalid timeline end (duration or timestamps)")

        logger.info(
            "Synchronizing contexts: 5-minute time-based chunking from %.2fs to %.2fs (chunk_size=%.0fs)",
            start_time,
            end_time,
            size,
        )

        # Build (scene_start, scene_end, keyframe) for scene-overlap assignment
        scene_keyframes: List[Tuple[float, float, VideoFrame]] = []
        if scene_boundaries is not None and video_duration is not None and video_frames:
            scene_keyframes = self._build_scene_keyframe_list(
                scene_boundaries, video_duration, video_frames
            )
            logger.debug(
                "Built %d scene→keyframe mappings for overlap-based assignment",
                len(scene_keyframes),
            )

        contexts: List[SynchronizedContext] = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + size, end_time)

            window_audio = [
                seg
                for seg in audio_segments
                if self._segment_overlaps_window(seg, current_start, current_end)
            ]

            if scene_keyframes:
                window_frames = self._keyframes_for_overlapping_scenes(
                    scene_keyframes, current_start, current_end
                )
            else:
                # Include frames at chunk end for final chunk only (keyframe at end_time)
                is_last = current_end >= end_time
                window_frames = [
                    f
                    for f in video_frames
                    if current_start <= f.timestamp < current_end
                    or (is_last and current_start <= f.timestamp <= current_end)
                ]

            ctx = SynchronizedContext(
                start_timestamp=current_start,
                end_timestamp=current_end,
                audio_segments=window_audio,
                video_frames=window_frames,
                metadata={
                    "chunk_type": "time_based",
                    "chunk_size_seconds": size,
                    "audio_segment_count": len(window_audio),
                    "video_frame_count": len(window_frames),
                },
            )
            contexts.append(ctx)
            logger.debug(
                "Chunk %.2fs–%.2fs: %d audio segments, %d keyframes",
                current_start,
                current_end,
                len(window_audio),
                len(window_frames),
            )

            current_start = current_end

        logger.info("Created %d contiguous 5-minute chunks", len(contexts))
        return contexts

    def _build_scene_keyframe_list(
        self,
        scene_boundaries: List[float],
        video_duration: float,
        video_frames: List[VideoFrame],
    ) -> List[Tuple[float, float, VideoFrame]]:
        """Build (scene_start, scene_end, keyframe) for each scene.

        Scenes are [0, b0), [b0, b1), ..., [b_{n-1}, video_duration].
        Keyframes are extracted at b0, b1, ...; keyframe at b_i represents
        the scene [b_i, b_{i+1}).
        """
        bounds = [0.0] + sorted(set(scene_boundaries)) + [float(video_duration)]
        bounds = sorted(set(bounds))
        tolerance = 0.01

        def frame_at(t: float) -> Optional[VideoFrame]:
            for f in video_frames:
                if abs(f.timestamp - t) <= tolerance:
                    return f
            best = None
            best_d = float("inf")
            for f in video_frames:
                d = abs(f.timestamp - t)
                if d < best_d:
                    best_d, best = d, f
            return best

        result: List[Tuple[float, float, VideoFrame]] = []
        for i in range(1, len(bounds) - 1):
            s_start, s_end = bounds[i], bounds[i + 1]
            kf = frame_at(s_start)
            if kf is not None:
                result.append((s_start, s_end, kf))
        return result

    def _keyframes_for_overlapping_scenes(
        self,
        scene_keyframes: List[Tuple[float, float, VideoFrame]],
        c_start: float,
        c_end: float,
    ) -> List[VideoFrame]:
        """Return keyframes whose scene overlaps [c_start, c_end)."""
        out: List[VideoFrame] = []
        for s_start, s_end, kf in scene_keyframes:
            if s_start < c_end and s_end > c_start:
                out.append(kf)
        return out

    def _segment_overlaps_window(
        self,
        segment: AudioSegment,
        window_start: float,
        window_end: float,
    ) -> bool:
        """True if segment overlaps [window_start, window_end)."""
        return segment.start_time < window_end and segment.end_time > window_start

    def map_frame_to_segments(
        self,
        frame_timestamp: float,
        segments: List[AudioSegment],
        tolerance: float = 1.0,
    ) -> List[AudioSegment]:
        """Map a video frame timestamp to overlapping audio segments."""
        return [
            seg
            for seg in segments
            if seg.start_time <= frame_timestamp <= seg.end_time
            or abs(seg.start_time - frame_timestamp) <= tolerance
            or abs(seg.end_time - frame_timestamp) <= tolerance
        ]

    def get_overlapping_segments(
        self,
        start_time: float,
        end_time: float,
        segments: List[AudioSegment],
    ) -> List[AudioSegment]:
        """Return segments overlapping [start_time, end_time)."""
        return [
            seg
            for seg in segments
            if self._segment_overlaps_window(seg, start_time, end_time)
        ]
