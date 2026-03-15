"""Audio helpers for muxing and timing-aware animation rendering."""

from kaivra.audio.local_voice import (
    DEFAULT_SHERPA_BINARY,
    GeneratedLocalVoiceAssets,
    LocalVoiceConfig,
    synthesize_local_voice_assets,
)
from kaivra.audio.mux import mux_audio
from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming, load_audio_timing_data, load_audio_timings

__all__ = [
    "AudioCue",
    "AudioTimingData",
    "DEFAULT_SHERPA_BINARY",
    "GeneratedLocalVoiceAssets",
    "LocalVoiceConfig",
    "SceneAudioTiming",
    "load_audio_timing_data",
    "load_audio_timings",
    "mux_audio",
    "synthesize_local_voice_assets",
]
