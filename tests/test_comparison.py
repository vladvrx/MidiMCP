import numpy as np
import pytest
import soundfile as sf
from midimcp.comparison import export_pair


def test_numbered_pair_keeps_stereo_timing_and_sources(tmp_path):
    a, b = tmp_path/'a.wav', tmp_path/'b.wav'
    x = np.zeros((8000, 2)); x[120:240, 0] = .2; x[400:520, 1] = -.2
    sf.write(a, x, 8000, subtype='FLOAT'); sf.write(b, x*3, 8000, subtype='FLOAT')
    before = a.read_bytes(), b.read_bytes()
    result = export_pair(a, b, tmp_path/'out')
    first, _ = sf.read(result['files'][0]['path']); second, _ = sf.read(result['files'][1]['path'])
    assert np.max(np.abs(first-second)) < 2e-7
    assert np.max(np.abs(first-x)) < 2e-7
    assert first.shape == (8000, 2)
    assert (a.read_bytes(), b.read_bytes()) == before
    with pytest.raises(ValueError, match='new files'):
        export_pair(a, b, tmp_path/'out')


def test_common_headroom_and_silence_rejection(tmp_path):
    a, b = tmp_path/'a.wav', tmp_path/'b.wav'
    sf.write(a, np.ones(8000)*2, 8000, subtype='FLOAT')
    sf.write(b, np.ones(8000), 8000, subtype='FLOAT')
    result = export_pair(a, b, tmp_path/'out', False)
    for item in result['files']:
        data, _ = sf.read(item['path'])
        assert np.max(np.abs(data)) <= .980001
    assert result['common_attenuation_db'] < 0
    sf.write(b, np.zeros(8000), 8000)
    with pytest.raises(ValueError, match='silent'):
        export_pair(a, b, tmp_path/'other')
