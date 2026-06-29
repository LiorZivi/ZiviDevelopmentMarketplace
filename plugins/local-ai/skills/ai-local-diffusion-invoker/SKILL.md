---
name: ai-local-diffusion-invoker
description: "Generate images locally on the user's own NVIDIA GPU by invoking a separately-installed LocalAIExecution `localai` CLI (FLUX text-to-image) through its stable --json subprocess contract. This skill vendors NONE of LocalAIExecution's code — it discovers the external tool at runtime and shells out to it. Use when the user wants to create/generate an image, render a picture from a text prompt, run local text-to-image / diffusion / FLUX, or make art on their own GPU without cloud or paid APIs. Triggers on: 'generate an image of X', 'create a picture of X', 'render X locally', 'make art of X', 'text-to-image X', 'run FLUX on X', 'local diffusion X'."
argument-hint: "[prompt]"
user-invocable: true
---

# ai-local-diffusion-invoker — Local Image Generation via the external `localai` CLI

You generate images by driving **LocalAIExecution**, a separate project that exposes a
`localai` command-line tool. That project lives in **its own repository and is NOT part of
this marketplace** — this skill only *discovers and invokes* it. You import none of its code.

The integration boundary is LocalAIExecution's stable **`--json` subprocess contract**
(documented in that repo's `docs/skill-invocation.md`): you run a command, read **exactly one
JSON object** from stdout, and trust the **process exit code** as the source of truth.

## Plugin paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Helper script**: `${CLAUDE_PLUGIN_ROOT}/skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1`

The helper script wraps discovery + invocation + exit-code mapping and emits one normalized
JSON envelope. **Prefer it** over calling `localai` directly.

## How to invoke (primary path)

Run the helper with PowerShell, passing the user's prompt and any knobs:

```powershell
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1" `
    -Prompt "<the user's prompt>" [-Model schnell|dev] [-Steps N] [-Preset NAME] `
    [-Seed N] [-Width N] [-Height N] [-Batch N] [-OutputDir DIR]
```

(Use `powershell` instead of `pwsh` if PowerShell 7 isn't installed — both work.)

The script prints **one JSON object** on stdout. Parse it:

- **`ok: true`** → read `images` (array of absolute PNG paths) and `result` (the raw `localai`
  JSON, including provenance metadata). Report the saved path(s) to the user; offer to open the
  first image.
- **`ok: false`** → read `exitCode` and `error` (already mapped to an actionable message), and
  `stderr` for detail. Relay the remediation; do **not** dump a raw traceback.

### Useful modes

- **Discover models** before generating (optional): add `-Capabilities` (runs
  `localai capabilities --json`).
- **Verify the GPU stack** when generation won't start: add `-Doctor` (runs
  `localai doctor --json`).
- **Preview without running**: add `-DryRun` to see the exact resolved command.

## Knobs (passed through to `localai generate`)

| Param | Meaning | Notes |
|---|---|---|
| `-Model` | `schnell` (default, fast, ~4 steps) or `dev` (gated, higher fidelity) | `dev` needs an HF token (exit 6 otherwise) |
| `-Steps` | inference steps | `schnell` is distilled for ≤4 — more steps won't help it; use `dev` for the quality lever |
| `-Preset` | named size preset (e.g. `widescreen`) | |
| `-Seed` | seed for reproducibility | omit for a random (but recorded) seed |
| `-Width` / `-Height` | pixel size | multiples of 16 |
| `-Batch` | number of images | yields N entries in `images` |
| `-OutputDir` | where PNG + `.json` sidecar are written | default is LocalAIExecution's `outputs/` |

## Discovery & prerequisites

LocalAIExecution must already be installed on the machine (it requires Windows + an NVIDIA GPU,
Python 3.12, the cu128 PyTorch build, and a one-time FLUX model download + HF login). The helper
locates the CLI in this order (first hit wins):

1. `-LocalAiExe` parameter (explicit path to `localai.exe`)
2. `$env:LOCALAI_EXE` (full path to `localai.exe`)
3. `$env:LOCALAI_HOME` (repo/install root) → `\.venv\Scripts\localai.exe`
4. `localai` on `PATH`
5. Convention default: `C:\Dev\MyRepos\LocalAIExecution\.venv\Scripts\localai.exe`

If none resolve, the envelope returns `exitCode: 127` with setup guidance — relay it (point the
user at LocalAIExecution's `scripts/bootstrap.ps1`, or ask them to set `LOCALAI_HOME`).

## Exit codes (from the contract)

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | unexpected error |
| 2 | invalid arguments (size/steps/preset) |
| 3 | CUDA/torch unavailable or wrong build — try `-Doctor` |
| 4 | no NVIDIA GPU detected |
| 5 | CUDA out of memory — reduce `-Width/-Height/-Batch` |
| 6 | gated model / token denied — set `HF_TOKEN` / `huggingface-cli login` |
| 7 | network / download failure |
| 8 | unknown capability or model — try `-Capabilities` |
| 127 | (this wrapper) `localai` CLI not found — install LocalAIExecution / set `LOCALAI_HOME` |

## Examples

```powershell
# Simple generation
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1" `
    -Prompt "a serene mountain lake at dawn"

# Reproducible, sized, into a chosen folder
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1" `
    -Prompt "a neon city street, rain" -Model schnell -Steps 4 -Seed 42 -Width 1344 -Height 768 -OutputDir ".\out"

# Verify the GPU stack
pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1" -Doctor
```

## Notes

- **Separation is intentional.** Never copy LocalAIExecution's source into this repo. This skill
  is a thin client over its CLI contract; if that project moves, only the discovery hints change.
- The first run downloads the model (~33 GB) and may need an HF login; afterwards it runs offline.
- Generation is GPU work — the first image after load includes a one-time CUDA warmup (~tens of
  seconds); subsequent images are fast. Set expectations before long calls.
- **Possible synergy:** the `content-ai` plugin's `linked-in-post` skill needs cover/visual
  images. This invoker can supply them — but keep the two skills decoupled.
