"""Public tool wrappers: isolation, manifests, validation and failed render gating."""
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from midimcp import server


@pytest.fixture(autouse=True)
def output_root(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setenv("MIDIMCP_OUTPUT_DIR", str(root))
    return root


def test_midi_jobs_are_unique_and_manifest_is_valid_json(output_root):
    notes = [{"start": .1, "end": .6, "pitch": 36, "velocity": 94}]
    first = server.midi_create_phrase(notes, 120)
    second = server.midi_create_phrase(notes, 120)
    assert first["path"] != second["path"]
    assert Path(first["path"]).is_relative_to(output_root)
    assert json.loads(Path(first["manifest"]).read_text()) == first
    assert server.midi_inspect(first["path"])["notes"] == first["notes"]


def test_input_validation_prevents_wrong_file_type(tmp_path):
    path = tmp_path / "not-midi.txt"
    path.write_text("not a MIDI file")
    with pytest.raises(ValueError, match="Expected file type"):
        server.midi_inspect(str(path))
    with pytest.raises(FileNotFoundError):
        server.midi_inspect(str(tmp_path / "missing.mid"))
    with pytest.raises(ValueError, match="pitch"):
        server.midi_create_phrase([{"start": 0, "end": 1, "pitch": 200}])


def test_audio_manifest_and_source_hashes(tmp_path):
    t = np.arange(8000) / 8000
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    sf.write(a, .2*np.sin(2*np.pi*100*t), 8000, subtype="FLOAT")
    sf.write(b, .1*np.sin(2*np.pi*100*t), 8000, subtype="FLOAT")
    before = a.read_bytes(), b.read_bytes()
    result = server.audio_compare(str(a), str(b))
    assert result["aligned"]["relative_rms_error_level_matched"] < 1e-6
    assert len(result["input_sha256"]["reference"]) == 64
    assert result["input_sha256"]["reference"] != result["input_sha256"]["candidate"]
    assert json.loads(Path(result["manifest"]).read_text()) == result
    assert before == (a.read_bytes(), b.read_bytes())


def test_failed_fl_render_never_compares(tmp_path, monkeypatch):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"only existence needed before failed render")
    failure = {"status": "error", "error": "Native renderer timed out"}
    monkeypatch.setattr(server, "fl_render_project", lambda *args: failure)
    def unexpected_compare(*args, **kwargs):
        pytest.fail("Comparison must not run after a failed render")
    monkeypatch.setattr(server, "audio_compare", unexpected_compare)
    result = server.fl_render_and_compare("example.flp", str(reference))
    assert result == {"status": "error", "render": failure, "comparison": None}


def test_missing_fl_is_actionable(monkeypatch):
    monkeypatch.delenv("MIDIMCP_FL_EXECUTABLE", raising=False)
    monkeypatch.setattr(server.fl, "discover_fl", lambda: None)
    with pytest.raises(ValueError, match="MIDIMCP_FL_EXECUTABLE"):
        server.fl_render_project("missing.flp")


def test_capabilities_and_schema_are_json(monkeypatch):
    monkeypatch.setattr(server.fl, "discover_fl", lambda: None)
    monkeypatch.delenv("MIDIMCP_FL_EXECUTABLE", raising=False)
    result = server.capabilities()
    assert result["transport"] == "stdio"
    assert result["fl_executable"] is None
    assert any("No automatic full-song transcription" in text for text in result["limitations"])
    schema = server.serum_parameter_schema()
    assert schema["additionalProperties"] is False
    json.dumps({"capabilities": result, "schema": schema}, allow_nan=False)
