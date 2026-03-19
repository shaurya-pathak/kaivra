from __future__ import annotations

from kaivra.dsl.pacing import get_pacing_profile, resolve_meta_duration
from kaivra.dsl.schema import parse_duration
from kaivra.mcp.blueprints import build_starter_document


def test_narrated_starter_defaults_to_educational_pacing() -> None:
    doc = build_starter_document(
        title="Queues",
        pattern="algorithm_walkthrough",
        beats=[
            {
                "title": "Observe",
                "detail": "A queue removes the oldest item first while preserving the original arrival order for every item in the line.",
            }
        ],
        theme="modern",
        audience=None,
        include_narration=True,
    )

    assert doc.meta.pacing.value == "educational"
    assert doc.meta.continuity_duration == "1.3s"
    assert 8.0 <= parse_duration(doc.scenes[0].duration) <= 16.0
    assert doc.scenes[0].focus_style is not None
    assert doc.scenes[0].focus_style.duration == "1.4s"


def test_silent_starter_defaults_to_balanced_pacing() -> None:
    doc = build_starter_document(
        title="Queues",
        pattern="algorithm_walkthrough",
        beats=[{"title": "Observe", "detail": "A queue removes the oldest item first."}],
        theme="modern",
        audience=None,
        include_narration=False,
    )

    assert doc.meta.pacing.value == "balanced"
    assert doc.meta.continuity_duration == "0.9s"
    assert parse_duration(doc.scenes[0].duration) <= 10.0


def test_explicit_quick_demo_pacing_overrides_narration_default() -> None:
    doc = build_starter_document(
        title="Queues",
        pattern="algorithm_walkthrough",
        beats=[{"title": "Observe", "detail": "A queue removes the oldest item first."}],
        theme="modern",
        audience=None,
        include_narration=True,
        pacing="quick-demo",
    )

    assert doc.meta.pacing.value == "quick-demo"
    assert doc.meta.continuity_duration == "0.6s"
    assert doc.meta.glow_release_padding == "0.8s"
    assert doc.scenes[0].focus_style is not None
    assert doc.scenes[0].focus_style.duration == "1s"


def test_resolve_meta_duration_uses_profile_defaults_only_when_field_missing() -> None:
    profile = get_pacing_profile("educational", include_narration=True)

    assert (
        resolve_meta_duration(
            {"pacing": "educational", "show_subtitles": True},
            "continuity_duration",
        )
        == profile.continuity_duration
    )
    assert (
        resolve_meta_duration(
            {
                "pacing": "educational",
                "show_subtitles": True,
                "continuity_duration": "2.5s",
            },
            "continuity_duration",
        )
        == "2.5s"
    )


def test_educational_pacing_formula_stays_longer_than_quick_demo_for_same_beat() -> None:
    beat = {
        "title": "Weighted Sum",
        "detail": (
            "We multiply one incoming value by its weight, add the bias, and then pass the "
            "result forward as the next stage's input."
        ),
    }
    word_count = len(f"{beat['title']} {beat['detail']}".split())
    educational_profile = get_pacing_profile("educational", include_narration=True)
    quick_profile = get_pacing_profile("quick-demo", include_narration=True)

    educational_doc = build_starter_document(
        title="Forward Propagation",
        pattern="visual_explainer",
        beats=[beat],
        theme="modern",
        audience=None,
        include_narration=True,
        pacing="educational",
    )
    quick_doc = build_starter_document(
        title="Forward Propagation",
        pattern="visual_explainer",
        beats=[beat],
        theme="modern",
        audience=None,
        include_narration=True,
        pacing="quick-demo",
    )

    assert educational_profile.scene_duration_seconds(word_count) == 14
    assert quick_profile.scene_duration_seconds(word_count) == 8
    assert parse_duration(educational_doc.scenes[0].duration) == 14.0
    assert parse_duration(quick_doc.scenes[0].duration) == 8.0
    assert parse_duration(educational_doc.scenes[0].duration) > parse_duration(
        quick_doc.scenes[0].duration
    )
