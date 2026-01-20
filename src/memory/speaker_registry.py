"""Speaker registry for mapping internal speaker IDs to human-friendly names.

This module provides a small persistence layer over a JSON file that stores
speaker metadata such as display name, role, and optional notes. It is used
by both Stage 1 (for prettier Markdown output) and Stage 2 (for more
interpretable search results).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Any

from config.settings import Settings


class SpeakerRegistry:
    """Persistent registry mapping speaker IDs to metadata.

    The underlying storage is a JSON file with the following shape:

    {
        "Speaker_01": {"name": "Alice", "role": "Engineer", "notes": "Primary user"},
        "Speaker_02": {"name": "Bob", "role": "PM", "notes": ""}
    }
    """

    def __init__(self, path: Optional[str | Path] = None, settings: Optional[Settings] = None) -> None:
        """Create a new SpeakerRegistry instance.

        Args:
            path: Optional explicit path to the registry JSON file. If not
                provided, the value from Settings (speaker_registry_path) is
                used, falling back to ``config/speakers.json`` in the project
                root.
            settings: Optional Settings instance (used to resolve default
                registry path). If not provided, a default Settings object is
                constructed.
        """
        self._settings = settings or Settings()

        if path is not None:
            self._path = Path(path).expanduser()
        else:
            # Default to settings value if present, otherwise config/speakers.json
            default_path = getattr(self._settings, "speaker_registry_path", "config/speakers.json")
            self._path = Path(default_path).expanduser()

        # Ensure parent directory exists but do not create the file yet
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    @property
    def path(self) -> Path:
        """Return the underlying JSON file path."""
        return self._path

    def _load(self) -> None:
        """Load registry data from disk, if present."""
        if not self._path.exists():
            self._data = {}
            return

        try:
            with self._path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    # Only keep string keys mapping to dict-like metadata
                    self._data = {
                        str(k): (v if isinstance(v, dict) else {})
                        for k, v in raw.items()
                    }
                else:
                    self._data = {}
        except Exception:
            # On any error, fall back to empty mapping to avoid hard failures.
            self._data = {}

    def _save(self) -> None:
        """Persist registry data to disk."""
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)

    # Public API -----------------------------------------------------------------

    def get_info(self, speaker_id: str) -> Optional[Dict[str, Any]]:
        """Return full metadata dict for a speaker ID, if known."""
        return self._data.get(speaker_id)

    def get_display_name(self, speaker_id: str) -> str:
        """Return the preferred display name for a speaker.

        If the registry has an entry with a non-empty ``name`` field, that is
        returned. Otherwise, the original ``speaker_id`` is returned.
        """
        info = self.get_info(speaker_id)
        if not info:
            return speaker_id

        name = info.get("name")
        return name or speaker_id

    def update_mapping(
        self,
        speaker_id: str,
        name: str,
        role: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Create or update a mapping for ``speaker_id``.

        Args:
            speaker_id: Internal ID, e.g. ``"Speaker_01"``.
            name: Human-friendly display name.
            role: Optional role/job description.
            notes: Optional freeform notes.
        """
        meta: Dict[str, Any] = {
            "name": name,
            "role": role or "",
            "notes": notes or "",
        }
        self._data[speaker_id] = meta
        self._save()

    def all_speakers(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of the internal mapping."""
        return dict(self._data)


__all__ = ["SpeakerRegistry"]

