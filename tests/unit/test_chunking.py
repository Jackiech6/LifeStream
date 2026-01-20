"""Unit tests for chunking utilities."""

from src.memory.chunking import make_chunks_from_daily_summary, Chunk
from src.models.data_models import DailySummary, TimeBlock, AudioSegment, Participant


def _build_sample_daily_summary() -> DailySummary:
    """Helper to build a small DailySummary fixture."""
    block1 = TimeBlock(
        start_time="09:00",
        end_time="09:10",
        activity="Morning commute",
        location="Car",
        transcript_summary="Driving to work while listening to a podcast.",
        audio_segments=[
            AudioSegment(
                start_time=0.0,
                end_time=60.0,
                speaker_id="Speaker_01",
                transcript_text="Talking about the day's plan.",
            )
        ],
        participants=[Participant(speaker_id="Speaker_01")],
        action_items=[],
    )

    block2 = TimeBlock(
        start_time="10:00",
        end_time="11:00",
        activity="Engineering sync",
        location="Office",
        transcript_summary="Discussed frontend architecture and deployment.",
        audio_segments=[
            AudioSegment(
                start_time=0.0,
                end_time=300.0,
                speaker_id="Speaker_01",
                transcript_text="Proposed new architecture.",
            ),
            AudioSegment(
                start_time=300.0,
                end_time=600.0,
                speaker_id="Speaker_02",
                transcript_text="Asked about latency and rollout.",
            ),
        ],
        participants=[
            Participant(speaker_id="Speaker_01"),
            Participant(speaker_id="Speaker_02"),
        ],
        action_items=[
            "Prepare architecture RFC.",
            "Schedule deployment review meeting.",
        ],
    )

    return DailySummary(
        date="2026-01-10",
        video_source="/path/to/video.mp4",
        time_blocks=[block1, block2],
    )


def test_make_chunks_basic():
    """Basic sanity checks for chunk creation."""
    summary = _build_sample_daily_summary()
    chunks = make_chunks_from_daily_summary(summary, max_chars=1000)

    assert isinstance(chunks, list)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)

    # Ensure chunk IDs are non-empty and unique
    ids = [c.chunk_id for c in chunks]
    assert all(ids)
    assert len(set(ids)) == len(ids)

    # Check that activity text shows up somewhere
    all_text = "\n".join(c.text for c in chunks)
    assert "Morning commute" in all_text
    assert "Engineering sync" in all_text


def test_make_chunks_metadata_and_speakers():
    """Chunks should carry over key metadata and speakers."""
    summary = _build_sample_daily_summary()
    chunks = make_chunks_from_daily_summary(summary, max_chars=1000)

    # Find a chunk related to the engineering sync block
    eng_chunks = [c for c in chunks if "Engineering sync" in c.text]
    assert eng_chunks, "Expected at least one chunk for engineering sync block"

    for c in eng_chunks:
        assert c.video_id == "/path/to/video.mp4"
        assert c.date == "2026-01-10"
        assert "activity" in c.metadata
        assert c.metadata["activity"] == "Engineering sync"

        # Speakers Speaker_01 and Speaker_02 should be reflected
        assert "Speaker_01" in c.speakers or "Speaker_02" in c.speakers


def test_make_chunks_respects_max_chars():
    """Chunks should be truncated when exceeding max_chars."""
    summary = _build_sample_daily_summary()
    # Use a very small max_chars to force truncation
    max_chars = 50
    chunks = make_chunks_from_daily_summary(summary, max_chars=max_chars)

    for c in chunks:
        assert len(c.text) <= max_chars


def test_action_item_chunks_are_created():
    """Each action item should generate a dedicated action_item chunk."""
    summary = _build_sample_daily_summary()
    chunks = make_chunks_from_daily_summary(summary, max_chars=1000)

    action_chunks = [c for c in chunks if c.source_type == "action_item"]
    # From _build_sample_daily_summary, block2 has 2 action items
    assert len(action_chunks) >= 2

    # Ensure text and metadata flags look correct
    for c in action_chunks:
        assert "Action item:" in c.text
        assert c.metadata.get("is_action_item") is True


def test_time_parsing_and_start_end_seconds():
    """Start/end times on blocks should be reflected as seconds in chunks."""
    summary = _build_sample_daily_summary()
    chunks = make_chunks_from_daily_summary(summary, max_chars=1000)

    # Morning commute block is 09:00–09:10 → 32400–33000 seconds since midnight
    commute_chunks = [c for c in chunks if "Morning commute" in c.text]
    assert commute_chunks, "Expected chunks for Morning commute"
    for c in commute_chunks:
        assert c.start_time == 9 * 3600  # 09:00
        assert c.end_time == 9 * 3600 + 10 * 60  # 09:10


