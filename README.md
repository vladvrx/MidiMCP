# MidiMCP

A local MCP server for editable MIDI, Serum 2 preset creation, FL Studio rendering and reference-audio comparison. Reuses [serum-mcp](https://github.com/Celian-mrc/serum-mcp) at commit `6c471bb8424f3f06f16f5b9fc5bfab244fd11384`.

This is an early development build. It does not promise automatic full-song transcription or an exact recreation. A MIDI file contains notes and expression; the matching sound also requires its synth preset, processing and project state.

## Install on Windows

Requires Python 3.12+, Git, and your own licensed FL Studio and Serum 2 installation for native sound work.

```powershell
./scripts/setup.ps1
```

The setup script creates a local virtual environment, installs the pinned upstream checkout (including its required init fixture), and writes `mcp.local.json`. Add that configuration to an MCP client supporting stdio. No network server or credentials are needed. Optional `MIDIMCP_FL_EXECUTABLE` selects a specific FL64.exe; `MIDIMCP_OUTPUT_DIR` selects the artifact directory.

## Tools

| Tool | Purpose |
| --- | --- |
| `capabilities` | Installed versions, paths and limitations |
| `serum_parameter_schema` | Supported preset controls and values |
| `serum_create_preset` | Create a Serum 2 patch |
| `serum_edit_preset` | Create a revised patch while preserving the source |
| `serum_describe_preset` | Read supported patch state and asset references |
| `midi_create_phrase` | Write editable notes with times in seconds |
| `midi_inspect` | Read timing, pitches, tempo and expression |
| `audio_reference_excerpt` | Extract a precise reference clip without normalization |
| `audio_compare` | Compare corresponding clips and export a level-matched A/B |
| `fl_create_serum_project` | Build a new one-channel FLP from a Serum preset and MIDI |
| `fl_replace_channel_serum` | Replace one instrument in a copied arrangement, preserving its MIDI and routing |
| `fl_render_project` | Render a saved FLP with its existing plugin state |
| `fl_render_and_compare` | Render, validate audio and compare with a reference |

Generated files use distinct job directories. Job manifests record outputs and diagnostics. Audio comparison reports timing alignment, level, spectral and envelope differences separately. A dominant spectral peak is not a reliable fundamental-pitch estimate. Metrics do not constitute an accuracy percentage; listen to the A/B.

## Working on a reference

Use an isolated part or short matching excerpt when possible. Create a MIDI phrase, inspect the preset schema and generate a candidate patch. Call `fl_create_serum_project` with the patch and MIDI, then `fl_render_and_compare`. Refine notes and sound separately. Full-mix spectral differences cannot establish whether one bass patch matches.

The experimental project builder currently supports FL Studio 24 and Serum 2.0.18 VST3. It needs a local FL24 project saved with a Serum instance and a pattern clip as a native wrapper template. Pass its path as `wrapper_project` or set `MIDIMCP_TEMPLATE_PROJECT` in your MCP configuration. Its source notes are not copied and the source is not modified. New projects contain the supplied notes and patch. Native FL wrapper serialization is observational and deliberately version-gated. Other versions require new native acceptance tests.

Save and close FL before batch rendering. FL can forward a new launch into an existing session; MidiMCP refuses to render while FL is open. It never closes your session. Export settings are inherited from FL. The project builder supports notes and velocity only and rejects MIDI expression. It builds one instrument per new project. For existing arrangements, `fl_replace_channel_serum` replaces a selected generator in a new copy while preserving notes, playlist and routing. Automation targeting the previous plugin is retained but not translated to Serum controls.

For Codex, register the local interpreter with `codex mcp add midimcp --env MIDIMCP_UPSTREAM_ROOT=<checkout> --env MIDIMCP_OUTPUT_DIR=<output> -- <venv-python> -m midimcp.server`. Set `tool_timeout_sec = 300` in the resulting server configuration for native renders. See the [official MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

Current preset edits use upstream module defaults for omitted fields within a supplied module. Inspect `changed_raw_fields`. Some reset operations are rejected because upstream silently ignores them. Existing asset references are preserved; new custom sample ingestion is disabled. Commercial libraries, plugin binaries and user audio are never included in this source distribution.

## Validation

```powershell
$env:MIDIMCP_UPSTREAM_ROOT = "$PWD/.dependencies/serum-mcp"
./.venv/Scripts/python.exe -m pytest
```

See `VALIDATION.md` for actual test results and native integration status. See `THIRD_PARTY.md` for upstream attribution. This tool is independent of Xfer Records and Image-Line.
