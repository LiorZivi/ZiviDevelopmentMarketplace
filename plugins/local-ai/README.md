# local-ai

A thin **invoker** plugin: it generates images locally by driving [LocalAIExecution](https://github.com/LiorZivi/LocalAIExecution)'s `localai` CLI (FLUX text-to-image) through that project's stable `--json` subprocess contract.

> **LocalAIExecution is a separate project and is *not* vendored here.** This plugin discovers the externally-installed `localai` command at runtime and shells out to it. Nothing about LocalAIExecution's source lives in this repository.

## Skill

### ai-local-diffusion-invoker
Takes a text prompt, runs `localai generate "<prompt>" --json` against the separately-installed CLI, parses the single JSON object it returns, maps the deterministic exit codes to actionable messages, and reports the saved image path(s). Also supports `-Doctor` (verify the GPU/CUDA stack) and `-Capabilities` (list models).

## How it works

The integration boundary is LocalAIExecution's **`--json` contract** (see that repo's `docs/skill-invocation.md`):

- Call `localai generate "<prompt>" --json [knobs]`.
- Read **exactly one JSON object** from stdout: `{ capability, model, artifacts:[{ path, type, metadata }] }`. `path` is the **absolute** PNG path (a `.json` provenance sidecar is written alongside it).
- The **process exit code** is the source of truth (0 ok; 2 bad args; 3 torch/CUDA; 4 no GPU; 5 OOM; 6 gated/token; 7 download; 8 unknown model).

The bundled helper `skills/ai-local-diffusion-invoker/scripts/Invoke-LocalDiffusion.ps1` wraps discovery + invocation + exit-code mapping and emits one normalized envelope:

```jsonc
// success
{ "ok": true,  "exitCode": 0, "mode": "Generate",
  "images": ["C:\\...\\outputs\\...png"], "result": { /* raw localai json */ } }
// failure
{ "ok": false, "exitCode": 5, "mode": "Generate",
  "error": "CUDA out of memory — ...", "stderr": "..." }
```

## Prerequisites

- **LocalAIExecution installed** on the machine (its own repo). It requires Windows
  + an NVIDIA GPU, Python 3.12, the cu128 PyTorch build, and a one-time FLUX model download + Hugging Face login. See that project's `scripts/bootstrap.ps1`.
- **PowerShell** (Windows PowerShell 5.1 or PowerShell 7).

## Discovery (how the helper finds `localai`)

First hit wins:

1. `-LocalAiExe <path>` parameter
2. `$env:LOCALAI_EXE` — full path to `localai.exe`
3. `$env:LOCALAI_HOME` — repo/install root → `\.venv\Scripts\localai.exe`
4. `localai` on `PATH`
5. Convention default: `C:\Dev\MyRepos\LocalAIExecution\.venv\Scripts\localai.exe`

If none resolve, the helper returns `exitCode: 127` with setup guidance.

> **Tip:** set `LOCALAI_HOME` once (e.g. in your PowerShell profile) so discovery is robust regardless of where the repo lives: `setx LOCALAI_HOME "C:\path\to\LocalAIExecution"`

## Usage

```powershell
# Simple generation
pwsh -NoProfile -File ".\skills\ai-local-diffusion-invoker\scripts\Invoke-LocalDiffusion.ps1" `
    -Prompt "a serene mountain lake at dawn"

# Reproducible, sized, into a chosen folder
pwsh -NoProfile -File ".\skills\ai-local-diffusion-invoker\scripts\Invoke-LocalDiffusion.ps1" `
    -Prompt "a neon city street, rain" -Model schnell -Steps 4 -Seed 42 `
    -Width 1344 -Height 768 -OutputDir ".\out"

# Verify the GPU stack / list models / preview the command
... Invoke-LocalDiffusion.ps1 -Doctor
... Invoke-LocalDiffusion.ps1 -Capabilities
... Invoke-LocalDiffusion.ps1 -Prompt "test" -DryRun
```

As a skill, just ask: *"generate an image of a serene mountain lake at dawn"*.

## Design notes

- **Thin client, clean separation.** If LocalAIExecution moves or changes its install location, only the discovery hints change — never copy its code here.
- The first run downloads the model (~33 GB) and may need an HF login; afterwards it runs offline. The first image after a load includes a one-time CUDA warmup.
- **Synergy:** `content-ai`'s `linked-in-post` skill needs cover/visual images — this invoker can supply them while staying decoupled.
