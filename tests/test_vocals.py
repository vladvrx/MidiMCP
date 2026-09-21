from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from midimcp.vocals import preserve_vocals, assemble_recreation


def wav(tmp_path, name, data, rate=8000):
    path = tmp_path / name
    sf.write(path, np.asarray(data), rate, subtype="FLOAT")
    return path


def test_preserve_byte_identity_and_explicit_provenance(tmp_path):
    source = wav(tmp_path, "voice.wav", [.1, -.2, .3])
    before = source.read_bytes()
    result = preserve_vocals(source, tmp_path / "asset", "user_supplied_stem")
    assert Path(result["path"]).read_bytes() == before == source.read_bytes()
    assert result["source_sha256"] == result["sha256"]
    assert result["provenance_basis"] == "caller_declared"
    assert not result["synthesis_applied"]
    with pytest.raises(FileExistsError):
        preserve_vocals(source, tmp_path / "asset", "user_supplied_stem")


def test_separation_requires_provenance(tmp_path):
    source = wav(tmp_path, "voice.wav", [.1])
    with pytest.raises(ValueError, match="original_mix"):
        preserve_vocals(source, tmp_path / "asset", "separated_from_mix")
    with pytest.raises(ValueError, match="provenance"):
        preserve_vocals(source, tmp_path / "asset", "original_studio_vocal")
    result = preserve_vocals(source, tmp_path / "asset", "separated_from_mix",
                             original_mix=source, separation_model="test-separator-v1")
    assert result["original_mix"]["sha256"] == result["sha256"]
    assert "artifacts" in result["warnings"][0]


def test_sample_offset_stereo_and_tail(tmp_path):
    backing = wav(tmp_path, "backing.wav", [[.2, -.2], [.1, -.1]])
    voice = wav(tmp_path, "voice.wav", [.1, .2, .3])
    asset = preserve_vocals(voice, tmp_path / "asset", "user_supplied_stem", 2 / 8000)
    result = assemble_recreation(backing, [asset], tmp_path / "mix")
    data, rate = sf.read(result["outputs"]["recreation"]["path"], always_2d=True)
    assert rate == 8000 and result["frames"] == 5
    np.testing.assert_allclose(data, [[.2, -.2], [.1, -.1], [.1, .1], [.2, .2], [.3, .3]], atol=1e-7)
    assert result["common_gain"] == 1
    assert not result["resampling_applied"]


def test_multiple_vocals_clipping_common_gain_raw_assets_unchanged(tmp_path):
    backing = wav(tmp_path, "backing.wav", [.8, -.8, .2])
    voice = wav(tmp_path, "voice.wav", [.7, -.7])
    a = preserve_vocals(voice, tmp_path / "asset1", "user_supplied_stem")
    b = preserve_vocals(voice, tmp_path / "asset2", "user_supplied_stem")
    before = Path(a["path"]).read_bytes()
    result = assemble_recreation(backing, [a, b], tmp_path / "mix")
    assert result["common_gain"] == pytest.approx(.98 / 2.2)
    parts = {key: sf.read(value["path"])[0] for key, value in result["outputs"].items()}
    np.testing.assert_allclose(parts["instrumental"] + parts["vocals"], parts["recreation"], atol=1e-7)
    assert abs(parts["recreation"]).max() <= .980001
    assert Path(a["path"]).read_bytes() == before


def test_hash_mismatch_rate_mismatch_and_no_overwrite(tmp_path):
    backing = wav(tmp_path, "backing.wav", [.1])
    voice = wav(tmp_path, "voice.wav", [.1], rate=16000)
    asset = preserve_vocals(voice, tmp_path / "asset", "user_supplied_stem")
    with pytest.raises(ValueError, match="rates must match"):
        assemble_recreation(backing, [asset], tmp_path / "mix")
    asset["sha256"] = "invalid"
    with pytest.raises(ValueError, match="hash"):
        assemble_recreation(backing, [asset], tmp_path / "mix")
    asset = preserve_vocals(backing, tmp_path / "asset2", "user_supplied_stem")
    assemble_recreation(backing, [asset], tmp_path / "mix")
    with pytest.raises(FileExistsError):
        assemble_recreation(backing, [asset], tmp_path / "mix")


@pytest.mark.parametrize("offset", [-1, float("nan"), float("inf"), True, 1201])
def test_bad_offset(tmp_path, offset):
    source = wav(tmp_path, "voice.wav", [.1])
    with pytest.raises(ValueError, match="timeline_start_seconds"):
        preserve_vocals(source, tmp_path / "asset", "user_supplied_stem", offset)


def test_invalid_and_silent_audio(tmp_path):
    bad = wav(tmp_path, "bad.wav", [float("nan")])
    with pytest.raises(ValueError, match="nonfinite"):
        preserve_vocals(bad, tmp_path / "bad", "user_supplied_stem")
    empty = wav(tmp_path, "empty.wav", np.zeros(0))
    with pytest.raises(ValueError, match="nonempty"):
        preserve_vocals(empty, tmp_path / "empty", "user_supplied_stem")
    multichannel = wav(tmp_path, "multi.wav", np.zeros((10, 3)))
    with pytest.raises(ValueError, match="mono/stereo"):
        preserve_vocals(multichannel, tmp_path / "multi", "user_supplied_stem")
    silence = wav(tmp_path, "silent.wav", np.zeros(10))
    result = preserve_vocals(silence, tmp_path / "silence", "user_supplied_stem")
    assert result["silent"] and any("silent" in w for w in result["warnings"])


def test_bounds_before_decode_and_synthesis_rejection(tmp_path, monkeypatch):
    import midimcp.vocals as vocals
    source = wav(tmp_path, "voice.wav", [.1] * 80)
    monkeypatch.setattr(vocals, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="512 MiB"):
        preserve_vocals(source, tmp_path / "asset", "user_supplied_stem")
    monkeypatch.setattr(vocals, "MAX_BYTES", 512 * 1024 * 1024)
    asset = preserve_vocals(source, tmp_path / "asset", "user_supplied_stem")
    asset["synthesis_applied"] = True
    with pytest.raises(ValueError, match="no synthesis"):
        assemble_recreation(source, [asset], tmp_path / "mix")


def test_cross_block_offsets_and_long_instrumental_tail(tmp_path):
    length = 65536 + 20
    backing = wav(tmp_path, "backing.wav", np.full(length + 10, .01))
    voice = wav(tmp_path, "voice.wav", [.1, -.1, .2, -.2])
    asset = preserve_vocals(voice, tmp_path / "asset", "user_supplied_stem", 65535 / 8000)
    result = assemble_recreation(backing, [asset], tmp_path / "mix")
    data, _ = sf.read(result["outputs"]["recreation"]["path"])
    assert len(data) == length + 10
    np.testing.assert_allclose(data[65535:65539], [.11, -.09, .21, -.19], atol=1e-7)
    assert data[-1] == pytest.approx(.01)
