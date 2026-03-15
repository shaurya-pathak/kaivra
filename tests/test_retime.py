from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming
from kaivra.dsl.retime import (
    estimate_scene_duration,
    retime_document_to_audio_timings,
    retime_document_to_scene_durations,
)


def test_retime_scales_scene_animations_and_duration():
    document = {
        "version": "1.1",
        "meta": {
            "title": "Test",
            "theme": "modern",
            "continuity_duration": "0.6s",
            "glow_release_padding": "0.8s",
        },
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "objects": [],
                "animations": [
                    {"action": "highlight", "target": "step", "at": "2s", "duration": "4s"},
                    {"action": "pulse", "target": "node", "at": "7s", "duration": "1s"},
                ],
                "focus_style": {"at": "1s", "duration": "2s", "scale": 1.1, "color": "accent"},
            }
        ],
    }

    retimed = retime_document_to_scene_durations(document, {"intro": 20.0})
    scene = retimed["scenes"][0]

    assert scene["duration"] == "20s"
    assert scene["animations"][0]["at"] == "4s"
    assert scene["animations"][0]["duration"] == "8s"
    assert scene["animations"][1]["at"] == "14s"
    assert scene["focus_style"]["duration"] == "4s"
    assert retimed["meta"]["continuity_duration"] == "1.2s"
    assert retimed["meta"]["glow_release_padding"] == "1.6s"


def test_estimate_scene_duration_uses_auto_timeline():
    scene = {
        "id": "auto",
        "duration": "auto",
        "objects": [],
        "animations": [
            {"action": "highlight", "target": ["a", "b", "c"], "at": "1s", "duration": "2s", "stagger": "0.5s"}
        ],
    }

    assert estimate_scene_duration(scene) == 5.0


def test_audio_cues_align_scene_local_emphasis_but_leave_global_step_glow_broad():
    document = {
        "version": "1.1",
        "meta": {"title": "Test", "theme": "modern"},
        "objects": [
            {"type": "token", "id": "step_compare", "content": "Compare"},
        ],
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "narration": "Most tests pass. Then one test fails. The machine lights up.",
                "objects": [
                    {"type": "token", "id": "note", "content": "fleet running"},
                    {"type": "box", "id": "machine", "content": "Machine C"},
                ],
                "animations": [
                    {"action": "highlight", "target": "step_compare", "at": "0s", "duration": "8s"},
                    {"action": "highlight", "target": "note", "at": "1s", "duration": "1.4s"},
                    {"action": "pulse", "target": "machine", "at": "4s", "duration": "1s"},
                ],
                "focus": "machine",
                "focus_style": {"at": "5s", "duration": "1.6s", "scale": 1.08, "color": "error"},
            }
        ],
    }

    timing_data = AudioTimingData(
        scenes={
            "intro": SceneAudioTiming(
                id="intro",
                duration_seconds=12.0,
                cues=(
                    AudioCue(start_seconds=2.0, duration_seconds=1.5, text="Most tests pass"),
                    AudioCue(start_seconds=5.5, duration_seconds=1.2, text="one test fails"),
                    AudioCue(start_seconds=8.0, duration_seconds=1.4, text="lights up"),
                ),
            )
        }
    )

    retimed = retime_document_to_audio_timings(document, timing_data)
    scene = retimed["scenes"][0]

    # The persistent carousel-ish step highlight should still be a broad active state.
    assert scene["animations"][0]["at"] == "0s"
    assert scene["animations"][0]["duration"] == "9.6s"

    # Scene-local emphasis should align to cue starts.
    assert scene["animations"][1]["at"] == "2s"
    assert scene["animations"][2]["at"] == "5.5s"
    assert scene["focus_style"]["at"] == "8s"


def test_duration_only_retime_infers_clause_beats_for_scene_local_emphasis():
    document = {
        "version": "1.1",
        "meta": {"title": "Test", "theme": "modern"},
        "objects": [{"type": "token", "id": "step_compare", "content": "Compare"}],
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "narration": "alpha beta. gamma delta. epsilon zeta.",
                "objects": [
                    {"type": "token", "id": "note", "content": "fleet running"},
                    {"type": "box", "id": "machine", "content": "Machine C"},
                ],
                "animations": [
                    {"action": "highlight", "target": "step_compare", "at": "0s", "duration": "8s"},
                    {"action": "highlight", "target": "note", "at": "1s", "duration": "1.0s"},
                    {"action": "pulse", "target": "machine", "at": "4s", "duration": "1.0s"},
                ],
                "focus": "machine",
                "focus_style": {"at": "5s", "duration": "1.6s", "scale": 1.08, "color": "error"},
            }
        ],
    }

    retimed = retime_document_to_scene_durations(document, {"intro": 12.0})
    scene = retimed["scenes"][0]

    # Persistent/global emphasis still scales with the scene.
    assert scene["animations"][0]["duration"] == "9.6s"

    # Local emphasis aligns to narration clause windows instead of only proportional scaling.
    assert scene["animations"][1]["at"] == "0.8s"
    assert scene["animations"][2]["at"] == "4.2s"
    assert scene["focus_style"]["at"] == "7.6s"
