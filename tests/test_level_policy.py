from pathlib import Path
import numpy as np
import soundfile as sf
from midimcp import server, workflow


def test_default_policy_and_missing_reference(tmp_path, monkeypatch):
    monkeypatch.setenv('MIDIMCP_OUTPUT_DIR', str(tmp_path/'out'))
    path=tmp_path/'tone.wav'
    sf.write(path,.1*np.sin(2*np.pi*220*np.arange(8000)/8000),8000,subtype='FLOAT')
    plan=workflow.create_reconstruction_plan([{'id':'bass','role':'bass'}])
    assert plan['level_policy']['required'] is True
    result=server.audio_monitor_levels([{'name':'bass','candidate':str(path)}])
    assert result['all_targets_achieved'] is False
    assert result['results'][0]['status']=='reference_required'


def test_automatic_render_monitor(tmp_path, monkeypatch):
    path=tmp_path/'tone.wav'; reference=tmp_path/'reference.wav'
    x=.1*np.sin(2*np.pi*220*np.arange(8000)/8000)
    sf.write(path,x,8000,subtype='FLOAT');sf.write(reference,x*2,8000,subtype='FLOAT')
    project=tmp_path/'test.flp';project.write_bytes(b'fixture')
    monkeypatch.setenv('MIDIMCP_FL_EXECUTABLE', 'test.exe')
    monkeypatch.setattr(server.fl,'render_project',lambda *a: {'status':'ok','audio':{'path':str(path)},'job_dir':str(tmp_path)})
    result=server.fl_render_project(str(project),reference_audio=str(reference))
    assert result['level_monitor']['target_achieved']
    assert abs(result['level_monitor']['applied_gain_db']-6.0206)<.01
    assert Path(result['level_monitor']['path']).is_file()
