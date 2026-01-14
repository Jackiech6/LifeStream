# Stage 1 Implementation Plan: Core Processing Engine

## Overview
This document outlines the implementation plan for Stage 1 of the LifeStream Intelligent Diary project. The plan is designed to build a solid foundation that seamlessly integrates with Stages 2 (RAG/Memory) and Stage 3 (Cloud Deployment).

**Estimated Duration:** 1 Week  
**Primary Goal:** Build a working script that takes a video file and produces a structured Markdown log.

---

## Project Structure

```
LifeStream/
├── README.md
├── requirements.txt
├── setup.py
├── .env.example
├── .gitignore
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuration management
├── src/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── media_processor.py   # Feature 1: Media ingestion & splitting
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── diarization.py      # Feature 2: Speaker diarization
│   │   └── asr.py               # Feature 3: ASR processing
│   ├── video/
│   │   ├── __init__.py
│   │   └── scene_detection.py  # Feature 4: Visual sampling
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── synchronization.py  # Feature 5: Temporal context sync
│   │   └── summarization.py    # Feature 6: LLM summarization
│   ├── models/
│   │   ├── __init__.py
│   │   └── data_models.py       # Shared data structures
│   └── main.py                  # Entry point
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_media_processor.py
│   │   ├── test_diarization.py
│   │   ├── test_asr.py
│   │   ├── test_scene_detection.py
│   │   ├── test_synchronization.py
│   │   └── test_summarization.py
│   └── fixtures/
│       ├── sample_videos/
│       ├── sample_audio/
│       └── test_data/
└── output/
    └── .gitkeep                 # Generated summaries go here
```

---

## Implementation Sequence

### Phase 1: Foundation & Data Models (Day 1)

