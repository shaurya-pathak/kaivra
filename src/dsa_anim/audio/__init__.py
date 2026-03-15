"""Audio helpers for muxing and timing-aware animation rendering."""

from dsa_anim.audio.local_voice import (
    DEFAULT_SHERPA_BINARY,
    GeneratedLocalVoiceAssets,
    LocalVoiceConfig,
    synthesize_local_voice_assets,
)
from dsa_anim.audio.mux import mux_audio
from dsa_anim.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming, load_audio_timing_data, load_audio_timings

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
