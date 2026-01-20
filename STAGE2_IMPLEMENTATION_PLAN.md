## Stage 2 Implementation Plan – Memory, Search & Intelligence

**Document version:** 1.0  
**Author:** AI assistant (based on LifeStream spec)  
**Scope:** Detailed, implementation-ready plan for Stage 2 of LifeStream: Memory, Search & Intelligence, building on the existing Stage 1 “Video → Markdown” pipeline.

---

## 1. Goals & High-Level Design

- **Objective:** Transform the Stage 1 “Daily Summary” pipeline into a queryable “Memory” system via a Retrieval-Augmented Generation (RAG) architecture.  
- **Inputs:**  
  - `DailySummary` objects and/or structured transcript/context produced in Stage 1.  
  - Speaker IDs (e.g., `Speaker_01`) and associated time-aligned text plus metadata.  
- **Outputs:**  
  - A persistent **vector index** of semantically meaningful “chunks” (time-bound pieces of the diary).  
  - A **semantic search API** that returns the most relevant chunks for a natural-language query.  
  - A **persistent speaker registry** that maps `Speaker_ID` → human-readable names and roles.

**Core design decisions:**

- **Embedding model:**  
  - Use **OpenAI embeddings** as the primary vectorization method.  
  - Default model: **`text-embedding-3-small`** (fast, cost-effective, high quality).  
  - Configurable via `Settings.embedding_model_name` and `EMBEDDING_MODEL_NAME` in `.env`.

- **Vector store / database:**  
  - Use a **local FAISS index** for efficient similarity search in Stage 2.  
  - Wrap FAISS in a small abstraction layer so it can be swapped for a managed vector DB (e.g., Pinecone, Weaviate) in Stage 3.  
  - Persist vectors + metadata on disk under a `memory_index/` directory in the project root.

- **Metadata store:**  
  - Store per-chunk metadata in a **JSONL file** (one JSON object per line) alongside the FAISS index.  
  - Each metadata record is keyed by a `chunk_id` that is also stored in the FAISS index.

- **Speaker registry:**  
  - Store speaker mappings in a **JSON file** under `config/speakers.json`.  
  - Simple key-value mapping from `Speaker_ID` to `{ name, role, notes }`.

---

## 2. Sub-Stage 2.1 – Chunking & Speaker Registry (Foundations)

### 2.1.1. Chunking Design

**Goal:** Convert `DailySummary` + transcript data into semantically meaningful “chunks” suitable for indexing and retrieval.

**New module:** `src/memory/chunking.py`

**Data model (conceptual):**

- `Chunk` (Pydantic model, stored in code only; serialized as metadata for the index):
  - `chunk_id: str` – deterministic ID (e.g., hash of `(video_id, start_time, end_time, source_type)`).
  - `video_id: str` – stable identifier for a specific video (could be a hash of the file path or `date + source path`).
  - `date: str` – ISO date string (e.g., `"2026-01-08"`).
  - `start_time: float` – seconds from video start.
  - `end_time: float` – seconds from video start.
  - `speakers: list[str]` – speaker IDs present (`["Speaker_01", "Speaker_02"]`).
  - `source_type: str` – e.g., `"transcript_block"`, `"summary_block"`, `"action_item"`, `"scene"`.
  - `text: str` – primary text content used for embeddings (concise but information-dense).
  - `metadata: dict` – arbitrary metadata, e.g., `{"location": "...", "activity": "...", "confidence": "...", "meeting_or_vlog": "meeting"}`.

**Chunking policy:**

- Input: `DailySummary` produced by Stage 1 (with time blocks, transcripts, summaries, action items, etc.).
- Strategy:
  - For each `time_block`:
    - Build a base text representation concatenating:
      - Block-level title/time, main activity, and any summary text.
      - Optionally, selected transcript excerpts (e.g., important utterances or action items).
    - If a `time_block` is:
      - Short (e.g., <= 5–7 minutes of transcript): create a single chunk.
      - Long: split into multiple chunks based on time windows (e.g., 5–10 minute segments) or token length (e.g., max ~512 tokens).
  - Create dedicated chunks for **action items** and other high-value content with `source_type="action_item"` and shorter focused `text`.

**Key functions:**

- `def make_chunks_from_daily_summary(summary: DailySummary) -> list[Chunk]:`
  - Implements the policy above.
  - Generates deterministic `chunk_id`s.

### 2.1.2. Speaker Registry Design

**Goal:** Map anonymous `Speaker_ID`s to stable, human-friendly names and roles, and use those in search and summaries.

**New module:** `src/memory/speaker_registry.py`

