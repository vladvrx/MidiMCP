from pathlib import Path

import pytest
from serum_mcp.preset.packer import SerumPreset, pack_bytes, unpack_bytes

from midimcp.presets import create_preset, describe_preset, edit_preset, parameter_schema


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.SerumPreset"
    path.write_bytes(pack_bytes(SerumPreset(
        metadata={"presetName": "Original", "vendorExtension": "keep"},
        data={"FutureModule": {"blob": b"unknown-field", "path": "User/private.wav"}},
    )))
    return path


def test_source_immutable_unknown_fields_and_unique_names(source, tmp_path):
    before = source.read_bytes()
    first = edit_preset(source, {}, tmp_path, "CON/../../Bass")
    second = edit_preset(source, {}, tmp_path, "CON/../../Bass")
    assert first["path"] != second["path"]
    assert Path(first["path"]).parent == tmp_path
    assert source.read_bytes() == before
    candidate = unpack_bytes(Path(first["path"]).read_bytes())
    assert candidate.data == unpack_bytes(before).data
    assert candidate.metadata["vendorExtension"] == "keep"
    assert first["dependencies"][0]["reference"] == "User/private.wav"
    assert describe_preset(Path(first["path"]))["metadata"]["presetName"] == "CON/../../Bass"


@pytest.mark.parametrize("spec", [
    {"unexpected": 1}, {"oscillators": [{"octve": -1.0}]},
    {"oscillators": [{"octave": -99.0}]},
    {"oscillators": [{"custom_harmonics": [1.0, 0.5]}]},
])
def test_invalid_spec_has_no_output(source, tmp_path, spec):
    with pytest.raises(ValueError):
        edit_preset(source, spec, tmp_path / "out", "Bass")
    assert not (tmp_path / "out").exists()


def test_explicit_default_reset_fails_instead_of_silent_success(source, tmp_path):
    changed = edit_preset(source, {"oscillators": [{"octave": -1.0}]}, tmp_path, "Low")
    with pytest.raises(ValueError, match="did not apply"):
        edit_preset(Path(changed["path"]), {"oscillators": [{"octave": 0.0}]}, tmp_path / "reset", "Reset")
    assert not (tmp_path / "reset").exists()


def test_create_from_explicit_fixture_root(source, tmp_path, monkeypatch):
    root = tmp_path / "upstream"
    (root / "fixtures").mkdir(parents=True)
    (root / "fixtures" / "init_preset.SerumPreset").write_bytes(source.read_bytes())
    monkeypatch.setenv("MIDIMCP_UPSTREAM_ROOT", str(root))
    result = create_preset({}, tmp_path / "out", "Bass")
    assert describe_preset(Path(result["path"]))["metadata"]["presetAuthor"] == "MidiMCP"


def test_missing_fixture_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIMCP_UPSTREAM_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="MIDIMCP_UPSTREAM_ROOT"):
        create_preset({}, tmp_path / "out", "Bass")


def test_schema_forbids_ignored_keys():
    schema = parameter_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["OscillatorSpec"]["additionalProperties"] is False