#### 1.1 Project Setup (Mac-Specific)
- [ ] Install Homebrew (if not already installed): `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- [ ] Install FFmpeg via Homebrew: `brew install ffmpeg`
- [ ] Verify FFmpeg installation: `ffmpeg -version`
- [ ] Initialize Python project with `requirements.txt`
- [ ] Set up virtual environment: `python3 -m venv venv`
- [ ] Activate virtual environment: `source venv/bin/activate`
- [ ] Create project structure
- [ ] Configure `.gitignore` (exclude `output/`, `__pycache__/`, `.env`)
- [ ] Set up logging configuration

#### 1.2 Data Models (`src/models/data_models.py`)
**Critical for Stage 2 compatibility:** Design data structures that will be easily serializable for vector storage.

```python
# Key data structures to define:
- VideoMetadata: file_path, duration, fps, resolution, format
- AudioSegment: start_time, end_time, speaker_id, transcript_text
- VideoFrame: timestamp, frame_data, scene_change_detected
- SynchronizedContext: timestamp, audio_segments[], video_frames[]
- DailySummary: date, time_blocks[], metadata
- TimeBlock: start_time, end_time, location, activity, participants[], transcript_summary, action_items[]
```

**Why this matters:** These models will be serialized to JSON for Stage 2 RAG indexing.

---

### Phase 2: Media Processing (Day 2)

#### Feature 1: Media Ingestion & Track Splitting
**File:** `src/ingestion/media_processor.py`

**Implementation Steps:**
1. Use `ffmpeg-python` or `moviepy` for video processing
2. Implement format validation (MP4, AVI, MOV, MKV support)
3. Extract audio track to WAV (16kHz mono for diarization)
4. Extract video frames at original resolution
5. Maintain timestamp mapping between audio and video streams

**Key Functions:**
- `validate_video_format(file_path) -> bool`
- `extract_audio_track(video_path, output_path) -> str`
- `get_video_metadata(video_path) -> VideoMetadata`
- `extract_video_frames(video_path, output_dir) -> List[VideoFrame]`

**Testing:**
- Unit test with various video formats
- Verify audio/video synchronization
- Test error handling for corrupted files

**Dependencies:**
- `ffmpeg-python` or `moviepy`
- `pydub` (for audio manipulation)

---

### Phase 3: Audio Processing (Day 3)

#### Feature 2: Deterministic Speaker Diarization
**File:** `src/audio/diarization.py`

**Implementation Steps:**
1. Research and select diarization library:
   - **Recommended:** `pyannote.audio` (SOTA, requires HuggingFace token)
   - **Alternative:** `speechbrain` or `resemblyzer`
2. Process audio file to identify speaker segments
3. Output: List of segments with `(start_time, end_time, speaker_id)`
4. Handle overlapping speakers (assign to dominant speaker)

**Key Functions:**
- `diarize_audio(audio_path) -> List[AudioSegment]`
- `merge_overlapping_segments(segments) -> List[AudioSegment]`

**Testing:**
- Create test audio with known speaker segments
- Verify >90% accuracy on 3-speaker test case
- Test edge cases (silence, single speaker, overlapping speech)

**Dependencies:**
- `pyannote.audio` (or alternative)
- `torch` (for model inference)
- `librosa` (for audio preprocessing)

**Configuration:**
- Store HuggingFace token in `.env` file
- Add model configuration to `config/settings.py`

#### Feature 3: Automatic Speech Recognition (ASR)
**File:** `src/audio/asr.py`

**Implementation Steps:**
1. Select ASR model:
   - **Recommended:** `whisper` (OpenAI, high accuracy)
   - **Alternative:** `speech_recognition` with Google API or `vosk`
2. Process audio with timestamps
3. Merge ASR output with diarization segments
4. Output: `AudioSegment` objects with `transcript_text` populated

**Key Functions:**
- `transcribe_audio(audio_path, language='en') -> List[Dict]`
- `merge_asr_diarization(asr_output, diarization_output) -> List[AudioSegment]`

**Testing:**
- Test with clear speech audio
- Verify timestamp alignment with diarization
- Test with different accents/languages (if needed)

**Dependencies:**
- `openai-whisper` or `whisper` (local model)
- `torch` (if using local Whisper)

---

### Phase 4: Video Processing (Day 4)

#### Feature 4: Intelligent Visual Sampling
**File:** `src/video/scene_detection.py`

**Implementation Steps:**
1. Implement scene change detection:
   - Use `scenedetect` library (PySceneDetect) for automatic scene detection
   - Alternative: Frame difference analysis with `opencv-python`
2. Extract keyframes at scene boundaries
3. Optionally extract frames at fixed intervals if no scene changes detected
4. Store frames with metadata (timestamp, scene_change_flag)

**Key Functions:**
- `detect_scene_changes(video_path, threshold=0.3) -> List[float]`
- `extract_keyframes(video_path, timestamps) -> List[VideoFrame]`
- `analyze_frame_content(frame) -> Dict` (for future visual analysis)

**Testing:**
- Test with video containing known scene changes
- Verify detection accuracy against manual annotations
- Test with static video (no scene changes)

**Dependencies:**
- `scenedetect` (PySceneDetect)
- `opencv-python` (cv2)
- `numpy`

---

### Phase 5: Integration & Synthesis (Day 5)

#### Feature 5: Temporal Context Synchronization
**File:** `src/processing/synchronization.py`

**Implementation Steps:**
1. Create mapping logic to align:
   - Audio segments (with timestamps) ↔ Video frames (with timestamps)
2. For each time window (e.g., 5-minute chunks), create `SynchronizedContext`:
   - All audio segments in that window
   - All video frames in that window
   - Metadata (location hints from video, activity classification)
3. Handle edge cases (missing audio/video at certain timestamps)

**Key Functions:**
- `synchronize_contexts(audio_segments, video_frames, chunk_size=300) -> List[SynchronizedContext]`
- `map_frame_to_segment(frame_timestamp, segments) -> List[AudioSegment]`

**Testing:**
- Test with perfectly aligned test data
- Test with misaligned timestamps
- Test with missing segments/frames

#### Feature 6: LLM Summarization & Synthesis
**File:** `src/processing/summarization.py`

**Implementation Steps:**
1. Select multimodal LLM API:
   - **Recommended:** OpenAI GPT-4 Vision or Anthropic Claude 3 (multimodal)
   - **Alternative:** Google Gemini Pro Vision
2. Design system prompt with strict Markdown format requirements
3. For each `SynchronizedContext`:
   - Prepare prompt with:
     - Audio transcript (with speaker labels)
     - Keyframe descriptions (or base64-encoded images)
     - Time window information
   - Request structured output matching the required Markdown format
4. Post-process LLM output to ensure format compliance
5. Merge all time blocks into final `DailySummary`

**Key Functions:**
- `summarize_context(context: SynchronizedContext, model='gpt-4-vision-preview') -> TimeBlock`
- `format_markdown_output(daily_summary: DailySummary) -> str`
- `validate_markdown_format(markdown_text) -> bool`

**Prompt Template Structure:**
```
You are a diary summarization system. Given audio transcripts and visual context, 
generate a structured daily log entry in Markdown format.

