import mido
import pytest
from midimcp.midi import make_phrase, inspect_midi


def test_roundtrip_seconds_and_chord(tmp_path):
    notes = [{"start": .25, "end": .5, "pitch": 36, "velocity": 100},
             {"start": .25, "end": .75, "pitch": 43, "velocity": 80},
             {"start": .5, "end": 1.25, "pitch": 36, "velocity": 95}]
    result = make_phrase(tmp_path / "phrase.mid", notes, bpm=90)
    assert result["note_count"] == 3
    for actual, expected in zip(result["notes"], notes):
        for key, value in expected.items():
            assert actual[key] == pytest.approx(value, abs=.001)


@pytest.mark.parametrize("update", [{"pitch": 128}, {"pitch": True}, {"velocity": 0},
                                  {"start": -1}, {"end": float("nan")}, {"end": 0}])
def test_reject_invalid_notes(tmp_path, update):
    note = {"start": 0, "end": 1, "pitch": 36, "velocity": 90}
    note.update(update)
    with pytest.raises(ValueError):
        make_phrase(tmp_path / "bad.mid", [note])
    assert not (tmp_path / "bad.mid").exists()


def test_reject_ambiguous_overlap(tmp_path):
    with pytest.raises(ValueError, match="Overlapping"):
        make_phrase(tmp_path / "bad.mid", [{"start": 0, "end": 2, "pitch": 40},
                                            {"start": 1, "end": 3, "pitch": 40}])


def test_tempo_changes_and_velocity_zero_noteoff(tmp_path):
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.extend([mido.MetaMessage("set_tempo", tempo=500000),
                  mido.Message("note_on", note=60, velocity=100, time=480),
                  mido.MetaMessage("set_tempo", tempo=1000000, time=480),
                  mido.Message("note_on", note=60, velocity=0, time=480)])
    path = tmp_path / "tempo.mid"
    midi.save(path)
    result = inspect_midi(path)
    assert result["notes"][0]["start"] == .5
    assert result["notes"][0]["end"] == 2.
    assert result["duration_seconds"] == 2.


def test_unclosed_notes_warn(tmp_path):
    midi = mido.MidiFile()
    midi.tracks.append(mido.MidiTrack([mido.Message("note_on", note=60, velocity=100)]))
    path = tmp_path / "unclosed.mid"
    midi.save(path)
    result = inspect_midi(path)
    assert result["note_count"] == 0
    assert "no matching note-off" in result["warnings"][0]