**Registry file:** `config/speakers.json` (committed as a template; user-customizable).

Example format:

```json
{
  "Speaker_01": { "name": "Alice", "role": "Engineer", "notes": "Primary user" },
  "Speaker_02": { "name": "Bob", "role": "Product Manager", "notes": "" }
}
```

**Interface:**

- `class SpeakerRegistry:`
  - `def __init__(self, path: str | Path): ...`
  - `def get_display_name(self, speaker_id: str) -> str: ...`
  - `def get_info(self, speaker_id: str) -> dict | None: ...`
  - `def update_mapping(self, speaker_id: str, name: str, role: str | None = None, notes: str | None = None) -> None`

**Integration points:**

- Stage 1 summarization:
  - Before generating final Markdown, resolve speaker IDs via `SpeakerRegistry`.
  - Replace `Speaker_01` → `"Alice"` or `"Speaker_01 (Alice)"` depending on UX preference.
- Stage 2 chunking:
  - Write both `speaker_ids` and resolved `speaker_names` into chunk metadata to make search results more interpretable.

### 2.1.3. Tests for Sub-Stage 2.1

**New tests:**

- `tests/unit/test_chunking.py`
  - **Test: basic chunk creation**
    - Given a `DailySummary` with 2 short time blocks:
      - Assert `make_chunks_from_daily_summary` returns at least 2 chunks.
      - `chunk_id` is non-empty and unique.
      - `start_time`/`end_time` match expected time block ranges.
      - `text` contains key phrases from the summary.
  - **Test: long block splitting**
    - Given a single block with a very long text (simulate long transcript).
    - Assert it is split into multiple chunks obeying a configured `max_chars` or `max_tokens`.
  - **Test: metadata propagation**
    - Given a time block with metadata like `location`, `activity`, `meeting_or_vlog`.
    - Assert each chunk’s `metadata` includes these fields.

- `tests/unit/test_speaker_registry.py`
  - **Test: load registry**
    - Use a temporary `speakers.json` file with 2 speakers.
    - Assert `get_display_name("Speaker_01") == "Alice"`.
  - **Test: unknown speaker fallback**
    - Assert unknown ID returns a sensible default (e.g., `"Speaker_99"` or `"Unknown Speaker_99"`).
  - **Test: update mapping**
    - Start with an empty file.
    - Call `update_mapping("Speaker_01", "Alice", "Engineer")`.
    - Recreate registry and assert the mapping is persisted.

---

## 3. Sub-Stage 2.2 – Embeddings & Vector Index

### 3.1. Embedding Model Wrapper

**Goal:** Provide a clean abstraction to convert lists of texts into dense vectors using OpenAI embeddings.

**New module:** `src/memory/embeddings.py`

**Configuration (in `Settings` and `.env`):**

- `embedding_model_name: str = "text-embedding-3-small"`
- `embedding_batch_size: int = 64`
- `embedding_max_retries: int = 3`

**Interface:**

- `class EmbeddingModel(Protocol):`
  - `def embed_texts(self, texts: list[str]) -> "np.ndarray": ...`

- Concrete implementation:
  - `class OpenAIEmbeddingModel(EmbeddingModel):`
    - Uses the official `openai` Python client (already included in Stage 1).
    - Batches requests according to `embedding_batch_size`.
    - Implements simple exponential backoff for transient API errors.

**Behavior:**

- For `n` input texts:
  - Split into batches of size `embedding_batch_size`.
  - For each batch, call `client.embeddings.create(model=settings.embedding_model_name, input=batch_texts)`.
  - Concatenate result into a 2D `numpy` array `[n, dim]`.

### 3.2. Vector Store (FAISS + JSONL)

**Goal:** Efficient similarity search over chunk embeddings, persisted on disk, with filterable metadata.

**New module:** `src/memory/vector_store.py`

**Backend choice:**  
- **FAISS** (Facebook AI Similarity Search) for local dense vector search:
  - Good performance and well supported.
  - Add `faiss-cpu` to `requirements.txt` (or a similar package name appropriate for the environment).

**On-disk layout (per index namespace, e.g., `default`):**

- `memory_index/`
  - `default.faiss` – FAISS index file.
  - `default_metadata.jsonl` – metadata records, each line:
    - `{ "id": "<chunk_id>", "video_id": "...", "date": "...", "start_time": ..., "end_time": ..., "speakers": [...], "source_type": "...", "extra": {...} }`

**Interface:**

- `class ScoredResult(BaseModel):`
  - `id: str`
  - `score: float`
  - `metadata: dict`