Required format:
## [START_TIME] - [END_TIME]: [Activity Title]
* **Location:** [inferred from visuals]
* **Activity:** [brief description]
* **Source Reliability:** [High/Medium/Low]
* **Participants:**
  * **Speaker_01:** [name if known, else "Speaker_01"]
* **Transcript Summary:** [concise summary]
* **Action Items:**
  * [ ] [item description]

Audio Transcript:
[Speaker_01] (09:00-09:05): [transcript]
[Speaker_02] (09:05-09:10): [transcript]

Visual Context: [description of keyframes]
```

**Testing:**
- Test with sample synchronized contexts
- Verify Markdown format compliance
- Test with edge cases (no audio, no video, single speaker)

**Dependencies:**
- `openai` (for GPT-4 Vision) or `anthropic` (for Claude)
- `python-dotenv` (for API key management)
- `markdown` (for validation)

**Configuration:**
- Store API keys in `.env` file
- Add model selection to `config/settings.py`

---

### Phase 6: Main Pipeline & Local Testing (Day 6-7)

#### Main Pipeline (`src/main.py`)
**Implementation Steps:**
1. Create orchestration function that runs all features in sequence:
   ```python
   def process_video(video_path: str, output_path: str) -> DailySummary:
       # 1. Media ingestion
       # 2. Diarization
       # 3. ASR
       # 4. Scene detection
       # 5. Synchronization
       # 6. Summarization
       # 7. Save Markdown
   ```
2. Add CLI interface using `argparse` or `click`
3. Add progress logging with progress bars (use `tqdm` for visual feedback)
4. Add error handling and recovery
5. Implement temporary file cleanup
6. Add verbose mode for debugging

**CLI Usage:**
```bash
# Basic usage
python src/main.py --input ~/Videos/meeting.mp4 --output summary.md

# With verbose logging
python src/main.py --input ~/Videos/meeting.mp4 --output summary.md --verbose

# Specify output directory
python src/main.py --input ~/Videos/meeting.mp4 --output-dir ./output
```

#### Feature 7: Local Development Environment & Testing
**Focus:** Ensure the pipeline works reliably on local Mac environment

**Implementation Steps:**
1. **Local File System Setup:**
   - Create `temp/` directory for intermediate files (audio extraction, frame extraction)
   - Create `output/` directory for final summaries
   - Implement automatic cleanup of temporary files
   - Handle Mac-specific path issues (spaces in paths, special characters)

2. **Performance Optimization:**
   - Profile the pipeline to identify bottlenecks
   - Optimize memory usage (important for large videos on Mac)
   - Implement parallel processing where possible (e.g., scene detection while ASR runs)
   - Cache model downloads locally (avoid re-downloading diarization/ASR models)

3. **Mac-Specific Considerations:**
   - Handle Mac file permissions correctly
   - Use absolute paths when needed (Mac path resolution)
   - Test with various video formats common on Mac (MOV, MP4 from iPhone/Mac)
   - Handle case-insensitive filesystem (if needed)
   - Test with videos containing special characters in filenames

4. **Error Handling:**
   - Graceful handling of interrupted processing (Ctrl+C)
   - Resume capability (save intermediate results)
   - Clear error messages for common Mac issues (missing FFmpeg, permission errors)

5. **Documentation:**
   - Create `LOCAL_SETUP.md` with Mac-specific setup instructions
   - Document known issues and workarounds
   - Include troubleshooting guide

**Code Structure for Cloud-Ready (Future Stage 3):**
Even though we're developing locally, structure code to be cloud-ready:
- Use environment variables for all configuration
- Avoid hardcoded paths (use `pathlib` for cross-platform compatibility)
- Make functions stateless (no global state)
- Use relative paths with configurable base directories
- Implement proper logging that can be redirected to cloud logging services

**Testing:**
- Test with various video formats (MP4, MOV, AVI, MKV)
- Test with videos of different lengths (short clips, 1-hour videos)
- Test with videos from different sources (iPhone, Mac screen recording, webcam)
- Verify temporary file cleanup
- Test error recovery (corrupted files, missing dependencies)

**Dependencies:**
- `tqdm` (for progress bars)
- `pathlib` (for cross-platform path handling)

---

## Dependencies Summary

Create `requirements.txt`:

```txt
# Core dependencies
python-dotenv>=1.0.0
pydantic>=2.0.0  # For data models validation

