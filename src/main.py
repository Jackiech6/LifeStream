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
    
    # Phase 3: Audio Processing
    logger.info("Phase 3: Audio processing (diarization + ASR)...")
    try:
        diarizer = SpeakerDiarizer(settings)
        asr_processor = ASRProcessor(settings)
        
        # Diarization
        logger.info("Performing speaker diarization...")
        diarization_segments = diarizer.diarize_audio(audio_path)
        logger.info(f"Diarization complete: {len(diarization_segments)} segments")
        
        # ASR with diarization
        logger.info("Performing speech recognition...")
        audio_segments = asr_processor.process_audio_with_diarization(
            audio_path,
            diarization_segments
        )
        logger.info(f"ASR complete: {len(audio_segments)} segments with transcripts")
        
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        raise RuntimeError(f"Audio processing failed: {e}") from e
    
    # Phase 4: Video Processing (Scene Detection)
    logger.info("Phase 4: Video processing (scene detection)...")
    try:
        scene_detector = SceneDetector(settings)
        
        # Detect scenes and extract keyframes
        scene_keyframes = scene_detector.extract_keyframes_with_scene_detection(
            video_path,
            output_dir=Path(settings.temp_dir) / f"{Path(video_path).stem}_keyframes"
        )
        logger.info(f"Scene detection complete: {len(scene_keyframes)} keyframes")
        
        # Combine with frames from media processor
        # Use scene-detected keyframes if available, otherwise use regular frames
        all_video_frames = scene_keyframes if scene_keyframes else video_frames
        logger.info(f"Total video frames: {len(all_video_frames)}")
        
    except Exception as e:
        logger.warning(f"Phase 4 failed (using regular frames): {e}")
        all_video_frames = video_frames  # Fall back to regular frames
    
    # Phase 5: Integration & Synthesis
    logger.info("Phase 5: Temporal context synchronization...")
    try:
        synchronizer = ContextSynchronizer(settings)
        
        # Synchronize audio and video
        contexts = synchronizer.synchronize_contexts(
            audio_segments,
            all_video_frames,
            chunk_size=settings.chunk_size_seconds
        )
        logger.info(f"Synchronization complete: {len(contexts)} contexts")
        
    except Exception as e:
        logger.error(f"Phase 5 (synchronization) failed: {e}")
        raise RuntimeError(f"Synchronization failed: {e}") from e
    
    # Phase 5: LLM Summarization
    logger.info("Phase 5: LLM summarization...")
    try:
        summarizer = LLMSummarizer(settings)
        
        # Create daily summary
        video_date = datetime.fromtimestamp(Path(video_path).stat().st_mtime).strftime("%Y-%m-%d")
        daily_summary = summarizer.create_daily_summary(
            contexts,
            date=video_date,
            video_source=video_path
        )
        daily_summary.video_metadata = video_metadata
        logger.info(f"Summarization complete: {len(daily_summary.time_blocks)} time blocks")
        
    except Exception as e:
        logger.error(f"Phase 5 (summarization) failed: {e}")
        raise RuntimeError(f"Summarization failed: {e}") from e
    
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
