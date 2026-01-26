"""Main pipeline orchestration for LifeStream.

This module provides the main entry point for processing video files
into structured daily summaries. Optimized for <20 min processing per 1 hr video.
"""

import logging
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Callable

from src.ingestion.media_processor import MediaProcessor
from src.audio.diarization import SpeakerDiarizer
from src.audio.asr import ASRProcessor
from src.video.scene_detection import SceneDetector
from src.processing.synchronization import ContextSynchronizer
from src.processing.meeting_detection import MeetingDetector
from src.processing.summarization import LLMSummarizer
from src.models.data_models import DailySummary, AudioSegment, VideoFrame
from config.settings import Settings
from src.utils.timing import stage_timing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _run_audio_branch(
    audio_path: str, settings: Settings, timings: Optional[Dict[str, int]] = None
) -> List[AudioSegment]:
    """Diarization + ASR. Used in parallel with scene branch."""
    diarizer = SpeakerDiarizer(settings)
    asr_processor = ASRProcessor(settings)
    with stage_timing("diarization", timings):
        diarization_segments = diarizer.diarize_audio(audio_path)
    if not diarization_segments or len(diarization_segments) == 0:
        raise RuntimeError("Diarization failed - no speaker segments detected. Diarization is mandatory.")
    logger.info(f"Diarization complete: {len(diarization_segments)} segments, {len(set(seg.speaker_id for seg in diarization_segments))} unique speakers")
    with stage_timing("asr", timings):
        audio_segments = asr_processor.process_audio_with_diarization(
            audio_path, diarization_segments
        )
    if not audio_segments or len(audio_segments) == 0:
        raise RuntimeError("ASR failed - no audio segments with transcripts. ASR is mandatory.")
    logger.info(f"ASR complete: {len(audio_segments)} segments with transcripts")
    return audio_segments


def _run_scene_branch(
    video_path: str,
    settings: Settings,
    temp_dir: Path,
    timings: Optional[Dict[str, int]] = None,
) -> Tuple[List[float], List[VideoFrame]]:
    """Scene detection + keyframe extraction. Used in parallel with audio branch."""
    scene_detector = SceneDetector(settings)
    with stage_timing("scene_detection", timings):
        scene_boundaries = scene_detector.detect_scene_changes(video_path)
    if not scene_boundaries or len(scene_boundaries) == 0:
        logger.warning("No scene boundaries detected - video may be a single continuous scene")
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        scene_boundaries = [duration] if duration > 0 else []
        logger.info(f"Using video duration as single scene boundary: {duration:.2f}s")
    logger.info(f"Scene detection complete: {len(scene_boundaries)} scene boundaries detected")
    keyframes_dir = temp_dir / f"{Path(video_path).stem}_keyframes"
    with stage_timing("keyframes", timings):
        scene_keyframes = scene_detector.extract_keyframes(
            video_path, scene_boundaries, output_dir=keyframes_dir
        )
    logger.info(f"Extracted {len(scene_keyframes)} keyframes at scene boundaries")
    return scene_boundaries, scene_keyframes


