import struct

import pytest

from midimcp.fl_project import _chunks, _encode_chunks, _encode_event, read_events, replace_wrapper_state, replace_native_wrapper_state, build_serum_project
from midimcp.midi import make_phrase
from serum_mcp.preset.packer import SerumPreset, pack_bytes, unpack_bytes


def vst_preset(path, class_id=b"56534558667350736572756D20320000"):
    comp, cont = b"XferJson\0processor", b"XferJson\0controller"
    offset = 48 + len(comp) + len(cont)
    path.write_bytes(b"VST3" + struct.pack("<I", 1) + class_id + struct.pack("<Q", offset)
                     + comp + cont + b"List" + struct.pack("<I", 2)
                     + struct.pack("<4sQQ", b"Comp", 48, len(comp))
                     + struct.pack("<4sQQ", b"Cont", 48 + len(comp), len(cont)))
    return path


def wrapper():
    inner = _encode_chunks([(1, b"config"), (3, b"XferJson\0old processor"), (2, b"XferJson\0old controller"), (4, b"parameter ids")], 1)
    return _encode_chunks([(52, bytes.fromhex("58455356736673506572756D20320000")),
                           (54, b"Serum2"), (53, inner), (99, b"unknown")], 11)


def test_replace_updates_lengths_and_preserves_unknown_chunks(tmp_path):
    before = wrapper()
    after = replace_wrapper_state(before, vst_preset(tmp_path / "test.vstpreset"))
    chunks = dict(_chunks(after, 11))
    assert chunks[99] == b"unknown"
    inner = dict(_chunks(chunks[53], 1))
    assert inner[1] == b"config"
    assert inner[4] == b"parameter ids"
    assert inner[3] == b"XferJson\0processor"
    assert inner[2] == b"XferJson\0controller"
    assert before == wrapper()


def test_mismatched_plugin_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="same Serum"):
        replace_wrapper_state(wrapper(), vst_preset(tmp_path / "bad.vstpreset", b"0" * 32))


@pytest.mark.parametrize("blob", [b"", struct.pack("<I", 12), struct.pack("<I", 11) + b"truncated"])
def test_bad_wrapper_is_rejected(blob):
    with pytest.raises(ValueError):
        _chunks(blob, 11)


def test_flp_event_length_checked(tmp_path):
    path = tmp_path / "bad.flp"
    path.write_bytes(struct.pack("<4sIhHH", b"FLhd", 6, 0, 1, 960) + b"FLdt" + struct.pack("<I", 1) + b"\xc0")
    with pytest.raises(ValueError, match="variable length"):
        read_events(path)


def test_native_translation_preserves_dsp_unknowns_and_moves_ui(tmp_path):
    metadata = {"product": "Serum2", "productVersion": "2.0.18", "component": "processor"}
    processor = pack_bytes(SerumPreset(metadata, {"component": "processor", "version": 7.0}))
    controller = pack_bytes(SerumPreset(dict(metadata, component="controller"), {"presetName": "Old", "selectedPresetPath": "C:/private/old-patch.fxp"}))
    inner = _encode_chunks([(1, b"config"), (3, processor), (2, controller), (4, b"ids")], 1)
    source_wrapper = _encode_chunks([(52, bytes.fromhex("58455356736673506572756D20320000")), (54, b"Serum2"), (53, inner)], 11)
    native = tmp_path / "test.SerumPreset"
    native.write_bytes(pack_bytes(SerumPreset({"presetName": "New"}, {
        "Oscillator0": {"plainParams": "default"}, "FutureModule": {"x": 42},
        "Macro0": {"name": "Brightness", "plainParams": {"value": 0.5}},
        "SerumGUI": {"tab": 1}, "fileType": "SerumPreset",
    })))
    original = native.read_bytes()
    result = replace_native_wrapper_state(source_wrapper, native)
    parts = dict(_chunks(dict(_chunks(result, 11))[53], 1))
    proc, ctrl = unpack_bytes(parts[3]), unpack_bytes(parts[2])
    assert proc.data["FutureModule"] == {"x": 42}
    assert proc.data["Oscillator0"]["plainParams"] == {}
    assert "SerumGUI" not in proc.data
    assert "name" not in proc.data["Macro0"]
    assert ctrl.data["Macro0"]["name"] == "Brightness"
    assert ctrl.metadata["presetName"] == "New"
    assert ctrl.data["SerumGUI"] == {"tab": 1}
    assert ctrl.data["selectedPresetPath"] == ""
    assert parts[4] == b"ids"
    assert native.read_bytes() == original


def test_builder_preserves_native_pattern_sentinel_bits(tmp_path, monkeypatch):
    monkeypatch.setattr("midimcp.fl_project._installed_fl_version", lambda path: (24, 1, 1, 4285))
    def write_container(path, events):
        path.parent.mkdir(parents=True, exist_ok=True)
        body = b"".join(_encode_event(*event) for event in events)
        path.write_bytes(struct.pack("<4sIhHH", b"FLhd", 6, 0, 1, 960) + b"FLdt" + struct.pack("<I", len(body)) + body)
        return path
    clip = bytearray(60)
    struct.pack_into("<H", clip, 6, 20482)
    clip[24:32] = b"\xff" * 8
    source = write_container(tmp_path / "native.flp", [
        (199, b"24.1.1.4285\0"), (159, struct.pack("<I", 4285)),
        (64, b"\0\0"), (21, b"\2"), (213, wrapper()), (233, bytes(clip))])
    installed = tmp_path / "installed"
    write_container(installed / "Data/System/Render tests/FLEX.flp", [
        (199, b"20.1.2.917\0"), (159, struct.pack("<I", 917)), (9, b"\0"),
        (65, b"\1\0"), (99, b"\0\0"), (233, bytes(32))])
    write_container(installed / "Data/Templates/Minimal/Empty/Empty.flp", [
        (64, b"\0\0"), (0, b"\1"), (99, b"\0\0")])
    midi = tmp_path / "phrase.mid"
    make_phrase(midi, [{"pitch": 36, "start": 0, "end": .5}])
    report = build_serum_project(source, vst_preset(tmp_path / "input.vstpreset"), midi,
                                tmp_path / "output", installed)
    result = read_events(report["path"])
    native = next(value for event, value in result if event == 233)
    assert len(native) == 60
    assert native[24:32] == b"\xff" * 8
    assert struct.unpack_from("<H", native, 6)[0] == 20481
    assert next(value for event, value in result if event == 199).startswith(b"24.")
