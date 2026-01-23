"""Main pipeline orchestration for LifeStream.

This module provides the main entry point for processing video files
into structured daily summaries.
"""

import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.ingestion.media_processor import MediaProcessor
from src.audio.diarization import SpeakerDiarizer
from src.audio.asr import ASRProcessor
from src.video.scene_detection import SceneDetector
from src.processing.synchronization import ContextSynchronizer
from src.processing.meeting_detection import MeetingDetector
from src.processing.summarization import LLMSummarizer
from src.models.data_models import DailySummary
from config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_video(
    video_path: str,
    output_path: Optional[str] = None,
    settings: Optional[Settings] = None,
    verbose: bool = False
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
    
    # Phase 2: Media Processing
    logger.info("Phase 2: Media ingestion and track splitting...")
    try:
        media_processor = MediaProcessor(settings)
        
        # Extract audio and video tracks
        audio_output = Path(settings.temp_dir) / f"{Path(video_path).stem}_audio.wav"
        frames_output_dir = Path(settings.temp_dir) / f"{Path(video_path).stem}_frames"
        audio_path, video_frames, video_metadata = media_processor.split_media_tracks(
            video_path,
            str(audio_output),
            str(frames_output_dir)
        )
        logger.info(f"Extracted audio: {audio_path}")
        logger.info(f"Extracted {len(video_frames)} video frames")
        
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        raise RuntimeError(f"Media processing failed: {e}") from e
    
    # Phase 3: Audio Processing (MANDATORY)
    logger.info("Phase 3: Audio processing (diarization + ASR) - MANDATORY...")
    diarizer = SpeakerDiarizer(settings)
    asr_processor = ASRProcessor(settings)
    
    # Diarization is MANDATORY - raise error if it fails
    logger.info("Performing speaker diarization (MANDATORY)...")
    diarization_segments = diarizer.diarize_audio(audio_path)
    if not diarization_segments or len(diarization_segments) == 0:
        raise RuntimeError("Diarization failed - no speaker segments detected. Diarization is mandatory.")
    logger.info(f"Diarization complete: {len(diarization_segments)} segments, {len(set(seg.speaker_id for seg in diarization_segments))} unique speakers")
    
    # ASR is MANDATORY - raise error if it fails
    logger.info("Performing speech recognition (MANDATORY)...")
    audio_segments = asr_processor.process_audio_with_diarization(
        audio_path,
        diarization_segments
    )
    if not audio_segments or len(audio_segments) == 0:
        raise RuntimeError("ASR failed - no audio segments with transcripts. ASR is mandatory.")
    logger.info(f"ASR complete: {len(audio_segments)} segments with transcripts")
    
    # Phase 4: Video Processing (Scene Detection - MANDATORY)
    logger.info("Phase 4: Video processing (scene detection) - MANDATORY...")
    scene_detector = SceneDetector(settings)
    
    # Scene detection is MANDATORY - raise error if it fails
    logger.info("Detecting scene boundaries (MANDATORY)...")
    scene_boundaries = scene_detector.detect_scene_changes(video_path)
    if not scene_boundaries or len(scene_boundaries) == 0:
        logger.warning("No scene boundaries detected - video may be a single continuous scene")
        # Still create at least one boundary at the end for chunking
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        scene_boundaries = [duration] if duration > 0 else []
        logger.info(f"Using video duration as single scene boundary: {duration:.2f}s")
    
    logger.info(f"Scene detection complete: {len(scene_boundaries)} scene boundaries detected")
    
    # Extract keyframes at scene boundaries
    logger.info("Extracting keyframes at scene boundaries...")
    scene_keyframes = scene_detector.extract_keyframes(
        video_path,
        scene_boundaries,
        output_dir=Path(settings.temp_dir) / f"{Path(video_path).stem}_keyframes"
    )
    logger.info(f"Extracted {len(scene_keyframes)} keyframes at scene boundaries")
    
    all_video_frames = scene_keyframes
    logger.info(f"Total video frames (scene-based): {len(all_video_frames)}")
    
    # Phase 5: Integration & Synthesis (using scene boundaries for chunking)
    logger.info("Phase 5: Temporal context synchronization (scene-based chunking)...")
    synchronizer = ContextSynchronizer(settings)
    
    # Synchronize audio and video using SCENE BOUNDARIES (per project guidelines)
    # Summary chunks must be based on scene detection boundaries
    contexts = synchronizer.synchronize_contexts(
        audio_segments,
        all_video_frames,
        scene_boundaries=scene_boundaries  # Use scene boundaries for chunking
    )
    if not contexts or len(contexts) == 0:
        raise RuntimeError("Synchronization failed - no contexts created. This should not happen.")
    logger.info(f"Synchronization complete: {len(contexts)} scene-based contexts")
    
    # Phase 5.5: Meeting Detection
    logger.info("Phase 5.5: Meeting detection...")
    try:
        meeting_detector = MeetingDetector(settings)
        
        # Detect meeting vs non-meeting for each context
        for context in contexts:
            metadata = meeting_detector.get_context_metadata(context)
            context.metadata.update(metadata)
            logger.debug(f"Context {context.start_timestamp:.2f}s: {metadata['context_type']} "
                        f"({metadata['num_speakers']} speakers)")
        
        meeting_count = sum(1 for ctx in contexts if ctx.metadata.get('is_meeting') is True)
        logger.info(f"Meeting detection complete: {meeting_count}/{len(contexts)} contexts are meetings")
        
    except Exception as e:
        logger.warning(f"Phase 5.5 (meeting detection) failed: {e}. Continuing without meeting detection.")
        # Don't raise - allow processing to continue
    
    # Phase 6: LLM Summarization (MANDATORY)
    logger.info("Phase 6: LLM summarization (MANDATORY)...")
    summarizer = LLMSummarizer(settings)
    
    # LLM summarization is MANDATORY - raise error if it fails
    # Create daily summary from scene-based contexts
    video_date = datetime.fromtimestamp(Path(video_path).stat().st_mtime).strftime("%Y-%m-%d")
    daily_summary = summarizer.create_daily_summary(
        contexts,
        date=video_date,
        video_source=video_path
    )
    daily_summary.video_metadata = video_metadata
    
    if not daily_summary.time_blocks or len(daily_summary.time_blocks) == 0:
        raise RuntimeError("LLM summarization failed - no time blocks created. Summarization is mandatory.")
    
    logger.info(f"Summarization complete: {len(daily_summary.time_blocks)} scene-based time blocks")
    
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
