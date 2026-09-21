import hashlib
import mido
import pytest

from midimcp.workflow import create_reconstruction_plan, export_instrumental_midi, VOCAL_ROLES


@pytest.mark.parametrize("role", sorted(VOCAL_ROLES))
def test_all_voices_remain_audio(role):
    part = {"id": "voice", "role": role}
    plan = create_reconstruction_plan([part, {"id": "bass", "role": "bass"}])
    assert plan["parts"][0]["representation"] == "audio"
    assert plan["parts"][0]["processing_policy"]["synthesize_voice"] is False
    assert plan["parts"][1]["representation"] == "midi"
    assert part == {"id": "voice", "role": role}
    assert plan["vocal_policy"] == "preserve_original_audio"


@pytest.mark.parametrize("update", [{"role": "unknown"}, {"role": "mixed"}, {"representation": "midi"},
                                    {"confidence": float("nan")}, {"confidence": True}, {"confidence": 1.01},
                                    {"status": "verified"}, {"status": "perfect"}, {"accuracy": 100}])
def test_reject_unsafe_or_unsupported_plan(update):
    part = {"id": "voice", "role": "vocal"}
    part.update(update)
    with pytest.raises(ValueError):
        create_reconstruction_plan([part])


def test_reference_and_evidence(tmp_path):
    source = tmp_path / "stem.wav"
    source.write_bytes(b"local stem placeholder")
    plan = create_reconstruction_plan([{"id": "bass", "role": "bass", "confidence": .4,
                                       "status": "verified", "evidence": ["Human note review"],
                                       "source_path": str(source)}], str(source))
    assert plan["native_fl_verified"] is False
    assert plan["parts"][0]["confidence"] == .4
    with pytest.raises(ValueError, match="unique"):
        create_reconstruction_plan([{"id": "x", "role": "bass"}] * 2)


def fixture_midi(tmp_path, shared=False):
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    midi.tracks = [mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000),
                                 mido.MetaMessage("time_signature", numerator=4, denominator=4)]),
                   mido.MidiTrack([mido.Message("note_on", note=36, channel=0, time=480),
                                   mido.Message("pitchwheel", pitch=2048, channel=0, time=120),
                                   mido.Message("note_off", note=36, channel=0, time=360)]),
                   mido.MidiTrack([mido.MetaMessage("track_name", name="explicit classification only"),
                                   mido.Message("note_on", note=60, channel=0 if shared else 1, time=240),
                                   mido.MetaMessage("set_tempo", tempo=1000000, time=240),
                                   mido.Message("control_change", control=64, value=127, channel=0 if shared else 1, time=120),
                                   mido.MetaMessage("lyrics", text="metadata survives", time=120),
                                   mido.Message("note_off", note=60, channel=0 if shared else 1, time=240)])]
    path = tmp_path / "source.mid"
    midi.save(path)
    return path


def timeline(track):
    elapsed, events = 0, []
    for message in track:
        elapsed += message.time
        item = message.dict()
        item["time"] = elapsed
        events.append(item)
    return events


def test_export_preserves_timeline_metadata_expression_and_source(tmp_path):
    source = fixture_midi(tmp_path)
    before = source.read_bytes()
    roles = {"0": "metadata", "1": "instrumental", "2": "vocal"}
    result = export_instrumental_midi(source, roles, tmp_path / "out")
    old, new = mido.MidiFile(source), mido.MidiFile(result["path"])
    assert source.read_bytes() == before
    assert result["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert timeline(old.tracks[1]) == timeline(new.tracks[1])
    assert [e for e in timeline(old.tracks[2]) if e["type"] in {"track_name", "set_tempo", "lyrics", "end_of_track"}] == timeline(new.tracks[2])
    assert new.length == old.length
    assert result["removed_vocal_note_count"] == 1
    assert result["removed_vocal_event_count"] == 3
    assert all(message.is_meta for message in new.tracks[2])


@pytest.mark.parametrize("roles", [{"0": "metadata", "1": "instrumental"},
                                  {"0": "metadata", "1": "instrumental", "2": "mixed"},
                                  {"0": "metadata", "1": "metadata", "2": "vocal"},
                                  {"0": "metadata", "1": "vocal", "2": "vocal"}])
def test_rejected_export_does_not_write(tmp_path, roles):
    source = fixture_midi(tmp_path)
    output = tmp_path / "out"
    with pytest.raises(ValueError):
        export_instrumental_midi(source, roles, output)
    assert not output.exists()


def test_shared_channels_rejected(tmp_path):
    source = fixture_midi(tmp_path, shared=True)
    with pytest.raises(ValueError, match="share MIDI channels"):
        export_instrumental_midi(source, {"0": "metadata", "1": "instrumental", "2": "vocal"}, tmp_path / "out")


def test_vocal_sysex_rejected(tmp_path):
    source = fixture_midi(tmp_path)
    midi = mido.MidiFile(source)
    midi.tracks[2].insert(0, mido.Message("sysex", data=[1, 2]))
    midi.save(source)
    with pytest.raises(ValueError, match="global/system"):
        export_instrumental_midi(source, {"0": "metadata", "1": "instrumental", "2": "vocal"}, tmp_path / "out")