# Media processing
ffmpeg-python>=0.2.0
moviepy>=1.0.3
opencv-python>=4.8.0
scenedetect>=0.6.2

# Audio processing
pyannote.audio>=3.1.0
torch>=2.0.0
librosa>=0.10.0
openai-whisper>=20231117

# LLM APIs
openai>=1.0.0  # or anthropic>=0.7.0

# Utilities
numpy>=1.24.0
Pillow>=10.0.0
click>=8.1.0  # For CLI
tqdm>=4.66.0  # For progress bars
pathlib2>=2.3.7; python_version < '3.4'  # For older Python (not needed for 3.10+)

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
```

---

## Testing Strategy

### Unit Tests
Each feature should have corresponding unit tests in `tests/unit/`:
- Mock external dependencies (APIs, file I/O)
- Use generated test fixtures
- Test edge cases and error handling

### Integration Tests
- Test full pipeline with sample video
- Verify output Markdown format
- Test with various video types (meeting, vlog, body-cam)

### Test Data Generation
Create scripts to generate test fixtures:
- `tests/fixtures/generate_test_audio.py` - Create multi-speaker audio
- `tests/fixtures/generate_test_video.py` - Create video with known scene changes

---

## Configuration Management

Create `config/settings.py`:

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    openai_api_key: Optional[str] = None
    huggingface_token: Optional[str] = None
    
    # Model Selection
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    asr_model: str = "base"  # whisper model size
    llm_model: str = "gpt-4-vision-preview"
    
    # Processing Parameters
    scene_detection_threshold: float = 0.3
    chunk_size_seconds: int = 300  # 5 minutes
    
    # Paths (Mac-friendly, uses home directory expansion)
    output_dir: str = "~/LifeStream/output"  # Will be expanded to absolute path
    temp_dir: str = "~/LifeStream/temp"      # Will be expanded to absolute path
    
    # Mac-specific settings
    cleanup_temp_files: bool = True  # Auto-cleanup temporary files
    max_temp_file_age_hours: int = 24  # Cleanup files older than this
    
    class Config:
        env_file = ".env"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Expand user paths on Mac
        from pathlib import Path
        self.output_dir = str(Path(self.output_dir).expanduser())
        self.temp_dir = str(Path(self.temp_dir).expanduser())
        # Create directories if they don't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
```

---

## Future-Proofing Considerations

### For Stage 2 (RAG):
1. **Data Serialization:** All data models should be JSON-serializable
2. **Chunking Strategy:** Use same 5-minute chunks for RAG indexing
3. **Metadata Preservation:** Store speaker IDs, timestamps, and source reliability
4. **Speaker Registry:** Design data model to support Feature 10 (Speaker Registry)

