"""Speaker diarization module.

This module handles speaker diarization using pyannote.audio to identify
who spoke when in the audio file.
"""

# Set HuggingFace cache directory to /tmp for Lambda (read-only filesystem except /tmp)
# MUST be set before importing any huggingface_hub or pyannote.audio modules
import os
# Set HOME to /tmp so os.path.expanduser('~') returns /tmp instead of /home/sbx_user1051
if 'HOME' not in os.environ:
    os.environ['HOME'] = '/tmp'
if 'HF_HOME' not in os.environ:
    os.environ['HF_HOME'] = '/tmp/huggingface'
if 'HF_HUB_CACHE' not in os.environ:
    os.environ['HF_HUB_CACHE'] = '/tmp/huggingface/hub'
# Ensure cache directory exists
os.makedirs('/tmp/huggingface/hub', exist_ok=True)

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
        """Check if required dependencies are available.
        
        Raises:
            ImportError: If required dependencies are not available (diarization is mandatory).
        """
        try:
            import torch
            from pyannote.audio import Pipeline
            logger.info("Diarization dependencies available")
        except ImportError as e:
            raise ImportError(
                f"Diarization is mandatory but dependencies are not available: {e}. "
                "Install required dependencies: pip install pyannote.audio torch pytorch-lightning huggingface-hub lazy_loader"
            ) from e
        self._dependencies_available = True
    
    def _load_model(self) -> None:
        """Load the diarization model.
        
        Raises:
            ValueError: If HuggingFace token is missing (diarization is mandatory).
            RuntimeError: If model loading fails (diarization is mandatory).
        """
        if not getattr(self, '_dependencies_available', True):
            raise RuntimeError(
                "Diarization is mandatory but dependencies check failed. "
                "This should not happen if _check_dependencies() passed."
            )
            
        try:
            from pyannote.audio import Pipeline
            
            # If Pipeline is not a real class with from_pretrained (e.g., mocked), skip
            if not hasattr(Pipeline, "from_pretrained"):
                raise ImportError(
                    "pyannote.audio Pipeline does not provide from_pretrained; "
                    "dependencies not fully installed or are being mocked."
                )
            
            # ECS: image bakes models in /opt/models/huggingface and sets HF_HOME, HF_HUB_CACHE, HF_HUB_OFFLINE=1.
            # Do NOT overwrite HF_HOME/HF_HUB_CACHE here, or the loader will look in /tmp (empty) and fail.
            # Lambda: no baked cache; use /tmp and token for download.
            use_offline = os.environ.get('HF_HUB_OFFLINE') == '1'
            hf_home_set = bool(os.environ.get('HF_HOME'))

            if not use_offline and not self.settings.huggingface_token:
                raise ValueError(
                    "HuggingFace token required for diarization when not using offline cache. "
                    "Set HUGGINGFACE_TOKEN in .env or bake models in image with HF_HUB_OFFLINE=1."
                )

            logger.info(
                "Loading diarization model: %s (offline=%s, HF_HOME=%s)",
                self.settings.diarization_model,
                use_offline,
                os.environ.get('HF_HOME', '(unset)'),
            )

            original_token = os.environ.get('HF_TOKEN')
            original_hf_home = os.environ.get('HF_HOME')
            original_hf_hub_cache = os.environ.get('HF_HUB_CACHE')
            try:
                if self.settings.huggingface_token:
                    os.environ['HF_TOKEN'] = self.settings.huggingface_token
                    os.environ['HUGGING_FACE_HUB_TOKEN'] = self.settings.huggingface_token
                # Only point to /tmp when HF_HOME is not already set (e.g. Lambda); ECS sets /opt/models/...
                if not hf_home_set:
                    os.environ['HF_HOME'] = '/tmp/huggingface'
                    os.environ['HF_HUB_CACHE'] = '/tmp/huggingface/hub'
                    os.makedirs('/tmp/huggingface/hub', exist_ok=True)

                self.pipeline = Pipeline.from_pretrained(
                    self.settings.diarization_model
                )
            finally:
                if original_token is not None:
                    os.environ['HF_TOKEN'] = original_token
                elif 'HF_TOKEN' in os.environ:
                    del os.environ['HF_TOKEN']
                if 'HUGGING_FACE_HUB_TOKEN' in os.environ and original_token is None:
                    del os.environ['HUGGING_FACE_HUB_TOKEN']
                if original_hf_home is not None:
                    os.environ['HF_HOME'] = original_hf_home
                elif 'HF_HOME' in os.environ and not hf_home_set:
                    del os.environ['HF_HOME']
                if original_hf_hub_cache is not None:
                    os.environ['HF_HUB_CACHE'] = original_hf_hub_cache
                elif 'HF_HUB_CACHE' in os.environ and not hf_home_set:
                    del os.environ['HF_HUB_CACHE']
            
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
            
        except ImportError as e:
            raise RuntimeError(
                f"Diarization is mandatory but model loading failed (ImportError): {e}. "
                "Ensure all dependencies are installed: pip install pyannote.audio torch pytorch-lightning huggingface-hub lazy_loader"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Diarization is mandatory but model loading failed: {e}. "
                "Check HuggingFace token and model availability."
            ) from e
    
    def diarize_audio(self, audio_path: str) -> List[AudioSegment]:
        """Perform speaker diarization on audio file.
        
        Args:
            audio_path: Path to the audio file (WAV format, 16kHz mono recommended).
            
        Returns:
            List of AudioSegment objects with speaker IDs and timestamps.
            Returns empty list if diarization dependencies are not available.
            
        Raises:
            ValueError: If audio file cannot be processed.
        """
        if not getattr(self, '_dependencies_available', True) or self.pipeline is None:
            raise RuntimeError(
                "Diarization is mandatory but dependencies are not available. "
                "Install required dependencies: pip install pyannote.audio torch pytorch-lightning huggingface-hub"
            )
            
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
                
            except Exception as e:
                # Fallback to file path if librosa fails (ImportError, numba issues, etc.)
                logger.warning("librosa path failed (%s), using file path (may fail with torchcodec issues): %s", type(e).__name__, e)
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
