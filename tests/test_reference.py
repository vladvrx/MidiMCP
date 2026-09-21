import numpy as np
import pytest
import soundfile as sf
from midimcp.reference import excerpt


def test_excerpt_preserves_samples_and_channels(tmp_path):
    source = tmp_path / "source.wav"
    data = np.column_stack([np.arange(1000)/1000, -np.arange(1000)/1000])
    sf.write(source, data, 1000, subtype="FLOAT")
    result = excerpt(source, tmp_path / "clip.wav", .2, .3)
    clip, rate = sf.read(result["path"])
    assert rate == 1000 and clip.shape == (300, 2)
    assert np.allclose(clip, data[200:500])
    assert result["normalization_applied"] is False
    with pytest.raises(FileExistsError):
        excerpt(source, tmp_path / "clip.wav", .2, .3)


@pytest.mark.parametrize("start,duration", [(-1,1), (0,float("nan")), (0,121), (.9,.2)])
def test_invalid_excerpt(tmp_path, start, duration):
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros(1000), 1000)
    with pytest.raises(ValueError):
        excerpt(source, tmp_path / "clip.wav", start, duration)
