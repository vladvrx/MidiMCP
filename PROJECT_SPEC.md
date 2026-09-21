# MidiMCP project specification

## User intent

Build a separate, publicly publishable tool on existing open-source foundations. When an AI is asked to recreate music accurately in FL Studio, it should use this tool to produce both the performance and the matching sounds. A generic General MIDI instrument arrangement does not satisfy this requirement.

Serum 2 is the primary sound engine. The tool must not assume every recorded sound originated in Serum. Sample-based recreation, other instruments and approximation must be labelled accurately. User-supplied music is a private test input, not public repository content.

## Components

- Preset adapter around a pinned serum-mcp revision, preserving existing codec and schema support.
- FL adapter for instance identity, exposed parameters, preset loading, MIDI/automation, save/reopen, and native rendering.
- Analysis worker for reference segmentation, performance checks and audio comparisons.
- Bounded iteration coordinator with provenance, recoverable job states, snapshots and candidate history.
- Installer, diagnostics, MCP configuration and reproducible public tests.

Use subagents for independent, bounded work. The main agent owns integration and user-visible evidence.

## First acceptance gate

On the installed FL Studio and Serum versions, complete three automated preset A/B/A cycles after documented one-time setup. Each cycle must load the intended patch, play a fixed MIDI phrase, render through FL Studio, and verify a new non-silent finite output. Confirm a known pitch or envelope change in the audio and restore the original state. The saved project must reopen with the correct notes, Serum state and assets. An isolated VST host may assist experimentation but does not satisfy this FL integration gate.

## Accuracy checks

Assess pitches, rhythm, note lengths, slides and expression separately from timbre. Compare attacks, sustain, release, dynamics, harmonic shape and stereo behavior. Compare level-matched and original-level audio and test both a development phrase and a held-out phrase. Preserve source uncertainty and repeat-render variability. Do not advertise a numerical similarity score as a perceptual accuracy percentage.

## Release gates

Public release follows a working native FL demonstration, actual MCP-client tests, install/reconnect/error recovery tests, documentation, attribution/license review and a scan excluding private/proprietary assets. No implementation or publication is claimed by creating this project scaffold.

## Immediate work

1. Finish upstream and FL adapter audits.
2. Pin the upstream revision and isolate dependencies.
3. Implement the smallest end-to-end native FL acceptance case.
4. Expose that case through MCP and test through a real client.
5. Add reference analysis and bounded patch/performance refinement.
6. Generalize beyond bass and prepare public packaging.
