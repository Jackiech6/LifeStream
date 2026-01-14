"""Speaker diarization module.

This module handles speaker diarization using pyannote.audio to identify
who spoke when in the audio file.
"""

import logging
from typing import List, Optional
from pathlib import Path

from src.models.data_models import AudioSegment
from config.settings import Settings

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """Handles speaker diarization using pyannote.audio."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize SpeakerDiarizer.
        
        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._check_dependencies()
        self._load_model()
    
    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        try:
            import torch
            from pyannote.audio import Pipeline
            logger.info("Diarization dependencies available")
        except ImportError as e:
            raise ImportError(
                f"Required dependencies not installed: {e}. "
                "Install with: pip install pyannote.audio torch"
            )
    
    def _load_model(self) -> None:
        """Load the diarization model."""
        try:
            from pyannote.audio import Pipeline
            
            # Check for HuggingFace token
            if not self.settings.huggingface_token:
                raise ValueError(
                    "HuggingFace token required for diarization. "
                    "Set HUGGINGFACE_TOKEN in .env file"
                )
            
            logger.info(f"Loading diarization model: {self.settings.diarization_model}")
            
            # Load pipeline with authentication
            # Try new API first (token parameter), fall back to old API (use_auth_token)
            try:
                self.pipeline = Pipeline.from_pretrained(
                    self.settings.diarization_model,
                    token=self.settings.huggingface_token
                )
            except TypeError:
                # Fall back to deprecated parameter name for older versions
                self.pipeline = Pipeline.from_pretrained(
                    self.settings.diarization_model,
                    use_auth_token=self.settings.huggingface_token
                )
            
            # Move to GPU if available, otherwise CPU
            import torch
            if torch.cuda.is_available():
                self.pipeline.to(torch.device("cuda"))
                logger.info("Using GPU for diarization")
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                # Apple Silicon MPS support
                self.pipeline.to(torch.device("mps"))
                logger.info("Using Apple Silicon MPS for diarization")
            else:
                self.pipeline.to(torch.device("cpu"))
                logger.info("Using CPU for diarization")
            
            logger.info("Diarization model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load diarization model: {e}")
            raise RuntimeError(f"Could not load diarization model: {e}") from e
    
    def diarize_audio(self, audio_path: str) -> List[AudioSegment]:
        """Perform speaker diarization on audio file.
        
        Args:
            audio_path: Path to the audio file (WAV format, 16kHz mono recommended).
            
        Returns:
            List of AudioSegment objects with speaker IDs and timestamps.
            
        Raises:
            ValueError: If audio file cannot be processed.
        """
        if not Path(audio_path).exists():
            raise ValueError(f"Audio file does not exist: {audio_path}")
        
        try:
            logger.info(f"Starting diarization for: {audio_path}")
            
            # Workaround for torchcodec/AudioDecoder issue:
            # Load audio with librosa and pass as dict instead of file path
            # This avoids the AudioDecoder NameError when torchcodec is not available
            try:
                import librosa
                import torch
                
                # Load audio file
                waveform, sample_rate = librosa.load(audio_path, sr=16000, mono=True)
                
                # Convert to torch tensor (shape: [channels, samples])
                waveform_tensor = torch.from_numpy(waveform).unsqueeze(0)  # [1, samples]
                
                # Create audio dict for pyannote.audio
                audio_dict = {
                    "waveform": waveform_tensor,
                    "sample_rate": sample_rate
                }
                
                logger.debug(f"Loaded audio: {waveform_tensor.shape}, sample_rate={sample_rate}")
                
                # Run diarization pipeline with audio dict
                diarization_output = self.pipeline(audio_dict)
                
            except ImportError:
                # Fallback to file path if librosa is not available
                logger.warning("librosa not available, using file path (may fail with torchcodec issues)")
                diarization_output = self.pipeline(audio_path)
            
            # Handle pyannote.audio 3.1 output format (DiarizeOutput object)
            # DiarizeOutput has .speaker_diarization property (or .annotation in some versions)
            from pyannote.core import Annotation
            
            # Try to extract Annotation from output
            diarization = None
            
            if isinstance(diarization_output, Annotation):
                # Already an Annotation object
                diarization = diarization_output
            else:
                # Try different attribute names (pyannote.audio API varies)
                # Check for .speaker_diarization first (pyannote.audio 3.1/4.x), then .annotation
                for attr_name in ['speaker_diarization', 'annotation']:
                    if hasattr(diarization_output, attr_name):
                        try:
                            attr_value = getattr(diarization_output, attr_name)
                            # Check if it's an Annotation OR has itertracks method
                            if isinstance(attr_value, Annotation) or hasattr(attr_value, 'itertracks'):
                                diarization = attr_value
                                break
                        except (AttributeError, TypeError):
                            continue
                
                # If still not found, try dict access
                if diarization is None and isinstance(diarization_output, dict):
                    for key in ['speaker_diarization', 'annotation']:
                        if key in diarization_output:
                            value = diarization_output[key]
                            if isinstance(value, Annotation) or hasattr(value, 'itertracks'):
                                diarization = value
                                break
            
            # Final validation: must have itertracks method
            if diarization is None or not hasattr(diarization, 'itertracks'):
                output_type = type(diarization_output).__name__
                output_attrs = [attr for attr in dir(diarization_output) if not attr.startswith('_')][:10]
                raise ValueError(
                    f"Unexpected diarization output format: {output_type}. "
                    f"Expected Annotation object or DiarizeOutput with .speaker_diarization/.annotation property. "
                    f"Available attributes: {output_attrs}"
                )
            
            # Convert pyannote output to AudioSegment objects
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segment = AudioSegment(
                    start_time=round(turn.start, 3),
                    end_time=round(turn.end, 3),
                    speaker_id=f"Speaker_{speaker}",
                    confidence=None  # pyannote doesn't provide confidence by default
                )
                segments.append(segment)
            
            logger.info(f"Diarization complete: {len(segments)} segments, {len(set(s.speaker_id for s in segments))} speakers")
            
            # Merge overlapping segments
            merged_segments = self.merge_overlapping_segments(segments)
            
            return merged_segments
            
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            raise ValueError(f"Could not perform diarization: {audio_path}") from e
    
    def merge_overlapping_segments(
        self,
        segments: List[AudioSegment]
    ) -> List[AudioSegment]:
        """Merge overlapping speaker segments.
        
        When segments overlap, assigns to the segment with longer duration
        or keeps both if they're similar in length.
        
        Args:
            segments: List of AudioSegment objects, possibly overlapping.
            
        Returns:
            List of AudioSegment objects with overlaps resolved.
        """
        if not segments:
            return []
        
        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda s: s.start_time)
        merged = []
        
        for current in sorted_segments:
            if not merged:
                merged.append(current)
                continue
            
            last = merged[-1]
            
            # Check for overlap
            if current.start_time < last.end_time:
                # Overlap detected - merge based on duration
                overlap_duration = last.end_time - current.start_time
                
                # If overlap is significant (>50% of shorter segment), merge
                shorter_duration = min(current.duration, last.duration)
                if overlap_duration > 0.5 * shorter_duration:
                    # Keep the longer segment, extend if needed
                    if current.duration > last.duration:
                        # Replace with current segment
                        merged[-1] = current
                    else:
                        # Extend last segment if current extends beyond it
                        if current.end_time > last.end_time:
                            merged[-1] = AudioSegment(
                                start_time=last.start_time,
                                end_time=current.end_time,
                                speaker_id=last.speaker_id,
                                confidence=last.confidence
                            )
                else:
                    # Small overlap - split at midpoint
                    midpoint = (current.start_time + last.end_time) / 2
                    merged[-1] = AudioSegment(
                        start_time=last.start_time,
                        end_time=midpoint,
                        speaker_id=last.speaker_id,
                        confidence=last.confidence
                    )
                    merged.append(AudioSegment(
                        start_time=midpoint,
                        end_time=current.end_time,
                        speaker_id=current.speaker_id,
                        confidence=current.confidence
                    ))
            else:
                # No overlap, add as new segment
                merged.append(current)
        
        return merged
