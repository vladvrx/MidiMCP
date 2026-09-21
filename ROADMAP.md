# Instrumental recreation roadmap

Recreate instrumental performances and sounds. Preserve singing, rap, speech, ad-libs, backing vocals and vocal chops as audio. Separated vocals can contain leakage and missing detail; they are not studio stems. MIDI cannot carry recorded voices or synth patches.

## 1. Preserve voices and make delivery repeatable

Copy vocal assets unchanged with hashes, provenance and explicit timeline offsets. Require part roles and remove only explicitly classified vocal MIDI. Assemble aligned previews with complete tails and disclosed headroom attenuation. Export separate numbered stereo comparison WAVs.

Acceptance: byte-identical preserved assets, impulse timing tests, vocal exclusion tests, complete tail coverage, source immutability and real MCP-client calls. Offline assembly does not establish native FL audio-clip integration.

## 2. Native audio clips and expressive MIDI

Add a version-gated FL audio-clip adapter using a dedicated native template. Bundle relative assets; reopen from a relocated folder and render a known impulse at its declared position. Then add named MIDI tracks, tempo/time-signature maps, pitch bends with declared ranges, sustain and expression. Preserve loose timing by default. Keep rejecting unsupported expression in FL until native acceptance passes.

Add transcription adapters with confidence and correction history: monophonic bass and drum onsets first, chords and overlapping instruments separately. Check pitch, onset, offset, octave, slides and groove independently. Uncertain detections stay marked for review.

## 3. Bounded sound search and production matching

Search a whitelist of Serum controls while MIDI stays fixed; refine performance separately. Retain immutable candidates, failures and diagnostics. Cache using patch, MIDI, source, host version and render-setting hashes. Test development and heldout phrases in different registers/velocities; repeat only promising candidates to measure variability.

Add sampler root-note tests, sidechain envelopes, supported automation, effects and stereo checks. Use finite render budgets. Stop when improvements are below measured variability. Spectral distance is not a perceptual accuracy percentage.

## 4. Offline benchmark before RL

Start with self-authored synthetic targets with known MIDI and patches. Group splits by patch origin and sound family, not overlapping snippets. Keep user recordings and commercial assets private.

Test metrics against silence, truncation, wrong octave, delayed attacks, extra tails, gain tricks, stereo cancellation, high-frequency noise and loud spikes. Compare full-band multiresolution spectra, attack/sustain/release, stereo and raw level separately. Score instruments without copied vocals. Current mono/12 kHz diagnostics are insufficient as a learning reward.

Compare seeded random and coordinate search under equal native-render budgets. Use blinded listening on heldout targets, including an unchanged baseline and degraded anchor. Require both diagnostic checks and listening evidence to promote a change.

## 5. Optional local RL sandbox

Only begin after evaluation and search baselines work. State includes reference features, valid patch, previous diagnostics and remaining render budget. Actions are bounded parameter edits or stop. Each creates a new candidate through a serialized native-render queue. No arbitrary shell or project mutation belongs in the action space.

Use seeded resets, distinguish success from budget truncation, gate invalid/clipped/incomplete output and penalize render cost. Keep test targets inaccessible during learning. RL must beat the strongest baseline on heldout targets with equal render budgets. No cloud training or recurring runs are enabled by this roadmap.

## Evaluation references

- [DDSP spectral losses](https://github.com/magenta/ddsp/blob/main/ddsp/losses.py)
- [mir_eval transcription metrics](https://mir-eval.readthedocs.io/stable/api/transcription.html)
- [Gymnasium environment contract](https://gymnasium.farama.org/api/env/)
- [ITU-R BS.1534 listening methodology](https://www.itu.int/rec/R-REC-BS.1534/en)

These guide evaluation design; they do not establish Serum-specific RL performance.
