"""Voice provider interface and plugin registry."""

from __future__ import annotations

import importlib.metadata
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioResult:
    """Result of generating audio for a single scene."""

    audio_path: str
    duration_seconds: float
    scene_id: str


class VoiceProvider(ABC):
    """Abstract base class for voice synthesis providers."""

    @abstractmethod
    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        """Generate audio for a single scene's narration text.

        Args:
            scene_id: Identifier for the scene.
            text: Narration text to synthesize.
            **kwargs: Provider-specific options (e.g. voice_id).

        Returns:
            AudioResult with path to generated audio and measured duration.
        """


_ENTRY_POINT_GROUP = "kaivra.voice_providers"


class ProviderRegistry:
    """Discovers VoiceProvider implementations via entry_points."""

    def __init__(self) -> None:
        self._providers: dict[str, type[VoiceProvider]] = {}

    def discover(self) -> None:
        """Load providers from installed packages."""
        eps = importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)
        for ep in eps:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, VoiceProvider):
                self._providers[ep.name] = cls

    def get(self, name: str) -> type[VoiceProvider]:
        """Get a provider class by name.

        Raises ValueError with install hint if no providers are available.
        """
        if not self._providers:
            raise ValueError(
                "Voice features require kaivra-voice: pip install kaivra-voice"
            )
        if name not in self._providers:
            available = ", ".join(sorted(self._providers))
            raise ValueError(
                f"Unknown voice provider: {name!r}. Available: {available}"
            )
        return self._providers[name]

    @property
    def available(self) -> list[str]:
        """Names of discovered providers."""
        return sorted(self._providers)
