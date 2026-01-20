"""Unit tests for SpeakerRegistry."""

from pathlib import Path
import json

from src.memory.speaker_registry import SpeakerRegistry


def test_load_empty_registry(tmp_path):
    """Registry should handle missing file gracefully."""
    registry_path = tmp_path / "speakers.json"
    registry = SpeakerRegistry(path=registry_path)

    assert registry.get_info("Speaker_01") is None
    assert registry.get_display_name("Speaker_01") == "Speaker_01"
    assert registry.all_speakers() == {}


def test_update_and_persist_mapping(tmp_path):
    """Updating a mapping should persist it to disk."""
    registry_path = tmp_path / "speakers.json"
    registry = SpeakerRegistry(path=registry_path)

    registry.update_mapping("Speaker_01", "Alice", role="Engineer")

    # New instance should see the saved data
    registry2 = SpeakerRegistry(path=registry_path)
    info = registry2.get_info("Speaker_01")

    assert info is not None
    assert info.get("name") == "Alice"
    assert info.get("role") == "Engineer"
    assert registry2.get_display_name("Speaker_01") == "Alice"


def test_unknown_speaker_fallback(tmp_path):
    """Unknown speakers should fall back to their ID."""
    registry_path = tmp_path / "speakers.json"
    registry = SpeakerRegistry(path=registry_path)

    assert registry.get_display_name("Speaker_99") == "Speaker_99"


def test_handles_corrupted_json_gracefully(tmp_path):
    """Registry should not crash when the JSON file is corrupted."""
    registry_path = tmp_path / "speakers.json"
    # Write invalid JSON
    registry_path.write_text("{not valid json", encoding="utf-8")

    registry = SpeakerRegistry(path=registry_path)

    # Should behave like an empty registry
    assert registry.all_speakers() == {}
    assert registry.get_display_name("Speaker_01") == "Speaker_01"


