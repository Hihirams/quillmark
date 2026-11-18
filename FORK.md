Quillmark
=========

Quillmark is a **fork of [SlopTotal](https://github.com/pablocaeg/sloptotal)**, an
open-source AI-text detector by [pablocaeg](https://github.com/pablocaeg),
released under the MIT licence.

What that means, plainly:

- **The detector is not ours.** The 23 engines, the calibrated ensemble, the
  SlopBench corpus and every accuracy figure in the README are upstream's work.
  They are reproduced here unchanged.
- **The original copyright notice and the MIT licence stay in place.** See
  [`LICENSE`](LICENSE). Nothing in this fork removes or rewrites them.
- **This fork adds:** Windows launchers (`start-local.ps1`, `stop-local.ps1`), an
  app icon, and the Quillmark name in the UI and the startup banner.

What this fork does **not** change: engine weights, verdict bands, calibration
(`app/calibration.json`), thresholds, or any scoring logic. A text scores the
same here as it does upstream, which is what makes the numbers comparable.

## Why the rename

Quillmark is meant as a working name for a self-hosted deployment, not as a new
detector. If you want the original, the documentation and the benchmark live in
the upstream repository:

- Upstream: <https://github.com/pablocaeg/sloptotal>
- hosted demo: <https://sloptotal.com>
- licence: MIT, copyright (c) 2025-2026 SlopTotal

## Keeping in sync with upstream

This clone keeps the original as a remote, so updates can be pulled without
losing the local additions:

```bash
git fetch upstream
git merge upstream/master
```

If you redistribute a modified version, keep the MIT notice and say what you
changed. That is all the licence asks.
