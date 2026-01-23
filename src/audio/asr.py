"""Automatic Speech Recognition (ASR) module.

This module handles speech-to-text transcription using OpenAI Whisper.
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path

from src.models.data_models import AudioSegment
from config.settings import Settings

logger = logging.getLogger(__name__)


class ASRProcessor:
    """Handles automatic speech recognition using Whisper."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize ASRProcessor.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the Whisper ASR model."""
        try:
            import whisper
            import os
            
            # Set Whisper cache directory to /tmp for Lambda (read-only filesystem)
            # Whisper downloads models to ~/.cache/whisper by default, which fails in Lambda
            whisper_cache_dir = os.environ.get("WHISPER_CACHE_DIR", "/tmp/whisper_cache")
            os.makedirs(whisper_cache_dir, exist_ok=True)
            os.environ["WHISPER_CACHE_DIR"] = whisper_cache_dir
            
            logger.info(f"Loading Whisper model: {self.settings.asr_model} (cache: {whisper_cache_dir})")
            
            # Load Whisper model
            self.model = whisper.load_model(self.settings.asr_model, download_root=whisper_cache_dir)
            
            logger.info(f"Whisper model '{self.settings.asr_model}' loaded successfully")
            self._model_available = True
            
        except ImportError:
            logger.warning(
                "Whisper not installed. ASR will be skipped. Install with: pip install openai-whisper"
            )
            self.model = None
            self._model_available = False
        except Exception as e:
            logger.warning(f"Failed to load Whisper model: {e}. ASR will be skipped.")
            self.model = None
            self._model_available = False
    
    def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> List[Dict]:
        """Transcribe audio file with timestamps.
        
        Args:
            audio_path: Path to the audio file.
            language: Language code (e.g., 'en', 'es'). If None, auto-detect.
            
        Returns:
            List of dictionaries with 'start', 'end', 'text' keys.
            
        Raises:
            ValueError: If audio file cannot be processed.
        """
        if not getattr(self, '_model_available', True) or self.model is None:
            logger.warning("Whisper model not available - skipping transcription")
            return []
            
        if not Path(audio_path).exists():
            raise ValueError(f"Audio file does not exist: {audio_path}")
        
        try:
            import whisper
            
            logger.info(f"Transcribing audio: {audio_path}")
            
            # Transcribe with word-level timestamps
            result = self.model.transcribe(
                audio_path,
                language=language,
                word_timestamps=True,
                verbose=False
            )
            
            # Extract segments with timestamps
            segments = []
            for segment in result.get("segments", []):
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "words": segment.get("words", [])
                })
            
            logger.info(f"Transcription complete: {len(segments)} segments")
            
            return segments
            
        except Exception as e:
            logger.warning(f"Transcription failed: {e}. ASR will be skipped.")
            return []  # Return empty list instead of raising
    
    def merge_asr_diarization(
        self,
        asr_output: List[Dict],
        diarization_output: List[AudioSegment]
    ) -> List[AudioSegment]:
        """Merge ASR transcription with diarization speaker labels.
        
        This function aligns ASR segments with diarization segments to create
        AudioSegment objects with both transcript text and speaker IDs.
        If diarization is empty, creates AudioSegment objects from ASR only.
        
        Args:
            asr_output: List of ASR segments with 'start', 'end', 'text' keys.
            diarization_output: List of AudioSegment objects with speaker IDs.
            
        Returns:
            List of AudioSegment objects with transcript_text populated.
        """
        if not asr_output:
            logger.warning("Empty ASR output")
            return diarization_output.copy() if diarization_output else []
        
        # If no diarization, create AudioSegment objects from ASR only
        if not diarization_output:
            logger.info("No diarization available - creating segments from ASR only")
            from src.models.data_models import AudioSegment
            segments = []
            for asr_seg in asr_output:
                segments.append(AudioSegment(
                    start_time=asr_seg["start"],
                    end_time=asr_seg["end"],
                    transcript_text=asr_seg["text"],
                    speaker_id="unknown"  # No speaker ID available
                ))
            return segments
        
        # Create a mapping of time ranges to speaker IDs
        speaker_map = {}
        for diar_seg in diarization_output:
            # Use start time as key (rounded to nearest 0.1s for matching)
            key = round(diar_seg.start_time, 1)
            speaker_map[key] = diar_seg.speaker_id
        
        # Merge ASR segments with speaker labels
        merged_segments = []
        
        for asr_seg in asr_output:
            asr_start = asr_seg["start"]
            asr_end = asr_seg["end"]
            asr_text = asr_seg["text"]
            
            # Find the speaker for this time range
            # Look for diarization segment that overlaps with ASR segment
            speaker_id = None
            for diar_seg in diarization_output:
                # Check for overlap
                if (asr_start < diar_seg.end_time and asr_end > diar_seg.start_time):
                    # Calculate overlap percentage
                    overlap_start = max(asr_start, diar_seg.start_time)
                    overlap_end = min(asr_end, diar_seg.end_time)
                    overlap_duration = overlap_end - overlap_start
                    asr_duration = asr_end - asr_start
                    
                    # If significant overlap (>50%), assign speaker
                    if overlap_duration > 0.5 * asr_duration:
                        speaker_id = diar_seg.speaker_id
                        break
            
            # If no speaker found, try to find closest speaker
            if speaker_id is None:
                # Find the diarization segment with closest start time
                closest_seg = min(
                    diarization_output,
                    key=lambda s: abs(s.start_time - asr_start)
                )
                if abs(closest_seg.start_time - asr_start) < 2.0:  # Within 2 seconds
                    speaker_id = closest_seg.speaker_id
            
            # Default to "Speaker_Unknown" if still no match
            if speaker_id is None:
                speaker_id = "Speaker_Unknown"
                logger.warning(
                    f"Could not assign speaker for ASR segment "
                    f"({asr_start:.2f}s - {asr_end:.2f}s)"
                )
            
            # Create merged segment
            merged_segment = AudioSegment(
                start_time=round(asr_start, 3),
                end_time=round(asr_end, 3),
                speaker_id=speaker_id,
                transcript_text=asr_text,
                confidence=None
            )
            merged_segments.append(merged_segment)
        
        logger.info(f"Merged {len(merged_segments)} segments with speaker labels")
        
        return merged_segments
    
    def process_audio_with_diarization(
        self,
        audio_path: str,
        diarization_segments: List[AudioSegment],
        language: Optional[str] = None
    ) -> List[AudioSegment]:
        """Complete ASR processing with diarization labels.
        
        Convenience method that transcribes audio and merges with diarization.
        
        Args:
            audio_path: Path to the audio file.
            diarization_segments: List of AudioSegment objects from diarization.
            language: Language code. If None, auto-detect.
            
        Returns:
            List of AudioSegment objects with both speaker IDs and transcripts.
        """
        # Transcribe audio
        asr_output = self.transcribe_audio(audio_path, language)
        
        # Merge with diarization
        merged_segments = self.merge_asr_diarization(asr_output, diarization_segments)
        
        return merged_segments
