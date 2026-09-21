import struct
from pathlib import Path

import pytest
from serum_mcp.preset.packer import SerumPreset, pack_bytes

from midimcp.fl_arrangement import replace_channel_serum
from midimcp.fl_project import _encode_chunks, _encode_event, read_events


@pytest.fixture
def arrangement(tmp_path, monkeypatch):
    monkeypatch.setattr("midimcp.fl_arrangement._installed_fl_version", lambda _: (24, 1, 1, 4285))
    def save(name, events):
        body = b"".join(_encode_event(*event) for event in events)
        path = tmp_path / name
        path.write_bytes(struct.pack("<4sIhHH", b"FLhd", 6, 0, 2, 960) + b"FLdt" + struct.pack("<I", len(body)) + body)
        return path
    header = [(199, b"24.1.1.4285\0"), (159, struct.pack("<I", 4285)),
              (65, b"\1\0"), (224, bytes(range(24)))]
    def channel(index, state, internal="FLEX", flags=False):
        return [(64, struct.pack("<H", index)), (21, b"\2"),
                (201, (internal + "\0").encode("utf-16-le")), (212, bytes(52)),
                (203, f"Channel {index}\0".encode("utf-16-le")), (128, b"\x12\x34\x56\0")]
    def channel_tail(state, flags=False):
        return ([(41, b"\1")] if flags else []) + [(213, state), (0, b"\1"),
                (22, b"\x07"), (219, bytes(range(24))), (215, bytes(168))]
    source_events = header + channel(0, b"") + channel_tail(b"original bass")
    source_events += channel(1, b"") + channel_tail(b"untouched keys")
    source_events += [(99, b"\0\0"), (233, bytes(range(60))), (235, b"mixer unknown state")]
    source = save("song.flp", source_events)
    meta = {"product": "Serum2", "productVersion": "2.0.18", "component": "processor"}
    proc = pack_bytes(SerumPreset(meta, {"component": "processor", "version": 7.0}))
    ctrl = pack_bytes(SerumPreset(dict(meta, component="controller"), {"component": "controller"}))
    inner = _encode_chunks([(3, proc), (2, ctrl), (4, b"ids")], 1)
    state = _encode_chunks([(52, bytes.fromhex("58455356736673506572756D20320000")),
                            (54, b"Serum2"), (53, inner)], 11)
    wrapper = save("wrapper.flp", header + channel(0, state, "Fruity Wrapper") + channel_tail(state, True) + [(99, b"\0\0")])
    preset = tmp_path / "patch.SerumPreset"
    preset.write_bytes(pack_bytes(SerumPreset({"presetName": "Replacement"}, {"Oscillator0": {"plainParams": {"kParamOctave": -1.0}}})))
    return source, wrapper, preset, save


def test_preserves_every_unrelated_event_and_source(arrangement, tmp_path):
    source, wrapper, preset, _ = arrangement
    original = source.read_bytes()
    result = replace_channel_serum(source, 0, preset, wrapper, tmp_path / "out", tmp_path)
    before, after = read_events(source), read_events(result["path"])
    start = next(i for i, (event, _) in enumerate(before) if event == 64)
    changed = set(result["changed_source_event_indices"])
    assert {before[index][0] for index in changed} == {201, 212, 213}
    assert all(index > start for index in changed)
    assert result["inserted_wrapper_flag"] is True
    without_insert = [item for item in after if item[0] != 41]
    assert len(without_insert) == len(before)
    for index, value in enumerate(before):
        if index not in changed:
            assert without_insert[index] == value
    assert source.read_bytes() == original
    assert result["channel_name"] == "Channel 0"
    assert result["all_other_event_bytes_preserved"] is True
    second = replace_channel_serum(source, 0, preset, wrapper, tmp_path / "out", tmp_path)
    assert second["path"] != result["path"]


def test_channel_missing_or_invalid_fails_before_writing(arrangement, tmp_path):
    source, wrapper, preset, _ = arrangement
    for channel in (-1, True, 5):
        with pytest.raises(ValueError):
            replace_channel_serum(source, channel, preset, wrapper, tmp_path / "out", tmp_path)
    assert not (tmp_path / "out").exists()


def test_audio_channel_not_silently_replaced(arrangement, tmp_path):
    source, wrapper, preset, save = arrangement
    events = read_events(source)
    index = next(i for i, (event, _) in enumerate(events) if event == 21)
    events[index] = (21, b"\0")
    sampler = save("sampler.flp", events)
    with pytest.raises(ValueError, match="audio clip or sampler"):
        replace_channel_serum(sampler, 0, preset, wrapper, tmp_path / "out", tmp_path)


def test_version_mismatch_fails(arrangement, tmp_path, monkeypatch):
    source, wrapper, preset, _ = arrangement
    monkeypatch.setattr("midimcp.fl_arrangement._installed_fl_version", lambda _: (25, 1, 0, 5000))
    with pytest.raises(ValueError, match="versions must match"):
        replace_channel_serum(source, 0, preset, wrapper, tmp_path / "out", tmp_path)


def test_sequential_replacement_keeps_previous_channel_state(arrangement, tmp_path):
    source, wrapper, preset, _ = arrangement
    first = replace_channel_serum(source, 0, preset, wrapper, tmp_path / "out", tmp_path)
    second = replace_channel_serum(Path(first["path"]), 1, preset, wrapper, tmp_path / "out", tmp_path)
    first_events, second_events = read_events(first["path"]), read_events(second["path"])
    end = next(i for i, (event, value) in enumerate(first_events) if event == 64 and value == b"\1\0")
    assert first_events[:end] == second_events[:end]
