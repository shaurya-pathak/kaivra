"""Voice provider interface, setup validation, and plugin registry."""

from __future__ import annotations

import importlib.metadata
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from kaivra.audio.timings import AudioCue


@dataclass(frozen=True)
class AudioResult:
    """Result of generating audio for a single scene."""

    audio_path: str
    duration_seconds: float
    scene_id: str
    cues: tuple[AudioCue, ...] = ()


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
DEFAULT_VOICE_PROVIDER = "openai"
_BUILTIN_VOICE_PROVIDERS = {"openai", "elevenlabs", "local"}


def _voice_install_hint() -> str:
    return (
        "Voice providers are not installed. "
        "From the repo root, run `make install-voice-local` for built-in OpenAI, ElevenLabs, "
        "and local Sherpa support, or install the package directly with "
        '`.venv/bin/python -m pip install -e "./packages/kaivra-voice[local]"`.'
    )


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
            raise ValueError(_voice_install_hint())
        if name not in self._providers:
            available = ", ".join(sorted(self._providers))
            raise ValueError(f"Unknown voice provider: {name!r}. Available: {available}")
        return self._providers[name]

    @property
    def available(self) -> list[str]:
        """Names of discovered providers."""
        return sorted(self._providers)


def resolve_voice_provider_name(name: str | None) -> str:
    """Resolve the requested provider, falling back to env and defaults."""
    if name is not None and name.strip():
        return name.strip()

    env_name = os.environ.get("KAIVRA_VOICE_PROVIDER", "").strip()
    if env_name:
        return env_name

    return DEFAULT_VOICE_PROVIDER


def validate_voice_provider_setup(name: str | None) -> str:
    """Fail early when a built-in voice provider is unavailable or misconfigured."""
    provider_name = resolve_voice_provider_name(name)
    if provider_name not in _BUILTIN_VOICE_PROVIDERS:
        return provider_name

    registry = ProviderRegistry()
    registry.discover()
    try:
        registry.get(provider_name)
    except ValueError as exc:
        message = str(exc)
        if "Voice providers are not installed." in message:
            raise RuntimeError(_voice_install_hint()) from exc
        raise RuntimeError(message) from exc

    if provider_name == "openai":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is required for OpenAI voice renders. "
                "Set it, or pass `--voice-provider elevenlabs` or `--voice-provider local`."
            )
        return provider_name

    if provider_name == "elevenlabs":
        if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
            raise RuntimeError(
                "ELEVENLABS_API_KEY environment variable is required for ElevenLabs voice renders. "
                "Set it, or omit `--voice-provider` to use the default OpenAI provider."
            )
        return provider_name

    try:
        from kaivra_voice.local import resolve_local_model_paths
    except ImportError as exc:
        raise RuntimeError(_voice_install_hint()) from exc

    try:
        resolve_local_model_paths(model_path=None, tokens_path=None, data_dir=None)
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc
    return provider_name
