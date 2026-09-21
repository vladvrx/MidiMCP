import json
import sys

import numpy as np
import pytest
import soundfile as sf

from midimcp.levels import inspect_level, match_level


def tone(tmp_path, name, amplitude=.1, seconds=2, rate=16000):
    t = np.arange(round(seconds*rate))/rate
    audio = amplitude*np.sin(2*np.pi*1000*t)
    path = tmp_path / name
    sf.write(path, audio, rate, subtype="FLOAT")
    return path


def test_known_level_measurements_and_intersample_estimate(tmp_path):
    path = tone(tmp_path, "tone.wav")
    result = inspect_level(path)
    assert result["rms_dbfs"] == pytest.approx(-23.0103, abs=.001)
    assert result["sample_peak_dbfs"] == pytest.approx(-20, abs=.001)
    assert result["integrated_lufs"] is not None
    # Quarter-sample-rate sine with a phase offset undershoots between samples.
    data = .5*np.sin(np.arange(16000)*np.pi/2+np.pi/4)
    sf.write(path, data, 16000, subtype="FLOAT")
    result = inspect_level(path)
    assert result["oversampled_peak_estimate_dbtp"] > result["sample_peak_dbfs"] + 2


def test_constant_gain_matches_and_preserves_sources(tmp_path):
    ref, cand = tone(tmp_path, "ref.wav", .2), tone(tmp_path, "cand.wav", .05)
    originals = [ref.read_bytes(), cand.read_bytes()]
    result = match_level(ref, cand, tmp_path / "out.wav", tolerance_db=.01)
    assert result["applied_gain_db"] == pytest.approx(12.0412, abs=.001)
    assert result["target_achieved"] is True
    assert result["gain_caps"] == []
    assert result["output"]["samples_at_or_above_full_scale"] == 0
    assert [ref.read_bytes(), cand.read_bytes()] == originals
    expected, rate = sf.read(ref)
    actual, _ = sf.read(result["path"])
    assert np.max(abs(expected-actual)) < 1e-7
    json.dumps(result, allow_nan=False)


def test_peak_cap_reports_unmet_target(tmp_path):
    ref, cand = tone(tmp_path, "ref.wav", .4), tone(tmp_path, "cand.wav", .02)
    audio, rate = sf.read(cand)
    audio[rate] = .95
    sf.write(cand, audio, rate, subtype="FLOAT")
    result = match_level(ref, cand, tmp_path / "out.wav")
    assert "estimated_peak_ceiling" in result["gain_caps"]
    assert result["target_achieved"] is False
    assert result["output"]["oversampled_peak_estimate_dbtp"] <= -.099
    assert result["output"]["samples_at_or_above_full_scale"] == 0


def test_gain_budget(tmp_path):
    ref, cand = tone(tmp_path, "ref.wav", .2), tone(tmp_path, "cand.wav", .01)
    result = match_level(ref, cand, tmp_path / "out.wav", max_gain_db=3)
    assert result["applied_gain_db"] == 3
    assert result["gain_caps"] == ["maximum_gain"]
    assert result["target_achieved"] is False


def test_missing_active_region_rejected(tmp_path):
    ref, cand = tone(tmp_path, "ref.wav"), tone(tmp_path, "cand.wav")
    audio, rate = sf.read(cand)
    audio[round(.8*rate):round(1.6*rate)] = 0
    sf.write(cand, audio, rate, subtype="FLOAT")
    with pytest.raises(ValueError, match="missing active reference coverage"):
        match_level(ref, cand, tmp_path / "out.wav")
    assert not (tmp_path / "out.wav").exists()


def test_duration_mismatch_rejected(tmp_path):
    ref, cand = tone(tmp_path, "ref.wav"), tone(tmp_path, "cand.wav", seconds=1)
    with pytest.raises(ValueError, match="same duration"):
        match_level(ref, cand, tmp_path / "out.wav")


@pytest.mark.parametrize("seconds, amplitude", [(2, 0), (.1, .1)])
def test_silent_short_inspection_and_match_rejection(tmp_path, seconds, amplitude):
    ref = tone(tmp_path, "ref.wav", amplitude, seconds)
    result = inspect_level(ref)
    assert result["integrated_lufs"] is None
    json.dumps(result, allow_nan=False)
    with pytest.raises(ValueError, match="Finite integrated LUFS"):
        match_level(ref, ref, tmp_path / "out.wav")


def test_optional_dependency_absence_is_explicit(tmp_path, monkeypatch):
    path = tone(tmp_path, "source.wav")
    monkeypatch.setitem(sys.modules, "pyloudnorm", None)
    result = inspect_level(path)
    assert result["integrated_lufs"] is None
    assert "pyloudnorm" in result["lufs_unavailable_reason"]
    assert result["rms_dbfs"] is not None
    with pytest.raises(ValueError, match="pyloudnorm"):
        match_level(path, path, tmp_path / "out.wav")


def test_source_overwrite_and_nonfinite_rejected(tmp_path):
    path = tone(tmp_path, "source.wav")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="new WAV"):
        match_level(path, path, path)
    assert path.read_bytes() == before
    sf.write(tmp_path / "bad.wav", np.array([float("nan")]*16000), 16000, subtype="FLOAT")
    with pytest.raises(ValueError, match="nonfinite"):
        inspect_level(tmp_path / "bad.wav")
