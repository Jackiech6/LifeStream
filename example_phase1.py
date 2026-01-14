#!/usr/bin/env python3
"""Example script demonstrating Phase 1 implementation.

This script shows that all Phase 1 components are working:
- Configuration loading
- Data models
- Logging setup
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import Settings
from src.models.data_models import (
    VideoMetadata,
    AudioSegment,
    VideoFrame,
    Participant,
    TimeBlock,
    DailySummary,
    SynchronizedContext,
)
from src.utils.logging_config import setup_logging, get_logger


def main():
    """Demonstrate Phase 1 functionality."""
    print("=" * 60)
    print("LifeStream Phase 1 - Implementation Verification")
    print("=" * 60)
    
    # 1. Test Settings
    print("\n1. Testing Settings Configuration...")
    try:
        settings = Settings()
        print(f"   ✓ Settings loaded successfully")
        print(f"   ✓ Output directory: {settings.output_dir}")
        print(f"   ✓ Temp directory: {settings.temp_dir}")
        print(f"   ✓ Log level: {settings.log_level}")
    except Exception as e:
        print(f"   ✗ Error loading settings: {e}")
        return
    
    # 2. Test Logging
    print("\n2. Testing Logging Configuration...")
    try:
        logger = setup_logging(settings)
        logger.info("Test log message - Phase 1 logging is working!")
        print("   ✓ Logging configured successfully")
    except Exception as e:
        print(f"   ✗ Error setting up logging: {e}")
        return
    
    # 3. Test Data Models
    print("\n3. Testing Data Models...")
    
    # VideoMetadata
    try:
        video_meta = VideoMetadata(
            file_path="/path/to/test_video.mp4",
            duration=3600.0,
            fps=30.0,
            resolution=(1920, 1080),
            format="mp4"
        )
        print(f"   ✓ VideoMetadata created: {video_meta.format}, {video_meta.resolution}")
    except Exception as e:
        print(f"   ✗ Error creating VideoMetadata: {e}")
        return
    
    # AudioSegment
    try:
        audio_seg = AudioSegment(
            start_time=0.0,
            end_time=5.0,
            speaker_id="Speaker_01",
            transcript_text="Hello, this is a test transcript."
        )
        print(f"   ✓ AudioSegment created: {audio_seg.speaker_id}, duration={audio_seg.duration}s")
    except Exception as e:
        print(f"   ✗ Error creating AudioSegment: {e}")
        return
    
    # VideoFrame
    try:
        video_frame = VideoFrame(
            timestamp=10.5,
            scene_change_detected=True,
            scene_id=1
        )
        print(f"   ✓ VideoFrame created: timestamp={video_frame.timestamp}s, scene_change={video_frame.scene_change_detected}")
    except Exception as e:
        print(f"   ✗ Error creating VideoFrame: {e}")
        return
    
    # Participant
    try:
        participant = Participant(
            speaker_id="Speaker_01",
            real_name="John Doe",
            role="Host"
        )
        print(f"   ✓ Participant created: {participant.speaker_id} -> {participant.real_name}")
    except Exception as e:
        print(f"   ✗ Error creating Participant: {e}")
        return
    
    # TimeBlock
    try:
        time_block = TimeBlock(
            start_time="09:00 AM",
            end_time="09:45 AM",
            activity="Commute",
            location="Car",
            participants=[participant],
            transcript_summary="User drove to work while listening to a podcast.",
            action_items=["Review meeting notes", "Prepare presentation"]
        )
        print(f"   ✓ TimeBlock created: {time_block.activity} ({time_block.start_time} - {time_block.end_time})")
    except Exception as e:
        print(f"   ✗ Error creating TimeBlock: {e}")
        return
    
    # SynchronizedContext
    try:
        context = SynchronizedContext(
            start_timestamp=0.0,
            end_timestamp=300.0,
            audio_segments=[audio_seg],
            video_frames=[video_frame]
        )
        print(f"   ✓ SynchronizedContext created: duration={context.duration}s")
    except Exception as e:
        print(f"   ✗ Error creating SynchronizedContext: {e}")
        return
    
    # DailySummary
    try:
        daily_summary = DailySummary(
            date="2026-01-09",
            video_source="/path/to/test_video.mp4",
            video_metadata=video_meta,
            time_blocks=[time_block],
            total_duration=3600.0
        )
        print(f"   ✓ DailySummary created: {daily_summary.date}, {len(daily_summary.time_blocks)} time blocks")
    except Exception as e:
        print(f"   ✗ Error creating DailySummary: {e}")
        return
    
    # 4. Test JSON Serialization
    print("\n4. Testing JSON Serialization (for Stage 2 RAG compatibility)...")
    try:
        json_str = daily_summary.model_dump_json()
        print(f"   ✓ DailySummary JSON serialization: {len(json_str)} characters")
        
        # Test to_dict methods
        audio_dict = audio_seg.to_dict()
        context_dict = context.to_dict()
        time_block_dict = time_block.to_dict()
        summary_dict = daily_summary.to_dict()
        print(f"   ✓ All to_dict() methods working")
    except Exception as e:
        print(f"   ✗ Error in JSON serialization: {e}")
        return
    
    # 5. Test Markdown Output
    print("\n5. Testing Markdown Output...")
    try:
        markdown = daily_summary.to_markdown()
        print(f"   ✓ Markdown generation: {len(markdown)} characters")
        print("\n   Sample Markdown output:")
        print("   " + "-" * 56)
        for line in markdown.split("\n")[:10]:  # Show first 10 lines
            print(f"   {line}")
        print("   " + "-" * 56)
    except Exception as e:
        print(f"   ✗ Error generating Markdown: {e}")
        return
    
    # Summary
    print("\n" + "=" * 60)
    print("Phase 1 Implementation: ✓ COMPLETE")
    print("=" * 60)
    print("\nAll Phase 1 components are working correctly:")
    print("  ✓ Project structure created")
    print("  ✓ Configuration system (Settings)")
    print("  ✓ Logging system")
    print("  ✓ All data models (JSON-serializable)")
    print("  ✓ Markdown output generation")
    print("\nReady to proceed to Phase 2: Media Processing")


if __name__ == "__main__":
    main()
