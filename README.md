# MidiMCP

A local MCP server for editable MIDI, Serum 2 preset creation, FL Studio rendering and reference-audio comparison. Reuses [serum-mcp](https://github.com/Celian-mrc/serum-mcp) at commit `6c471bb8424f3f06f16f5b9fc5bfab244fd11384`.

This is an early development build. It does not promise automatic full-song transcription or an exact recreation. A MIDI file contains notes and expression; the matching sound also requires its synth preset, processing and project state.

## Install on Windows

Recreation targets the instrumental. Preserve all original vocal performances as audio, including rap, backing vocals and vocal chops. Do not generate synthetic vocal guides by default. See [ROADMAP.md](ROADMAP.md) for the staged implementation and evaluation plan.

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
| `audio_export_comparison` | Export separate numbered stereo WAVs with optional RMS matching |
| `audio_preserve_vocals` | Copy vocal audio unchanged with provenance and timeline offset |
| `audio_assemble_recreation` | Mix preserved vocal assets with an instrumental render |
| `audio_inspect_levels` | Read full-file LUFS, RMS, peaks and 400 ms level history |
| `audio_match_reference_level` | Match reference loudness using a disclosed constant gain |
| `audio_monitor_levels` | Check instrument and final-mix pairs, reporting unmet targets |
| `reconstruction_plan` | Validate explicit part roles and original-vocal policy |
| `midi_export_instrumental` | Exclude explicitly classified vocal performance tracks |
| `fl_create_serum_project` | Build a new one-channel FLP from a Serum preset and MIDI |
| `fl_replace_channel_serum` | Replace one instrument in a copied arrangement, preserving its MIDI and routing |
| `fl_render_project` | Render a saved FLP with its existing plugin state |
| `fl_render_and_compare` | Render, validate audio and compare with a reference |

Generated files use distinct job directories. Job manifests record outputs and diagnostics. Audio comparison reports timing alignment, level, spectral and envelope differences separately. A dominant spectral peak is not a reliable fundamental-pitch estimate. Metrics do not constitute an accuracy percentage; listen to the A/B.

## Working on a reference

Level preservation applies to every reconstruction. Measure each rebuilt instrument against its corresponding stem and the final mix against its reference. `reconstruction_plan` includes this policy by default. Vocal preservation records levels; native renders and assembled previews automatically attach a level report. Pass `reference_audio` to `fl_render_project` or `reference_mix` to `audio_assemble_recreation` to create a separately corrected copy. The original render and source files remain unchanged; the corrected WAV does not alter FL mixer settings.

Before delivery, call `audio_monitor_levels` with every named instrument and final mix. Each pair contains `name`, `reference` and `candidate`. Missing references produce `reference_required`; missing coverage and clipping-limited gain produce an unresolved result. Only supplied pairs are checked. Matching requires corresponding complete durations and channel counts; explicitly select matching windows when a host adds render tails. The default tolerance is 0.5 LU and the estimated peak ceiling is -0.1 dBTP. Reports distinguish integrated LUFS, RMS, sample peaks and a 4x oversampled peak estimate. Matching loudness cannot guarantee identical peaks, dynamics or musical content. No limiter is applied silently.

The monitor runs when tools are called; it is not a background service. LUFS uses [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm). Oversampled peaks are estimates, not a certified true-peak measurement.

Call `audio_preserve_vocals` with provenance `user_supplied_stem` or `separated_from_mix`. Separated stems require the original mix and model name; this tool does not perform separation. Pass returned manifests to `audio_assemble_recreation` with an instrumental render. Mixing requires matching sample rates and nonnegative offsets. It retains tails and reports common attenuation, without pitch correction or stretching. Native FL vocal-clip insertion is still pending.

`midi_export_instrumental` requires every zero-based track index as a string key mapped to `instrumental`, `vocal` or `metadata`. It rejects unresolved/mixed roles and shared vocal/instrument channels. It preserves metadata and retained event timing. Generic MIDI creation remains available; the recreation plan enforces voices as audio.

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
