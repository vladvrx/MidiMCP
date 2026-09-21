# Validation

## 0.1.0a3 vocal workflow

108 automated tests passed, including real stdio calls to all five new tools. Tests cover byte-identical vocal preservation, declared provenance, sample offsets, stereo/tails, rate mismatch rejection, clipping protection, source immutability, instrumental-only export with retained event timing, ambiguous track rejection and numbered comparison WAVs.

A private full-song MCP check preserved the separated vocal file byte for byte, removed 436 explicitly classified vocal-guide notes, retained 1,274 instrumental notes and assembled a 231.37-second preview. A common -2.56 dB attenuation protected headroom. This is offline assembly of an existing native instrumental render; native FL vocal-clip insertion and new perceptual fidelity are not established. Original-performance audio is preserved, but separation quality is not certified. No new native renders were needed for this release.

Development build 0.1.0a1, tested on Windows with Python 3.12, FL Studio 24.1.1.4285 and Serum 2.0.18 VST3.

The subsequent 0.1.0a2 adds arrangement-channel replacement and passes 69 automated tests. Its additional tests cover preserving other event bytes, notes, routing, source immutability and replacing multiple channels sequentially. Native acceptance rendered a separate seven-channel project with three Serum instances: 231.37 seconds of finite stereo audio, peak 0.9525, zero clipped samples and no startup errors. The actual MCP client replaced three instruments sequentially while preserving the arrangement. Reference audio and private project assets are not distributed.

## Verified

- All 64 automated tests passed in the fresh project installation. They cover preset source preservation and state roundtrips, MIDI timing and input validation, audio delay/level comparisons, reference excerpt extraction, native wrapper/container validation, and render failure handling.
- A real stdio MCP client initialized the server, discovered tools, created/inspected MIDI and Serum presets, compared audio and recovered from a rejected call.
- Actual FL Studio completed three A/B/A cycles, nine native renders: patch A, patch B with oscillator raised one octave, then A restored. All WAVs were finite, non-silent and unclipped.
- Measured held-note spectral peak ratios B/A ranged from 1.9987427 to 1.9987498. Two restored A files were byte-identical to their baseline. One had 0.00669 normalized RMS difference and correlation 0.9999786, so repeat rendering is not assumed bit-exact. This establishes this fixture's preset-change and restoration behavior.
- A real client of the final installed MCP also completed native project creation followed by FL rendering and audio comparison, with all 12 tools discoverable.
- Final native startup logs contained no invalid-playlist or initialization-failure warnings.
- An FL process guard prevents launching a batch project over an existing session. This was added after discovering native single-instance forwarding during development.
- A regression test covers silent render tails: A/B export uses the aligned phrase's gain, so extra silence does not artificially boost the candidate.

## Not established

This is not a measured recreation of a commercial song. It does not establish automatic transcription accuracy, perceptual similarity across arbitrary sounds, all Serum synthesis modes, multi-instrument FL arrangements, MIDI expression import into FL, or compatibility with other FL/Serum versions. Native tests reopened saved FLPs through FL's renderer; a GUI Save As roundtrip is not part of the acceptance evidence.

## Reproduce native acceptance

With the supported software installed, save a local Serum FLP template with a pattern clip. Create a short original MIDI phrase and a simple patch A. Build and render its project. Create patch B with an octave change, build and render it, then rebuild and render A. Inspect render manifests, native FL startup logs, WAVs, and the A/B comparison. Keep the fixtures local; commercial plugin libraries are not supplied.

Unit/MCP tests do not require FL to launch. Run `python -m pytest` after the documented setup. Native tests require an interactive licensed Windows installation and should not be replaced with mocked render success.
