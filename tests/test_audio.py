import numpy as np
import pytest
import soundfile as sf
from midimcp.audio import compare_audio


def compare(tmp_path, a, b, rate=16000, **kwargs):
    sf.write(tmp_path / "a.wav", a, rate, subtype="FLOAT")
    sf.write(tmp_path / "b.wav", b, rate, subtype="FLOAT")
    return compare_audio(tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "out", **kwargs)


def tone(frequency=100):
    t = np.arange(32000) / 16000
    return 0.3 * np.sin(2*np.pi*frequency*t) * np.minimum(t*10, 1)


def test_identical_and_export(tmp_path):
    result = compare(tmp_path, tone(), tone())
    assert result["aligned"]["relative_rms_error_level_matched"] < 1e-10
    assert result["aligned"]["spectral_db_mean_absolute_error"] < 1e-10
    data, rate = sf.read(result["ab"]["path"])
    assert len(data) == int(4.5 * rate)
    assert np.max(np.abs(data)) <= 0.981


def test_level_difference_is_not_timbre_error(tmp_path):
    result = compare(tmp_path, tone(), tone() * .25)
    assert result["unaligned"]["relative_rms_error"] == pytest.approx(.75, abs=1e-5)
    assert result["levels"]["candidate_match_gain_db"] == pytest.approx(12.0412, abs=.001)
    assert result["aligned"]["relative_rms_error_level_matched"] < 1e-5


def test_bounded_delay(tmp_path):
    rng = np.random.default_rng(10)
    a = rng.normal(0, .1, 32000)
    b = np.concatenate((np.zeros(480), a[:-480]))
    result = compare(tmp_path, a, b)
    assert result["alignment"]["candidate_delay_seconds"] == pytest.approx(.03, abs=1/12000)
    assert result["aligned"]["relative_rms_error_level_matched"] < .02
    assert result["unaligned"]["relative_rms_error"] > 1


def test_octave_detected_as_spectral_peak_change(tmp_path):
    result = compare(tmp_path, tone(100), tone(200))
    assert result["dominant_frequency"]["difference_cents"] == pytest.approx(1200, abs=10)
    assert result["aligned"]["spectral_db_mean_absolute_error"] > .1


def test_silence_and_invalid_inputs(tmp_path):
    result = compare(tmp_path, np.zeros(1600), np.zeros(1600))
    assert result["dominant_frequency"]["reference_hz"] is None
    assert any("silent" in warning for warning in result["warnings"])
    with pytest.raises(ValueError, match="finite"):
        compare(tmp_path, np.full(1600, np.nan), np.zeros(1600))
    with pytest.raises(ValueError, match="max_shift"):
        compare(tmp_path, tone(), tone(), max_shift_seconds=-1)


def test_sample_rates_and_duration_mismatch(tmp_path):
    sf.write(tmp_path / "a.wav", tone(), 16000, subtype="FLOAT")
    t = np.arange(48000) / 48000
    sf.write(tmp_path / "b.wav", .3*np.sin(2*np.pi*100*t)*np.minimum(t*10,1), 48000, subtype="FLOAT")
    result = compare_audio(tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "out")
    assert result["duration_seconds"] == {"reference": 2., "candidate": 1.}
    assert any("Durations differ" in warning for warning in result["warnings"])
    assert result["aligned"]["relative_rms_error_level_matched"] < .01


def test_ab_gain_uses_compared_phrase_not_silent_render_tail(tmp_path):
    a = tone()
    b = np.concatenate((a, np.zeros(len(a) * 3)))
    result = compare(tmp_path, a, b)
    assert result["aligned"]["relative_rms_error_level_matched"] < 1e-6
    # Export tail length must not change the level of identical audible content.
    assert result["ab"]["candidate_gain_db"] == pytest.approx(0., abs=.001)