### For Stage 3 (Cloud Deployment):
1. **Stateless Functions:** All processing functions should be pure (no global state)
2. **Environment Variables:** All configuration via env vars
3. **Error Handling:** Robust error handling for cloud retries
4. **Logging:** Structured logging for cloud monitoring
5. **API-Ready:** Structure code to be easily wrapped in API endpoints

---

## Success Criteria Checklist

- [ ] **Feature 1:** Successfully extracts audio and video from multiple formats
- [ ] **Feature 2:** Achieves >90% speaker diarization accuracy on 3-speaker test
- [ ] **Feature 3:** Produces accurate transcripts with correct timestamps
- [ ] **Feature 4:** Detects scene changes with reasonable accuracy
- [ ] **Feature 5:** Correctly synchronizes audio and video contexts
- [ ] **Feature 6:** Generates Markdown output matching required format
- [ ] **Feature 7:** Local development environment fully functional on Mac
- [ ] **Integration:** Full pipeline processes 1-hour video end-to-end
- [ ] **Output Quality:** Generated summary is coherent and structured

---

## Risk Mitigation

1. **API Rate Limits:** Implement retry logic and rate limiting for LLM APIs
2. **Large Files:** Implement streaming/chunking for large videos (important on Mac with limited storage)
3. **Model Download:** Cache diarization/ASR models locally (saves bandwidth and time)
4. **Cost Management:** Monitor API usage, consider local models for ASR (Whisper runs locally)
5. **Format Compatibility:** Test with various video formats early (especially Mac-native MOV files)
6. **Memory Management:** Mac memory constraints - implement chunking for large videos
7. **Disk Space:** Monitor temp directory size, implement automatic cleanup
8. **FFmpeg Issues:** Provide clear error messages if FFmpeg is missing or incorrectly installed

---

## Next Steps After Stage 1

1. **Speaker Registry (Feature 10):** Design JSON/YAML schema for speaker mapping
2. **RAG Preparation:** Ensure all outputs are in a format suitable for vectorization
3. **API Design:** Start thinking about REST endpoint structure for Stage 3

---

## Mac-Specific Setup Instructions

### Prerequisites Installation

1. **Install Homebrew** (if not already installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install FFmpeg**:
   ```bash
   brew install ffmpeg
   ```

3. **Verify FFmpeg**:
   ```bash
   ffmpeg -version
   ```

4. **Install Python 3.10+** (if not already installed):
   ```bash
   brew install python@3.11
   ```

5. **Set up Python Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Mac-Specific Troubleshooting

**Issue: FFmpeg not found**
- Solution: Ensure FFmpeg is in PATH: `export PATH="/opt/homebrew/bin:$PATH"` (add to `~/.zshrc`)

**Issue: Permission denied errors**
- Solution: Ensure temp and output directories have write permissions: `chmod -R 755 temp output`

**Issue: Model download fails**
- Solution: Check internet connection and HuggingFace token. Models are cached in `~/.cache/`

**Issue: Out of memory errors**
- Solution: Process videos in smaller chunks, or use smaller Whisper model (tiny/base instead of large)

**Issue: Slow processing**
- Solution: Use smaller models for local testing, or enable GPU acceleration if available (M1/M2 Macs)

### Performance Tips for Mac

1. **Use Apple Silicon Optimizations:**
   - PyTorch has M1/M2 optimizations - ensure you install the correct version
   - Whisper can use Metal Performance Shaders on Apple Silicon

2. **Monitor Resources:**
   - Use Activity Monitor to watch CPU/Memory usage
   - Large videos may require significant RAM

3. **Storage Management:**
   - Temp files can be large - ensure sufficient disk space
   - Enable automatic cleanup in settings

## Resources & References

- [pyannote.audio Documentation](https://github.com/pyannote/pyannote-audio)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [PySceneDetect](https://www.scenedetect.com/)
- [FFmpeg Python](https://github.com/kkroening/ffmpeg-python)
- [Homebrew](https://brew.sh/)
- [Python on Mac](https://docs.python.org/3/using/mac.html)

---

**Document Version:** 1.1  
**Last Updated:** 2026-01-09  
**Development Environment:** Local Mac Development
