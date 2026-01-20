# LifeStream: Tools and Methods Reference

**Concise reference of all tools and methods used in Stage 1 and Stage 2**

---

## Stage 1: Core Processing Engine

### Phase 1: Foundation
- **Pydantic** - Data model validation
- **Python-dotenv** - Environment variable management
- **Pathlib** - File path handling

### Phase 2: Media Processing
**Tool:** FFmpeg (via subprocess)
- `MediaProcessor.split_media_tracks()` - Extract audio/video tracks
- `MediaProcessor.validate_video_format()` - Format validation
- `MediaProcessor.get_video_metadata()` - Extract metadata (ffprobe)
- `MediaProcessor.extract_audio_track()` - Audio extraction (ffmpeg)
- `MediaProcessor.extract_video_frames()` - Frame extraction (ffmpeg)

**Libraries:**
- `subprocess` - FFmpeg command execution
- `ffprobe` - Video metadata extraction

### Phase 3: Audio Processing

**Speaker Diarization:**
- **Tool:** pyannote.audio (HuggingFace)
- **Model:** `pyannote/speaker-diarization-3.1`
- `SpeakerDiarizer.diarize_audio()` - Identify speaker segments
- `librosa.load()` - Audio loading (bypasses torchcodec issues)
- `torch` - Tensor operations

**ASR (Automatic Speech Recognition):**
- **Tool:** OpenAI Whisper
- **Model:** `base` (configurable: tiny, base, small, medium, large)
- `ASRProcessor.transcribe_audio()` - Speech-to-text
- `ASRProcessor.process_audio_with_diarization()` - Merge ASR + diarization

**Libraries:**
- `whisper` - OpenAI Whisper ASR
- `librosa` - Audio preprocessing
- `torch` - PyTorch for model inference

### Phase 4: Video Processing

**Scene Detection:**
- **Tool:** PySceneDetect
- `SceneDetector.detect_scene_changes()` - Detect scene boundaries
- `SceneDetector.extract_keyframes_with_scene_detection()` - Extract keyframes
- `ContentDetector` - Visual change detection algorithm

**Frame Extraction:**
- **Tool:** OpenCV (cv2)
- `cv2.VideoCapture()` - Video file reading
- `cv2.imwrite()` - Frame saving

**Libraries:**
- `scenedetect` - Scene change detection
- `opencv-python` - Video frame extraction

### Phase 5: Integration & Synthesis

**Synchronization:**
- `ContextSynchronizer.synchronize_contexts()` - Align audio/video by timestamps
- `ContextSynchronizer._map_segments_to_context()` - Temporal mapping

**LLM Summarization:**
- **Tool:** OpenAI GPT-4o
- **API:** OpenAI Chat Completions API
- `LLMSummarizer.create_daily_summary()` - Generate structured summary
- `LLMSummarizer.summarize_context()` - Summarize individual contexts
- `LLMSummarizer.format_markdown_output()` - Format final output

**Libraries:**
- `openai` - OpenAI API client

---

## Stage 2: Memory, Search & Intelligence

### Sub-Stage 2.1: Chunking & Speaker Registry

**Chunking:**
- `make_chunks_from_daily_summary()` - Convert DailySummary to chunks
- `_parse_time_to_seconds()` - Time string parsing
- `_collect_speakers()` - Extract speaker IDs
- `_build_summary_text()` - Build summary chunk text
- `_build_transcript_text()` - Build transcript chunk text
- `_deterministic_chunk_id()` - Generate deterministic IDs (SHA256)

**Speaker Registry:**
- `SpeakerRegistry.get_display_name()` - Map Speaker_ID → name
- `SpeakerRegistry.get_info()` - Get speaker metadata
- `SpeakerRegistry.update_mapping()` - Update/persist mappings
- `SpeakerRegistry.all_speakers()` - List all registered speakers

**Libraries:**
- `hashlib` - Deterministic ID generation
- `json` - Speaker registry persistence

### Sub-Stage 2.2: Embeddings & Vector Index