def process_video_streaming(
    video_url: str,
    local_video_path: str,
    wait_for_download: Callable[[], None],
    video_stem: str,
    settings: Optional[Settings] = None,
    verbose: bool = False,
    timings: Optional[Dict[str, int]] = None,
) -> DailySummary:
    """Process video using streaming URL for audio extraction while download runs in parallel.

    Overlaps S3 transfer with decode: audio is extracted from presigned URL (ffmpeg streams)
    while the full file is downloaded in the background. Once download completes, scene
    detection and keyframes run on the local file. All other pipeline stages are unchanged.

    Args:
        video_url: Presigned GET URL for the video (e.g. S3).
        local_video_path: Path where the video is or will be downloaded (must exist after wait).
        wait_for_download: Callable that blocks until the file at local_video_path is ready.
        video_stem: Base name for temp outputs (e.g. from s3_key stem).
        settings: Application settings.
        verbose: Verbose logging.
        timings: Optional dict to record stage timings.

    Returns:
        DailySummary same as process_video().
    """
    if settings is None:
        settings = Settings()
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    t: Dict[str, int] = timings if timings is not None else {}
    temp_dir = Path(settings.temp_dir)
    logger.info("Starting LifeStream streaming pipeline (audio from URL, scene from local after download)")

    # Phase 2a: Metadata and audio from URL (overlaps with download elsewhere)
    media_processor = MediaProcessor(settings)
    with stage_timing("audio_extraction", t):
        video_metadata = media_processor.get_video_metadata(video_url)
        audio_output = temp_dir / f"{video_stem}_audio.wav"
        audio_path = media_processor.extract_audio_track(video_url, str(audio_output))
    logger.info(f"Extracted audio from URL: {audio_path}")

    # Block until full video is on disk for scene detection
    wait_for_download()
    if not Path(local_video_path).exists():
        raise RuntimeError(f"Local video file missing after wait: {local_video_path}")

    # Phase 3+4: Audio branch (diarization + ASR) || Scene branch (local file) — parallel
    max_workers = getattr(settings, "parallel_max_workers", 2)
    audio_segments: List[AudioSegment] = []
    scene_boundaries: List[float] = []
    scene_keyframes: List[VideoFrame] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_audio = ex.submit(_run_audio_branch, audio_path, settings, t)
        fut_scene = ex.submit(_run_scene_branch, local_video_path, settings, temp_dir, t)
        for fut in as_completed([fut_audio, fut_scene]):
            try:
                result = fut.result()
                if fut is fut_audio:
                    audio_segments = result
                else:
                    scene_boundaries, scene_keyframes = result
            except Exception as e:
                logger.error(f"Parallel phase failed: {e}")
                raise RuntimeError(f"Pipeline phase failed: {e}") from e

    all_video_frames = scene_keyframes
    video_duration = video_metadata.duration

    logger.info("Phase 5: Temporal context synchronization...")
    with stage_timing("sync", t):
        synchronizer = ContextSynchronizer(settings)
        contexts = synchronizer.synchronize_contexts(
            audio_segments,
            all_video_frames,
            chunk_size=300,
            scene_boundaries=scene_boundaries,
            video_duration=video_duration,
        )
    if not contexts or len(contexts) == 0:
        raise RuntimeError("Synchronization failed - no contexts created.")

    logger.info("Phase 5.5: Meeting detection...")
    try:
        meeting_detector = MeetingDetector(settings)
        for context in contexts:
            metadata = meeting_detector.get_context_metadata(context)
            context.metadata.update(metadata)
    except Exception as e:
        logger.warning("Meeting detection failed (non-fatal): %s", e)

    logger.info("Phase 6: LLM summarization...")
    summarizer = LLMSummarizer(settings)
    video_date = datetime.fromtimestamp(Path(local_video_path).stat().st_mtime).strftime("%Y-%m-%d")
    with stage_timing("summarization", t):
        daily_summary = summarizer.create_daily_summary(
            contexts,
            date=video_date,
            video_source=local_video_path,
        )
    daily_summary.video_metadata = video_metadata

    if not daily_summary.time_blocks or len(daily_summary.time_blocks) == 0:
        raise RuntimeError("LLM summarization failed - no time blocks created.")

    date_str = datetime.fromtimestamp(Path(local_video_path).stat().st_mtime).strftime("%Y-%m-%d")
    output_file = Path(settings.output_dir) / f"{date_str}_{video_stem}_summary.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summarizer.format_markdown_output(daily_summary))
    logger.info("Pipeline complete (streaming): %s", output_file)
    return daily_summary


