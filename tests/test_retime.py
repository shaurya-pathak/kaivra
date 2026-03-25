from kaivra.audio.timings import AudioCue, AudioTimingData, SceneAudioTiming
from kaivra.dsl.retime import (
    estimate_scene_duration,
    retime_document_to_audio_timings,
    retime_document_to_scene_durations,
)


def test_retime_scales_scene_animations_and_duration():
    document = {
        "version": "1.2",
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
            {
                "action": "highlight",
                "target": ["a", "b", "c"],
                "at": "1s",
                "duration": "2s",
                "stagger": "0.5s",
            }
        ],
    }

    assert estimate_scene_duration(scene) == 5.0


def test_audio_cues_align_scene_local_emphasis_but_leave_global_step_glow_broad():
    document = {
        "version": "1.2",
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


def test_duration_only_retime_scales_scene_local_emphasis_without_inferred_beats():
    document = {
        "version": "1.2",
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

    # Without explicit cue windows, local emphasis only scales with the scene.
    assert scene["animations"][1]["at"] == "1.2s"
    assert scene["animations"][2]["at"] == "4.8s"
    assert scene["focus_style"]["at"] == "6s"


def test_audio_cues_align_reveals_to_narration_windows() -> None:
    document = {
        "version": "1.2",
        "meta": {"title": "Test", "theme": "modern"},
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "objects": [
                    {"type": "box", "id": "input_card", "content": "Input"},
                    {"type": "connector", "id": "flow", "from": "input_card", "to": "result_card"},
                    {"type": "box", "id": "result_card", "content": "Result"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "input_card", "at": "0.4s", "duration": "0.5s"},
                    {"action": "draw", "target": "flow", "at": "2s", "duration": "1s"},
                    {"action": "appear", "target": "result_card", "at": "5s"},
                ],
            }
        ],
    }

    timing_data = AudioTimingData(
        scenes={
            "intro": SceneAudioTiming(
                id="intro",
                duration_seconds=11.0,
                cues=(
                    AudioCue(start_seconds=1.0, duration_seconds=0.9, text="show the input"),
                    AudioCue(start_seconds=3.5, duration_seconds=1.2, text="draw the flow"),
                    AudioCue(start_seconds=6.2, duration_seconds=0.8, text="land on the result"),
                ),
            )
        }
    )

    retimed = retime_document_to_audio_timings(document, timing_data)
    scene = retimed["scenes"][0]

    # Semantic match: "Input" ↔ "show the input", "flow" ↔ "draw the flow",
    # "Result" ↔ "land on the result".  Duration preserved from scene scaling.
    assert scene["animations"][0]["at"] == "1s"
    assert scene["animations"][0]["duration"] == "0.55s"
    assert scene["animations"][1]["at"] == "3.5s"
    assert scene["animations"][1]["duration"] == "1.1s"
    assert scene["animations"][2]["at"] == "6.2s"
    assert "duration" not in scene["animations"][2]


def test_retime_preserves_selected_pacing_baseline_when_meta_fields_are_missing():
    document = {
        "version": "1.2",
        "meta": {
            "title": "Test",
            "theme": "modern",
            "show_narration": True,
            "pacing": "educational",
        },
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "objects": [],
                "animations": [
                    {"action": "highlight", "target": "step", "at": "2s", "duration": "4s"},
                ],
            }
        ],
    }

    retimed = retime_document_to_scene_durations(document, {"intro": 12.0})

    assert retimed["meta"]["continuity_duration"] == "1.56s"
    assert retimed["meta"]["glow_release_padding"] == "1.68s"


def test_semantic_matching_pairs_cues_to_target_content():
    """Word cues should match animation targets by content, not position."""
    document = {
        "version": "1.2",
        "meta": {"title": "Test", "theme": "modern"},
        "scenes": [
            {
                "id": "demo",
                "duration": "10s",
                "objects": [
                    {"type": "token", "id": "fail_token", "content": "FAIL"},
                    {"type": "box", "id": "server_box", "content": "Server"},
                    {"type": "token", "id": "pass_token", "content": "PASS"},
                ],
                "animations": [
                    {"action": "fade-in", "target": "pass_token", "at": "0s", "duration": "0.5s"},
                    {"action": "fade-in", "target": "fail_token", "at": "2s", "duration": "0.5s"},
                    {"action": "fade-in", "target": "server_box", "at": "4s", "duration": "0.5s"},
                ],
            }
        ],
    }

    timing_data = AudioTimingData(
        scenes={
            "demo": SceneAudioTiming(
                id="demo",
                duration_seconds=10.0,
                cues=(
                    AudioCue(start_seconds=1.0, duration_seconds=0.8, text="the server boots"),
                    AudioCue(start_seconds=3.0, duration_seconds=0.6, text="tests pass"),
                    AudioCue(start_seconds=6.0, duration_seconds=0.7, text="one failure"),
                ),
            )
        }
    )

    retimed = retime_document_to_audio_timings(document, timing_data)
    scene = retimed["scenes"][0]

    # "pass_token" (content "PASS") should match cue "tests pass" at 3s.
    assert scene["animations"][0]["at"] == "3s"
    # "fail_token" (content "FAIL") should match cue "one failure" at 6s (substring).
    assert scene["animations"][1]["at"] == "6s"
    # "server_box" (content "Server") should match cue "the server boots" at 1s.
    assert scene["animations"][2]["at"] == "1s"


def test_scene_duration_never_shrinks_below_authored():
    """When TTS audio is shorter than authored duration, keep the authored duration."""
    document = {
        "version": "1.2",
        "meta": {"title": "Test", "theme": "modern"},
        "scenes": [
            {
                "id": "intro",
                "duration": "10s",
                "objects": [],
                "animations": [
                    {"action": "highlight", "target": "step", "at": "2s", "duration": "4s"},
                    {"action": "pulse", "target": "node", "at": "7s", "duration": "1s"},
                ],
            }
        ],
    }

    timing_data = AudioTimingData(
        scenes={
            "intro": SceneAudioTiming(id="intro", duration_seconds=6.0),
        }
    )

    retimed = retime_document_to_audio_timings(document, timing_data)
    scene = retimed["scenes"][0]

    # Scene should keep authored 10s, not shrink to 6s.
    assert scene["duration"] == "10s"
    # Animations should be unchanged (scale = 1.0).
    assert scene["animations"][0]["at"] == "2s"
    assert scene["animations"][0]["duration"] == "4s"
    assert scene["animations"][1]["at"] == "7s"


def test_semantic_matching_uses_spoken_forms_aliases():
    """spoken_forms let cue matching handle alternate pronunciations/transcripts."""
    document = {
        "version": "1.2",
        "meta": {"title": "Test", "theme": "modern"},
        "scenes": [
            {
                "id": "demo",
                "duration": "8s",
                "objects": [
                    {
                        "type": "box",
                        "id": "copilot_box",
                        "content": "Copilot",
                        "spoken_forms": ["co pilot", "cobalt"],
                    }
                ],
                "animations": [
                    {"action": "fade-in", "target": "copilot_box", "at": "1s", "duration": "0.5s"},
                ],
            }
        ],
    }

    timing_data = AudioTimingData(
        scenes={
            "demo": SceneAudioTiming(
                id="demo",
                duration_seconds=8.0,
                cues=(
                    AudioCue(start_seconds=3.2, duration_seconds=0.7, text="cobalt opens the report"),
                ),
            )
        }
    )

    retimed = retime_document_to_audio_timings(document, timing_data)
    scene = retimed["scenes"][0]

    assert scene["animations"][0]["at"] == "3.2s"
