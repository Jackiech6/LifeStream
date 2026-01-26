"""Automatic Speech Recognition (ASR) module.

Uses faster-whisper (CTranslate2) when available for ~4x speedup at same quality;
falls back to OpenAI Whisper otherwise.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from src.models.data_models import AudioSegment
from config.settings import Settings

logger = logging.getLogger(__name__)


def _fw_segments_to_list(segments_iter, word_timestamps: bool) -> List[Dict[str, Any]]:
    """Consume faster-whisper segment generator into [{"start","end","text","words"}]. """
    out: List[Dict[str, Any]] = []
    for s in segments_iter:
        words = []
        if word_timestamps and getattr(s, "words", None):
            for w in s.words:
                words.append({
                    "word": getattr(w, "word", ""),
                    "start": getattr(w, "start", s.start),
                    "end": getattr(w, "end", s.end),
                })
        out.append({
            "start": s.start,
            "end": s.end,
            "text": (s.text or "").strip(),
            "words": words,
        })
    return out


class ASRProcessor:
    """Handles automatic speech recognition using Whisper (faster-whisper or openai-whisper)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._backend: str = "none"
        self._model: Any = None
        self._load_model()

    @property
    def model(self) -> Any:
        """Backward compatibility: exposes _model as model."""
        return self._model

    def _load_model(self) -> None:
        use_fw = getattr(self.settings, "use_faster_whisper", True)
        cache_dir = os.environ.get("WHISPER_CACHE_DIR", "/tmp/whisper_cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["WHISPER_CACHE_DIR"] = cache_dir

        if use_fw:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.settings.asr_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=cache_dir,
                )
                self._backend = "faster_whisper"
                logger.info("Loaded faster-whisper model '%s' (cache=%s)", self.settings.asr_model, cache_dir)
                return
            except Exception as e:
                logger.warning("faster-whisper load failed (%s), falling back to openai-whisper: %s", type(e).__name__, e)

        try:
            import whisper
            self._model = whisper.load_model(
                self.settings.asr_model,
                download_root=cache_dir,
            )
            self._backend = "whisper"
            logger.info("Loaded openai-whisper model '%s' (cache=%s)", self.settings.asr_model, cache_dir)
        except ImportError:
            logger.warning("Whisper not installed. ASR will be skipped. Install openai-whisper or faster-whisper.")
            self._model = None
            self._backend = "none"
        except Exception as e:
            logger.warning("Failed to load Whisper model: %s. ASR will be skipped.", e)
            self._model = None
            self._backend = "none"

    def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Transcribe audio file with timestamps.

        Returns:
            List of dicts with 'start', 'end', 'text', 'words' keys.
        """
        if self._model is None:
            logger.warning("ASR model not available - skipping transcription")
            return []

        if not Path(audio_path).exists():
            raise ValueError(f"Audio file does not exist: {audio_path}")

        try:
            logger.info("Transcribing audio: %s (backend=%s)", audio_path, self._backend)

            if self._backend == "faster_whisper":
                segments_gen, _ = self._model.transcribe(
                    audio_path,
                    language=language,
                    word_timestamps=True,
                    vad_filter=False,
                )
                segments = _fw_segments_to_list(segments_gen, word_timestamps=True)
            else:
                import whisper
                result = self._model.transcribe(
                    audio_path,
                    language=language,
                    word_timestamps=True,
                    verbose=False,
                )
                segments = []
                for seg in result.get("segments", []):
                    segments.append({
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": (seg.get("text") or "").strip(),
                        "words": seg.get("words", []),
                    })

            logger.info("Transcription complete: %d segments", len(segments))
            return segments

        except Exception as e:
            logger.warning("Transcription failed: %s. ASR will be skipped.", e)
            return []

    def merge_asr_diarization(
        self,
        asr_output: List[Dict[str, Any]],
        diarization_output: List[AudioSegment],
    ) -> List[AudioSegment]:
        """Merge ASR transcription with diarization speaker labels."""
        if not asr_output:
            logger.warning("Empty ASR output")
            return list(diarization_output) if diarization_output else []

        if not diarization_output:
            logger.info("No diarization available - creating segments from ASR only")
            return [
                AudioSegment(
                    start_time=seg["start"],
                    end_time=seg["end"],
                    transcript_text=seg["text"],
                    speaker_id="unknown",
                )
                for seg in asr_output
            ]

        merged = []
        for asr_seg in asr_output:
            asr_start = asr_seg["start"]
            asr_end = asr_seg["end"]
            asr_text = asr_seg["text"]
            speaker_id = None
            for d in diarization_output:
                if asr_start < d.end_time and asr_end > d.start_time:
                    overlap_start = max(asr_start, d.start_time)
                    overlap_end = min(asr_end, d.end_time)
                    if (overlap_end - overlap_start) > 0.5 * (asr_end - asr_start):
                        speaker_id = d.speaker_id
                        break
            if speaker_id is None:
                closest = min(diarization_output, key=lambda s: abs(s.start_time - asr_start))
                speaker_id = closest.speaker_id if abs(closest.start_time - asr_start) < 2.0 else "Speaker_Unknown"
            if speaker_id is None:
                speaker_id = "Speaker_Unknown"
            merged.append(
                AudioSegment(
                    start_time=round(asr_start, 3),
                    end_time=round(asr_end, 3),
                    speaker_id=speaker_id,
                    transcript_text=asr_text,
                    confidence=None,
                )
            )

        logger.info("Merged %d segments with speaker labels", len(merged))
        return merged

    def process_audio_with_diarization(
        self,
        audio_path: str,
        diarization_segments: List[AudioSegment],
        language: Optional[str] = None,
    ) -> List[AudioSegment]:
        """Transcribe and merge with diarization labels."""
        asr_output = self.transcribe_audio(audio_path, language)
        return self.merge_asr_diarization(asr_output, diarization_segments)
