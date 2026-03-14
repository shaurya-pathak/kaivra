import json

from dsa_anim.audio.timings import load_audio_timing_data


def test_load_audio_timing_data_supports_scene_cues(tmp_path):
    path = tmp_path / "timings.json"
    path.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "intro",
                        "duration_seconds": 12.5,
                        "cues": [
                            {"start_seconds": 1.2, "duration_seconds": 0.8, "text": "hello"},
                            {"at": "3.5s", "end": "4.4s", "kind": "phrase"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    data = load_audio_timing_data(path)

    scene = data.scenes["intro"]
    assert scene.duration_seconds == 12.5
    assert len(scene.cues) == 2
    assert scene.cues[0].start_seconds == 1.2
    assert scene.cues[0].duration_seconds == 0.8
    assert scene.cues[1].start_seconds == 3.5
    assert round(scene.cues[1].duration_seconds, 3) == 0.9