- `class VectorStore(Protocol):`
  - `def upsert(self, vectors: "np.ndarray", metadatas: list[dict], ids: list[str]) -> None`
  - `def query(self, vector: "np.ndarray", top_k: int = 5, filters: dict | None = None) -> list[ScoredResult]`
  - `def delete(self, ids: list[str]) -> None`

- `class FaissVectorStore(VectorStore):`
  - Holds a FAISS index and an in-memory list/dict of metadata synchronized with `default_metadata.jsonl`.
  - Supports simple filter-by-metadata logic (e.g., `date`, `video_id`, `speaker_ids`).

### 3.3. Index Builder

**New module:** `src/memory/index_builder.py`

**Core function:**

- `def index_daily_summary(summary: DailySummary, store: VectorStore, embedder: EmbeddingModel) -> None:`
  - `chunks = make_chunks_from_daily_summary(summary)`
  - `texts = [c.text for c in chunks]`
  - `vectors = embedder.embed_texts(texts)`
  - `metadatas = [c.to_metadata_dict() for c in chunks]`
  - `ids = [c.chunk_id for c in chunks]`
  - `store.upsert(vectors, metadatas, ids)`

**Tests for Sub-Stage 2.2**

- `tests/unit/test_embeddings.py`
  - **Test: basic embedding**
    - Mock OpenAI client to return deterministic vectors.
    - Assert shape `[n, dim]` and correct model name is used.
  - **Test: batching**
    - With `embedding_batch_size=2`, pass 5 texts.
    - Assert underlying client is called 3 times (2+2+1).
  - **Test: retry**
    - First call raises a transient exception, second succeeds.
    - Assert function returns correct result and logs a warning.

- `tests/unit/test_vector_store.py`
  - Use an in-memory FAISS index or a small stub implementation that mimics FAISS behavior.
  - **Test: upsert & query**
    - Insert obvious 1D or 2D vectors and query near them.
    - Assert the closest IDs are returned in correct order.
  - **Test: filters**
    - Insert vectors with varying `date` and `video_id` metadata.
    - Query with filters, assert only matching items are returned.
  - **Test: delete**
    - Insert multiple entries, delete one ID, query again, and ensure it is absent.

- `tests/unit/test_index_builder.py`
  - **Test: indexing pipeline**
    - Use a synthetic `DailySummary` fixture.
    - Mock `EmbeddingModel` and `VectorStore` (track calls).
    - Ensure:
      - `upsert` is called exactly once.
      - Number of vectors equals number of chunks.
      - Metadata contains `video_id`, `date`, `start_time`, `end_time`.

---

## 4. Sub-Stage 2.3 – Semantic Search API

### 4.1. Search Module & API Design

**New module:** `src/search/semantic_search.py`

**Data models:**

- `class SearchQuery(BaseModel):`
  - `query: str`
  - `top_k: int = 5`
  - `min_score: float | None = None`
  - Optional filters:
    - `date: str | None`
    - `video_id: str | None`
    - `speaker_ids: list[str] | None`
    - `source_types: list[str] | None`

- `class SearchResult(BaseModel):`
  - `chunk_id: str`
  - `score: float`
  - `text: str`
  - `video_id: str`
  - `date: str`
  - `start_time: float`
  - `end_time: float`
  - `speakers: list[str]`
  - `metadata: dict`

**Core function:**

- `def semantic_search(query: SearchQuery, store: VectorStore, embedder: EmbeddingModel) -> list[SearchResult]:`
  - Embed `query.query`.
  - Build filter dict from query’s filter fields.
  - Call `store.query(...)`.
  - Wrap results in `SearchResult`.
  - Apply `min_score` threshold if provided.

### 4.2. (Optional) CLI Interface for Search

**Optional new module:** `src/search/cli.py`

- Basic usage:
  - `python -m src.search.cli --query "What did we discuss about the frontend last week?" --top-k 5`
  - Flags for filters like `--date 2026-01-08`, `--speaker Alice`.

### 4.3. Tests for Sub-Stage 2.3

- `tests/unit/test_semantic_search.py`
  - Use in-memory `VectorStore` and mocked `EmbeddingModel`.
  - **Test: simple retrieval**
    - Insert 3 chunks whose text clearly differs (frontend, latency, lunch).
    - Mock embeddings so that queries about “frontend” are close to the “frontend” chunk.
    - Assert top result text matches expected chunk.
  - **Test: filter by date/video**
    - Populate metadata with multiple dates and video_ids.
    - Query with filters; assert only matching metadata is returned.
  - **Test: min_score threshold**
    - Ensure low-similarity results are dropped when `min_score` is set.

