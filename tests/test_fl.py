from pathlib import Path
import subprocess

import numpy as np
import pytest
import soundfile as sf

from midimcp import fl


@pytest.fixture
def inputs(tmp_path):
    project = tmp_path / "Project with spaces.flp"
    project.write_bytes(b"test snapshot")
    executable = tmp_path / "FL64.exe"
    executable.write_bytes(b"fake")
    return project, tmp_path / "renders", executable


def fake_renderer(monkeypatch, mode="good"):
    calls = []
    monkeypatch.setattr(fl, "_existing_fl_instances", lambda: [])

    class Process:
        pid = 123

        def __init__(self, args, **kwargs):
            self.killed = False
            calls.append(self)
            self.args = args
            assert kwargs["shell"] is False
            job = Path(args[-1][2:])
            assert args[1:3] == ["/Ewav", "/R"]
            assert Path(args[3]).is_absolute()
            assert list(job.iterdir()) == [job / "process.log"]
            if mode not in ("missing", "timeout", "failed"):
                audio = np.sin(2 * np.pi * 110 * np.arange(4410) / 44100) * 0.3
                if mode == "silent":
                    audio[:] = 0
                elif mode == "clipped":
                    audio[0] = 1
                elif mode == "nan":
                    audio[0] = np.nan
                sf.write(job / "render.wav", audio, 44100, subtype="FLOAT")

        def wait(self, timeout):
            if mode == "timeout" and not self.killed:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return 1 if mode == "failed" else 0

        def kill(self):
            self.killed = True

    monkeypatch.setattr(fl.subprocess, "Popen", Process)
    monkeypatch.setattr(fl.time, "sleep", lambda _: None)
    return calls


def test_fresh_render_has_metrics_provenance_and_unique_jobs(inputs, monkeypatch):
    calls = fake_renderer(monkeypatch)
    first = fl.render_project(*inputs)
    second = fl.render_project(*inputs)
    assert first["status"] == second["status"] == "ok"
    assert first["job_dir"] != second["job_dir"]
    assert first["audio"]["duration_seconds"] == pytest.approx(0.1)
    assert first["audio"]["peak"] == pytest.approx(0.3, abs=1e-5)
    assert len(first["audio"]["sha256"]) == 64
    assert len(first["project_sha256"]) == 64
    assert first["patch_identity_verified"] is False
    assert Path(first["job_dir"], "job.json").is_file()
    assert not any(p.killed for p in calls)


def test_missing_project_never_spawns(inputs, monkeypatch):
    calls = fake_renderer(monkeypatch)
    inputs[0].unlink()
    result = fl.render_project(*inputs)
    assert result["error"]["code"] == "missing_project"
    assert not calls
    assert not inputs[1].exists()


def test_running_fl_is_preserved_without_launch_or_forwarding(inputs, monkeypatch):
    calls = fake_renderer(monkeypatch)
    monkeypatch.setattr(fl, "_existing_fl_instances", lambda: [34384])
    result = fl.render_project(*inputs)
    assert result["error"]["code"] == "fl_already_running"
    assert result["existing_fl_pids"] == [34384]
    assert not calls
    assert not inputs[1].exists()


def test_stale_wav_cannot_satisfy_render(inputs, monkeypatch):
    fake_renderer(monkeypatch, "missing")
    inputs[1].mkdir()
    stale = inputs[1] / "render.wav"
    stale.write_bytes(b"old render")
    result = fl.render_project(*inputs)
    assert result["error"]["code"] == "missing_or_ambiguous_audio"
    assert stale.read_bytes() == b"old render"


def test_timeout_only_kills_owned_process(inputs, monkeypatch):
    calls = fake_renderer(monkeypatch, "timeout")
    result = fl.render_project(*inputs, timeout_seconds=0.01)
    assert result["error"]["code"] == "render_timeout"
    assert len(calls) == 1 and calls[0].killed


@pytest.mark.parametrize("mode, code", [("silent", "silent_audio"),
                                         ("clipped", "clipped_audio"),
                                         ("nan", "render_error"),
                                         ("failed", "renderer_failed")])
def test_rejects_invalid_renders(inputs, monkeypatch, mode, code):
    fake_renderer(monkeypatch, mode)
    result = fl.render_project(*inputs)
    assert result["status"] == "error"
    assert result["error"]["code"] == code


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_rejects_invalid_timeout(inputs, monkeypatch, timeout):
    calls = fake_renderer(monkeypatch)
    assert fl.render_project(*inputs, timeout_seconds=timeout)["error"]["code"] == "invalid_timeout"
    assert not calls
