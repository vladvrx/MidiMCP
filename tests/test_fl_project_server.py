"""Server project creation runs the real serializer against synthetic containers."""
import json
import struct
from pathlib import Path

import mido
import pytest

from midimcp import server
from midimcp.fl_project import _encode_chunks, _encode_event, read_events


@pytest.fixture
def project_inputs(tmp_path, monkeypatch):
    def container(path, events):
        path.parent.mkdir(parents=True, exist_ok=True)
        body = b"".join(_encode_event(*event) for event in events)
        path.write_bytes(struct.pack("<4sIhHH", b"FLhd", 6, 0, 1, 960) + b"FLdt" + struct.pack("<I", len(body)) + body)
        return path
    native_clip = bytearray(60)
    struct.pack_into("<H", native_clip, 6, 20481)
    native_clip[24:32] = b"\xff" * 8
    inner = _encode_chunks([(3, b"XferJson\0old processor"), (2, b"XferJson\0old controller")], 1)
    wrapper = _encode_chunks([(52, bytes.fromhex("58455356736673506572756D20320000")),
                              (54, b"Serum2"), (53, inner)], 11)
    source = container(tmp_path / "source.flp", [
        (199, b"24.1.1.4285\0"), (159, struct.pack("<I", 4285)),
        (64, b"\0\0"), (21, b"\2"), (213, wrapper), (233, bytes(native_clip))])
    installed = tmp_path / "installed"
    container(installed / "Data/System/Render tests/FLEX.flp", [
        (199, b"20.1.2.917\0"), (159, struct.pack("<I", 917)), (9, b"\0"),
        (65, b"\1\0"), (99, b"\0\0"), (233, bytes(32))])
    container(installed / "Data/Templates/Minimal/Empty/Empty.flp", [
        (64, b"\0\0"), (0, b"\1"), (99, b"\0\0")])
    preset = tmp_path / "patch.vstpreset"
    comp, cont = b"XferJson\0new processor", b"XferJson\0new controller"
    preset.write_bytes(b"VST3" + struct.pack("<I", 1) + b"56534558667350736572756D20320000"
                      + struct.pack("<Q", 48 + len(comp) + len(cont)) + comp + cont
                      + b"List" + struct.pack("<I", 2)
                      + struct.pack("<4sQQ", b"Comp", 48, len(comp))
                      + struct.pack("<4sQQ", b"Cont", 48 + len(comp), len(cont)))
    phrase = tmp_path / "phrase.mid"
    server.midi.make_phrase(phrase, [{"pitch": 36, "start": 0, "end": .5}])
    monkeypatch.setenv("MIDIMCP_OUTPUT_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("MIDIMCP_FL_EXECUTABLE", str(installed / "FL64.exe"))
    monkeypatch.setenv("MIDIMCP_TEMPLATE_PROJECT", str(source))
    monkeypatch.setattr(server.fl_project, "_installed_fl_version", lambda _: (24, 1, 1, 4285))
    return source, preset, phrase


def test_real_builder_through_server_writes_unique_projects_and_manifests(project_inputs):
    source, preset, phrase = project_inputs
    original = [path.read_bytes() for path in project_inputs]
    first = server.fl_create_serum_project(str(preset), str(phrase))
    second = server.fl_create_serum_project(str(preset), str(phrase), str(source))
    assert first["path"] != second["path"]
    assert first["note_count"] == 1
    assert first["native_render_verified"] is False
    assert first["fl_version"] == "24.1.1.4285"
    assert json.loads(Path(first["manifest"]).read_text()) == first
    assert set(first["input_sha256"]) == {"wrapper", "preset", "midi"}
    result = read_events(first["path"])
    clip = next(value for event, value in result if event == 233)
    assert len(clip) == 60 and clip[24:32] == b"\xff" * 8
    assert b"new processor" in Path(first["path"]).read_bytes()
    assert b"old processor" not in Path(first["path"]).read_bytes()
    assert original == [path.read_bytes() for path in project_inputs]


def test_missing_wrapper_is_actionable(project_inputs, monkeypatch):
    _, preset, phrase = project_inputs
    monkeypatch.delenv("MIDIMCP_TEMPLATE_PROJECT")
    with pytest.raises(ValueError, match="wrapper_project"):
        server.fl_create_serum_project(str(preset), str(phrase))


def test_newer_executable_rejected_before_output(project_inputs, monkeypatch):
    _, preset, phrase = project_inputs
    monkeypatch.setattr(server.fl_project, "_installed_fl_version", lambda _: (25, 1, 0, 5000))
    with pytest.raises(ValueError, match="differs from wrapper"):
        server.fl_create_serum_project(str(preset), str(phrase))


def test_multichannel_midi_is_not_silently_flattened(project_inputs):
    _, preset, phrase = project_inputs
    midi = mido.MidiFile(str(phrase))
    track = midi.tracks[0]
    track.insert(1, mido.Message("note_on", note=48, channel=1, velocity=80))
    track.insert(-1, mido.Message("note_off", note=48, channel=1, velocity=0))
    midi.save(str(phrase))
    with pytest.raises(ValueError, match="one MIDI channel"):
        server.fl_create_serum_project(str(preset), str(phrase))