def process_video(
    video_path: str,
    output_path: Optional[str] = None,
    settings: Optional[Settings] = None,
    verbose: bool = False,
    timings: Optional[Dict[str, int]] = None,
) -> DailySummary:
    """Process a video file through the complete pipeline.
    
    This function orchestrates all phases of the LifeStream pipeline:
    1. Media ingestion (audio/video extraction)
    2. Speaker diarization
    3. Automatic speech recognition (ASR)
    4. Scene detection
    5. Temporal context synchronization
    6. LLM summarization
    7. Markdown output generation
    
    Args:
        video_path: Path to the input video file.
        output_path: Optional path for output Markdown file. If None, uses settings output_dir.
        settings: Application settings. If None, creates default settings.
        verbose: Enable verbose logging.
        
    Returns:
        DailySummary object with all time blocks.
        
    Raises:
        ValueError: If video file cannot be processed.
        RuntimeError: If pipeline fails at any stage.
    """
    if settings is None:
        settings = Settings()
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Starting LifeStream pipeline for: {video_path}")
    t: Dict[str, int] = timings if timings is not None else {}

    # Phase 2: Media ingestion (audio only; scene keyframes replace interval frames)
    logger.info("Phase 2: Media ingestion (audio extraction)...")
    try:
        with stage_timing("audio_extraction", t):
            media_processor = MediaProcessor(settings)
            audio_output = Path(settings.temp_dir) / f"{Path(video_path).stem}_audio.wav"
            frames_output_dir = Path(settings.temp_dir) / f"{Path(video_path).stem}_frames"
            audio_path, _, video_metadata = media_processor.split_media_tracks(
                video_path,
                str(audio_output),
                str(frames_output_dir),
                extract_frames=False,
            )
        logger.info(f"Extracted audio: {audio_path}")
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        raise RuntimeError(f"Media processing failed: {e}") from e

    # Phase 3+4: Audio (diarization + ASR) || Scene (detection + keyframes) — parallel
    max_workers = getattr(settings, "parallel_max_workers", 2)
    logger.info("Phase 3+4: Audio pipeline (diarization + ASR) || Scene pipeline (detection + keyframes)... (max_workers=%d)", max_workers)
    temp_dir = Path(settings.temp_dir)
    audio_segments: List[AudioSegment] = []
    scene_boundaries: List[float] = []
    scene_keyframes: List[VideoFrame] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_audio = ex.submit(_run_audio_branch, audio_path, settings, t)
        fut_scene = ex.submit(_run_scene_branch, video_path, settings, temp_dir, t)
        for fut in as_completed([fut_audio, fut_scene]):
            try:
                result = fut.result()
                if fut is fut_audio:
                    audio_segments = result
                else:
                    scene_boundaries, scene_keyframes = result
            except Exception as e:
                logger.error(f"Parallel phase failed: {e}")
                raise RuntimeError(f"Pipeline phase failed: {e}") from e

    all_video_frames = scene_keyframes
    
    # Phase 5: Integration & Synthesis (5-minute time-based chunking)
    video_duration = video_metadata.duration
    logger.info("Phase 5: Temporal context synchronization (5-minute time-based chunking)...")
    with stage_timing("sync", t):
        synchronizer = ContextSynchronizer(settings)
        contexts = synchronizer.synchronize_contexts(
            audio_segments,
            all_video_frames,
            chunk_size=300,
            scene_boundaries=scene_boundaries,
            video_duration=video_duration,
        )
    if not contexts or len(contexts) == 0:
        raise RuntimeError("Synchronization failed - no contexts created. This should not happen.")
    logger.info(f"Synchronization complete: {len(contexts)} contiguous 5-minute chunks")
    
    # Phase 5.5: Meeting Detection
    logger.info("Phase 5.5: Meeting detection...")
    try:
        meeting_detector = MeetingDetector(settings)
        
        # Detect meeting vs non-meeting for each context (heuristics only; no LLM)
        for context in contexts:
            metadata = meeting_detector.get_context_metadata(context)
            context.metadata.update(metadata)
            logger.debug(f"Context {context.start_timestamp:.2f}s: {metadata['context_type']} "
                        f"({metadata['num_speakers']} speakers)")
        meeting_count = sum(1 for ctx in contexts if ctx.metadata.get('is_meeting') is True)
        logger.info(f"Meeting detection complete: {meeting_count}/{len(contexts)} contexts are meetings")
        
    except Exception as e:
        logger.error(f"Phase 5.5 (meeting detection) failed: {e}")
        # Meeting detection is important but not critical - log error but continue
        # This allows processing to complete even if meeting detection fails
        logger.warning("Continuing without meeting detection metadata")
    
    # Phase 6: LLM Summarization (MANDATORY) — one ChatGPT call per 5-min chunk
    logger.info("Phase 6: LLM summarization (MANDATORY)...")
    summarizer = LLMSummarizer(settings)
    video_date = datetime.fromtimestamp(Path(video_path).stat().st_mtime).strftime("%Y-%m-%d")
    with stage_timing("summarization", t):
        daily_summary = summarizer.create_daily_summary(
            contexts,
            date=video_date,
            video_source=video_path,
        )
    daily_summary.video_metadata = video_metadata
    if not daily_summary.time_blocks or len(daily_summary.time_blocks) == 0:
        raise RuntimeError("LLM summarization failed - no time blocks created. Summarization is mandatory.")
    logger.info(f"Summarization complete: {len(daily_summary.time_blocks)} 5-minute time blocks")
    
    # Save output
    if output_path:
        output_file = Path(output_path)
    else:
        video_name = Path(video_path).stem
        date_str = datetime.fromtimestamp(Path(video_path).stat().st_mtime).strftime("%Y-%m-%d")
        output_file = Path(settings.output_dir) / f"{date_str}_{video_name}_summary.md"
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Writing output to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        markdown = summarizer.format_markdown_output(daily_summary)
        f.write(markdown)
    
    logger.info("Pipeline complete!")
    logger.info(f"Output saved to: {output_file}")
    
    return daily_summary


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='LifeStream: Convert video to structured daily summary',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python -m src.main --input video.mp4 --output summary.md
  
  # With verbose logging
  python -m src.main --input video.mp4 --output summary.md --verbose
  
  # Specify output directory
  python -m src.main --input video.mp4 --output-dir ./output
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Input video file path'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output Markdown file path (default: auto-generated in output_dir)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for summaries (default: from settings)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    video_path = Path(args.input)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)
    
    # Load settings
    settings = Settings()
    
    # Override output directory if specified
    if args.output_dir:
        settings.output_dir = str(Path(args.output_dir).expanduser())
        Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Process video
    try:
        daily_summary = process_video(
            str(video_path),
            output_path=args.output,
            settings=settings,
            verbose=args.verbose
        )
        
        print(f"\n✅ Success! Generated {len(daily_summary.time_blocks)} time blocks")
        if args.output:
            print(f"📄 Output: {args.output}")
        else:
            video_name = Path(args.input).stem
            date_str = datetime.fromtimestamp(video_path.stat().st_mtime).strftime("%Y-%m-%d")
            output_file = Path(settings.output_dir) / f"{date_str}_{video_name}_summary.md"
            print(f"📄 Output: {output_file}")
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