**Embeddings:**
- **Tool:** OpenAI Embeddings API
- **Model:** `text-embedding-3-small` (configurable)
- `OpenAIEmbeddingModel.embed_texts()` - Batch text embedding
- `OpenAIEmbeddingModel._embed_batch()` - Single batch with retry logic

**Vector Store:**
- **Tool:** FAISS (Facebook AI Similarity Search)
- `FaissVectorStore.upsert()` - Insert/update vectors
- `FaissVectorStore.query()` - Similarity search with filters
- `FaissVectorStore.delete()` - Delete by ID
- `FaissVectorStore._load()` - Load index from disk
- `FaissVectorStore._save_index()` - Persist to disk

**Index Builder:**
- `index_daily_summary()` - Orchestrate chunking → embedding → indexing

**Libraries:**
- `faiss-cpu` - Vector similarity search
- `numpy` - Vector operations
- `json` - Metadata persistence (JSONL format)

### Sub-Stage 2.3: Semantic Search API

**Search:**
- `semantic_search()` - Natural language query interface
- `_build_filters()` - Build metadata filters from query
- `SearchQuery` - Query model (query, top_k, filters, min_score)
- `SearchResult` - Result model (chunk_id, score, text, metadata)

**Libraries:**
- `numpy` - Vector operations for query embedding

### Sub-Stage 2.4: End-to-End RAG

**Pipeline Flow:**
1. `DailySummary` (from Stage 1)
2. `make_chunks_from_daily_summary()` → `List[Chunk]`
3. `OpenAIEmbeddingModel.embed_texts()` → `np.ndarray`
4. `FaissVectorStore.upsert()` → Indexed
5. `semantic_search()` → `List[SearchResult]`

---

## External Tools Summary

### Command-Line Tools
- **FFmpeg** - Media processing (audio/video extraction)
- **ffprobe** - Video metadata extraction

### APIs & Services
- **OpenAI API** - GPT-4o for summarization
- **OpenAI Embeddings API** - text-embedding-3-small for vectorization
- **HuggingFace** - pyannote.audio model hosting

### Python Libraries
- **Core:** pydantic, python-dotenv, pathlib
- **Media:** ffmpeg-python, opencv-python, scenedetect
- **Audio:** pyannote.audio, whisper, librosa, torch
- **LLM:** openai
- **Vector:** faiss-cpu, numpy
- **Utils:** Pillow, tqdm, click

---

## Method Call Order (Pipeline)

### Stage 1 Pipeline
```
process_video()
├── MediaProcessor.split_media_tracks()
│   ├── validate_video_format()
│   ├── get_video_metadata() [ffprobe]
│   ├── extract_audio_track() [ffmpeg]
│   └── extract_video_frames() [ffmpeg]
├── SpeakerDiarizer.diarize_audio()
│   └── pyannote.audio Pipeline [librosa + torch]
├── ASRProcessor.process_audio_with_diarization()
│   └── whisper.transcribe() [Whisper model]
├── SceneDetector.extract_keyframes_with_scene_detection()
│   ├── detect_scene_changes() [PySceneDetect]
│   └── extract_frames() [OpenCV]
├── ContextSynchronizer.synchronize_contexts()
└── LLMSummarizer.create_daily_summary()
    ├── summarize_context() [OpenAI GPT-4o]
    └── format_markdown_output()
```

### Stage 2 Pipeline
```
index_daily_summary()
├── make_chunks_from_daily_summary()
│   ├── _parse_time_to_seconds()
│   ├── _collect_speakers()
│   ├── _build_summary_text()
│   ├── _build_transcript_text()
│   └── _deterministic_chunk_id()
├── OpenAIEmbeddingModel.embed_texts()
│   └── OpenAI Embeddings API [text-embedding-3-small]
└── FaissVectorStore.upsert()
    └── FAISS Index + JSONL metadata

semantic_search()
├── OpenAIEmbeddingModel.embed_texts() [query]
├── FaissVectorStore.query()
│   └── FAISS similarity search
└── Filter & format results
```

---

**Last Updated:** 2026-01-20