- `tests/integration/test_semantic_search_integration.py`
  - Use:
    - Real chunking logic.
    - Mock embedding model (but preserve semantics).
    - Real `VectorStore` implementation.
  - **Test: question over indexed summary**
    - Build a `DailySummary` where only one chunk references “frontend architecture”.
    - Index it.
    - Query: “What did we discuss about the frontend?”.
    - Assert that chunk is the top result and includes correct timestamps and speakers.

---

## 5. Sub-Stage 2.4 – End-to-End RAG & Quality Validation

### 5.1. RAG Pipeline Overview

**Goal:** Validate Stage 2 as a cohesive system, ensuring that natural-language questions over historical videos yield correct and useful results.

**End-to-end flow:**

1. **Stage 1**: Ingest raw video → produce `DailySummary` + transcripts.
2. **Stage 2 indexing**:
   - `index_daily_summary` converts `DailySummary` → chunks → embeddings → vector index.
3. **Stage 2 query**:
   - User asks a question.
   - `semantic_search` retrieves top-k relevant chunks.
4. **(Optional) Stage 2+ summarization for answers**:
   - Use an LLM (e.g., GPT-4o) to synthesize a final natural-language answer using retrieved chunks as context (this can be implemented now or in Stage 3).

### 5.2. End-to-End Integration Tests

- `tests/integration/test_rag_pipeline.py`

**Scenario 1 – Meeting-focused query (from project spec):**

- Build a `DailySummary` fixture representing an engineering sync meeting, containing:
  - A chunk where `Speaker_01` proposes a new frontend architecture.
  - A chunk about backend latency.
  - A chunk about lunch.
- Index the summary (using mocked embeddings for determinism).
- Run query: `"What did we discuss about the frontend last week?"`.
- Assertions:
  - At least one result is returned.
  - Top result text clearly references the frontend architecture discussion.
  - `start_time`/`end_time` map to the correct time block in the meeting.
  - Speakers resolved via `SpeakerRegistry` appear correctly (e.g., `Alice` instead of `Speaker_01`).

**Scenario 2 – Speaker-focused query (leveraging registry):**

- Registry maps `Speaker_02` to `Bob`.
- Build a summary where `Speaker_02` talks about “deployment timeline”.
- Index data.
- Query: `"What did Bob say about deployment?"`.
- Assertions:
  - At least one result returned.
  - Retrieved text mentions deployment and matches the correct speaker and time.

**Scenario 3 – Vlog context vs. meeting context:**

- Summary containing:
  - A meeting block with high reliability and many speakers.
  - A vlog block annotated as `meeting_or_vlog="vlog"` in metadata.
- Index with `source_type` and `meeting_or_vlog`.
- Query: `"What happened during my commute?"`.
- Assertions:
  - Top result is drawn from blocks labeled or described as commute/vlog.
  - Meeting blocks should rank lower or be filtered out where appropriate.

---

## 6. Milestones & Implementation Order

**Milestone 1 – Foundations (Sub-Stage 2.1)**

- Implement:
  - `src/memory/chunking.py`
  - `src/memory/speaker_registry.py`
- Add and pass:
  - `tests/unit/test_chunking.py`
  - `tests/unit/test_speaker_registry.py`

**Milestone 2 – Embeddings & Index (Sub-Stage 2.2)**

- Implement:
  - `src/memory/embeddings.py`
  - `src/memory/vector_store.py`
  - `src/memory/index_builder.py`
- Update `requirements.txt` to include FAISS.
- Add and pass:
  - `tests/unit/test_embeddings.py`
  - `tests/unit/test_vector_store.py`
  - `tests/unit/test_index_builder.py`

**Milestone 3 – Semantic Search API (Sub-Stage 2.3)**

- Implement:
  - `src/search/semantic_search.py`
  - (Optional) `src/search/cli.py`
- Add and pass:
  - `tests/unit/test_semantic_search.py`
  - `tests/integration/test_semantic_search_integration.py`

**Milestone 4 – End-to-End RAG Validation (Sub-Stage 2.4)**

- Implement:
  - Full RAG integration scenarios.
- Add and pass:
  - `tests/integration/test_rag_pipeline.py`

---

## 7. Notes & Future Extensions

- In Stage 3 (Cloud deployment), the FAISS-backed local vector store can be wrapped behind a service layer or replaced with a managed vector database. The abstraction in `VectorStore` is designed to make this swap minimal.
- Additional Stage 2+ enhancements:
  - Use LLM re-ranking of retrieved chunks for better answer quality.
  - Add topic/tags classification (e.g., “frontend”, “infra”, “personal”) during indexing for more powerful filtering.
  - Add a question-answering API that directly returns an LLM-generated answer plus references to the underlying chunks.

