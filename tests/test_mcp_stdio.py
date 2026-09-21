"""Real subprocess MCP transport tests. No FL launch or proprietary fixture copy."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest
import soundfile as sf
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _environment(tmp_path):
    env = dict(os.environ)
    env["MIDIMCP_OUTPUT_DIR"] = str(tmp_path / "mcp-jobs")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return env


def _payload(result):
    assert not result.isError, result.model_dump_json()
    # Untyped dict returns use JSON text; typed dicts may additionally expose
    # structuredContent. Both are valid MCP results and must agree if present.
    texts = [part.text for part in result.content if part.type == "text"]
    assert texts
    value = json.loads(texts[0])
    assert isinstance(value, dict)
    if result.structuredContent is not None:
        assert result.structuredContent == value
    json.dumps(value, allow_nan=False)
    return value


async def _run_smoke(tmp_path):
    params = StdioServerParameters(command=sys.executable, args=["-m", "midimcp.server"],
                                  env=_environment(tmp_path))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
            init = await session.initialize()
            assert init.serverInfo.name == "MidiMCP"
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            expected = {"capabilities", "serum_parameter_schema", "serum_create_preset", "serum_edit_preset",
                        "serum_describe_preset", "midi_create_phrase", "midi_inspect", "audio_compare",
                        "fl_render_project", "fl_render_and_compare"}
            assert expected <= tools.keys()
            assert tools["midi_create_phrase"].inputSchema["properties"]["notes"]["type"] == "array"
            assert tools["audio_compare"].inputSchema["required"] == ["reference", "candidate"]
            assert tools["serum_create_preset"].inputSchema["properties"]["spec"]["type"] == "object"
            if tools["midi_create_phrase"].outputSchema is not None:
                assert tools["midi_create_phrase"].outputSchema["type"] == "object"
            capabilities = _payload(await session.call_tool("capabilities", {}))
            assert capabilities["transport"] == "stdio"
            created = _payload(await session.call_tool("midi_create_phrase", {
                "notes": [{"start": .25, "end": .75, "pitch": 36, "velocity": 100}], "bpm": 120}))
            inspected = _payload(await session.call_tool("midi_inspect", {"path": created["path"]}))
            assert inspected["note_count"] == 1
            assert inspected["notes"][0]["start"] == .25
            assert inspected["notes"][0]["end"] == .75
            t = np.arange(8000) / 8000
            a, b = tmp_path / "reference.wav", tmp_path / "candidate.wav"
            sf.write(a, .2*np.sin(2*np.pi*100*t), 8000, subtype="FLOAT")
            sf.write(b, .1*np.sin(2*np.pi*100*t), 8000, subtype="FLOAT")
            compared = _payload(await session.call_tool("audio_compare", {"reference": str(a), "candidate": str(b)}))
            assert compared["aligned"]["relative_rms_error_level_matched"] < 1e-6
            assert Path(compared["ab"]["path"]).is_file()
            plan = _payload(await session.call_tool("reconstruction_plan", {"parts": [
                {"id": "bass", "role": "bass"}, {"id": "voice", "role": "rap"}]}))
            assert plan["parts"][1]["representation"] == "audio"
            preserved = _payload(await session.call_tool("audio_preserve_vocals", {
                "source": str(a), "provenance": "user_supplied_stem"}))
            assert Path(preserved["path"]).read_bytes() == a.read_bytes()
            assembled = _payload(await session.call_tool("audio_assemble_recreation", {
                "instrumental": str(b), "vocal_assets": [preserved]}))
            mixed, rate = sf.read(assembled["outputs"]["recreation"]["path"])
            assert rate == 8000 and np.max(np.abs(mixed-.3*np.sin(2*np.pi*100*t))) < 1e-6
            pair = _payload(await session.call_tool("audio_export_comparison", {
                "first": str(a), "second": str(b)}))
            assert [item["number"] for item in pair["files"]] == [1, 2]
            monitored = _payload(await session.call_tool("audio_monitor_levels", {"pairs": [
                {"name": "instrument", "reference": str(a), "candidate": str(b)}]}))
            assert monitored["all_targets_achieved"]
            assert abs(monitored["results"][0]["applied_gain_db"]-6.0206) < .01
            exported = _payload(await session.call_tool("midi_export_instrumental", {
                "source": created["path"], "track_roles": {"0": "instrumental"}}))
            assert exported["removed_vocal_note_count"] == 0
            invalid = await session.call_tool("midi_create_phrase", {
                "notes": [{"start": 0, "end": 1, "pitch": 200}]})
            assert invalid.isError is True
            assert "pitch" in " ".join(part.text for part in invalid.content if part.type == "text")
            bad_schema = await session.call_tool("midi_inspect", {})
            assert bad_schema.isError is True
            # A failed call must not kill the server/session.
            assert _payload(await session.call_tool("capabilities", {}))["transport"] == "stdio"


def test_real_stdio_transport(tmp_path):
    asyncio.run(_run_smoke(tmp_path))


def test_real_stdio_serum_fixture(tmp_path):
    configured = os.environ.get("MIDIMCP_UPSTREAM_ROOT")
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "upstream-serum"
    fixture = root / "fixtures" / "init_preset.SerumPreset"
    if not fixture.is_file():
        pytest.skip("Set MIDIMCP_UPSTREAM_ROOT to the pinned serum-mcp checkout for native-fixture integration")
    before = fixture.read_bytes()
    async def run():
        env = _environment(tmp_path)
        env["MIDIMCP_UPSTREAM_ROOT"] = str(root.resolve())
        params = StdioServerParameters(command=sys.executable, args=["-m", "midimcp.server"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                schema = _payload(await session.call_tool("serum_parameter_schema", {}))
                assert "oscillators" in schema["properties"]
                result = _payload(await session.call_tool("serum_create_preset", {
                    "spec": {"oscillators": [{"octave": -1.0}]}, "name": "MCP integration bass"}))
                assert Path(result["path"]).suffix == ".SerumPreset"
                assert Path(result["manifest"]).is_file()
                described = _payload(await session.call_tool("serum_describe_preset", {"path": result["path"]}))
                assert described["metadata"]["presetName"] == "MCP integration bass"
                assert described["spec"]["oscillators"][0]["octave"] == -1.0
                assert described["sha256"] == result["sha256"]
    asyncio.run(run())
    assert fixture.read_bytes() == before
