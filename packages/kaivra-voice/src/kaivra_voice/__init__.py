"""Voice synthesis providers for kaivra animations."""

from kaivra_voice.elevenlabs import ElevenLabsProvider

__all__ = ["ElevenLabsProvider"]

try:
    from kaivra_voice.local import LocalProvider
    __all__.append("LocalProvider")
except ImportError:
    pass
