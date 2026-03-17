"""Tests for the VoiceProvider interface and ProviderRegistry."""

from unittest.mock import MagicMock, patch

import pytest

from kaivra.audio.base import AudioResult, ProviderRegistry, VoiceProvider


class DummyProvider(VoiceProvider):
    """Concrete test provider."""

    def generate(self, scene_id: str, text: str, **kwargs) -> AudioResult:
        return AudioResult(
            audio_path=f"/tmp/kaivra_{scene_id}.mp3",
            duration_seconds=3.5,
            scene_id=scene_id,
        )


def _make_entry_point(name: str, provider_cls: type):
    """Create a mock entry point that loads to provider_cls."""
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = provider_cls
    return ep


def test_registry_discovers_providers_via_entry_points():
    ep = _make_entry_point("dummy", DummyProvider)
    with patch("kaivra.audio.base.importlib.metadata.entry_points", return_value=[ep]):
        registry = ProviderRegistry()
        registry.discover()
    assert "dummy" in registry.available
    assert registry.get("dummy") is DummyProvider


def test_registry_raises_with_install_hint_when_empty():
    with patch("kaivra.audio.base.importlib.metadata.entry_points", return_value=[]):
        registry = ProviderRegistry()
        registry.discover()
    with pytest.raises(ValueError, match="pip install kaivra-voice"):
        registry.get("elevenlabs")


def test_registry_raises_for_unknown_provider():
    ep = _make_entry_point("dummy", DummyProvider)
    with patch("kaivra.audio.base.importlib.metadata.entry_points", return_value=[ep]):
        registry = ProviderRegistry()
        registry.discover()
    with pytest.raises(ValueError, match="Unknown voice provider"):
        registry.get("nonexistent")


def test_registry_ignores_non_provider_entry_points():
    ep = _make_entry_point("bad", str)  # str is not a VoiceProvider
    with patch("kaivra.audio.base.importlib.metadata.entry_points", return_value=[ep]):
        registry = ProviderRegistry()
        registry.discover()
    assert registry.available == []


def test_audio_result_is_frozen():
    result = AudioResult(audio_path="/tmp/test.mp3", duration_seconds=2.0, scene_id="s1")
    with pytest.raises(AttributeError):
        result.audio_path = "/other.mp3"


def test_dummy_provider_generates_audio_result():
    provider = DummyProvider()
    result = provider.generate("scene_01", "Hello world")
    assert result.scene_id == "scene_01"
    assert result.duration_seconds == 3.5
    assert "scene_01" in result.audio_path
