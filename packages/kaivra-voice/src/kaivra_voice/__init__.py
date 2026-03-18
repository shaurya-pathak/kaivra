"""Voice synthesis providers for kaivra animations."""

from kaivra_voice.elevenlabs import ElevenLabsProvider

__all__ = ["ElevenLabsProvider"]

try:
    _local_module = __import__("kaivra_voice.local", fromlist=["LocalProvider"])
    LocalProvider = _local_module.LocalProvider
    __all__.append("LocalProvider")
except ImportError:
    pass
