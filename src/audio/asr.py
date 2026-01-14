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
            
            logger.info(f"Loading Whisper model: {self.settings.asr_model}")
            
            # Load Whisper model
            self.model = whisper.load_model(self.settings.asr_model)
            
            logger.info(f"Whisper model '{self.settings.asr_model}' loaded successfully")
            
        except ImportError:
            raise ImportError(
                "Whisper not installed. Install with: pip install openai-whisper"
            )
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Could not load Whisper model: {e}") from e
    
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
            logger.error(f"Transcription failed: {e}")
            raise ValueError(f"Could not transcribe audio: {audio_path}") from e
    
    def merge_asr_diarization(
        self,
        asr_output: List[Dict],
        diarization_output: List[AudioSegment]
    ) -> List[AudioSegment]:
        """Merge ASR transcription with diarization speaker labels.
        
        This function aligns ASR segments with diarization segments to create
        AudioSegment objects with both transcript text and speaker IDs.
        
        Args:
            asr_output: List of ASR segments with 'start', 'end', 'text' keys.
            diarization_output: List of AudioSegment objects with speaker IDs.
            
        Returns:
            List of AudioSegment objects with transcript_text populated.
        """
        if not asr_output or not diarization_output:
            logger.warning("Empty ASR or diarization output")
            return diarization_output.copy() if diarization_output else []
        
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
