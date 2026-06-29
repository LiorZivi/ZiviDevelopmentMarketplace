<#
.SYNOPSIS
    Thin invoker for the separately-installed LocalAIExecution `localai` CLI.

.DESCRIPTION
    Discovers an externally-installed `localai` command (LocalAIExecution lives in
    its own repo and is NOT vendored here), runs it under its stable `--json`
    subprocess contract, parses the single JSON object it prints to stdout, maps
    the deterministic exit codes (0-8) to actionable messages, and emits ONE
    normalized JSON envelope on stdout. All diagnostics go to stderr.

    Discovery order (first hit wins):
      1. -LocalAiExe parameter (explicit full path to localai.exe)
      2. $env:LOCALAI_EXE  (full path to localai.exe)
      3. $env:LOCALAI_HOME (repo/install root) -> .venv\Scripts\localai.exe
      4. `localai` on PATH
      5. Convention default: C:\Dev\MyRepos\LocalAIExecution\.venv\Scripts\localai.exe

.PARAMETER Prompt
    Text-to-image prompt. Required unless -Doctor or -Capabilities is used.

.PARAMETER Model
    Model id (e.g. schnell | dev). Passed through verbatim.

.PARAMETER Steps
    Number of inference steps.

.PARAMETER Preset
    Named size preset (e.g. widescreen).

.PARAMETER Seed
    Seed for reproducibility.

.PARAMETER Width
    Image width (multiple of 16).

.PARAMETER Height
    Image height (multiple of 16).

.PARAMETER Batch
    Number of images to generate (yields N artifacts).

.PARAMETER OutputDir
    Directory to write the PNG(s) + JSON sidecar(s) into.

.PARAMETER Doctor
    Run `localai doctor --json` (verify GPU/CUDA stack) instead of generating.

.PARAMETER Capabilities
    Run `localai capabilities --json` (enumerate models) instead of generating.

.PARAMETER LocalAiExe
    Explicit path to localai.exe, overriding all discovery.

.PARAMETER DryRun
    Resolve + print the exact command without executing it.

.OUTPUTS
    One JSON object on stdout. Shape:
      success:  { "ok": true,  "exitCode": 0, "mode": "...", "command": "...",
                  "images": ["C:\\...png"], "result": { <raw localai json> } }
      failure:  { "ok": false, "exitCode": N, "mode": "...", "command": "...",
                  "error": "<actionable>", "stderr": "<full stderr>" }

.EXAMPLE
    .\Invoke-LocalDiffusion.ps1 -Prompt "a serene mountain lake at dawn"

.EXAMPLE
    .\Invoke-LocalDiffusion.ps1 -Prompt "a neon city street" -Model schnell -Steps 4 -Seed 42 -OutputDir .\out

.EXAMPLE
    .\Invoke-LocalDiffusion.ps1 -Doctor
#>
[CmdletBinding(DefaultParameterSetName = 'Generate')]
param(
    [Parameter(ParameterSetName = 'Generate', Position = 0)]
    [string]$Prompt,

    [Parameter(ParameterSetName = 'Generate')]
    [string]$Model,

    [Parameter(ParameterSetName = 'Generate')]
    [int]$Steps,

    [Parameter(ParameterSetName = 'Generate')]
    [string]$Preset,

    [Parameter(ParameterSetName = 'Generate')]
    [long]$Seed,

    [Parameter(ParameterSetName = 'Generate')]
    [int]$Width,

    [Parameter(ParameterSetName = 'Generate')]
    [int]$Height,

    [Parameter(ParameterSetName = 'Generate')]
    [int]$Batch,

    [Parameter(ParameterSetName = 'Generate')]
    [string]$OutputDir,

    [Parameter(ParameterSetName = 'Doctor')]
    [switch]$Doctor,

    [Parameter(ParameterSetName = 'Capabilities')]
    [switch]$Capabilities,

    [string]$LocalAiExe,

    [switch]$DryRun
)

Set-StrictMode -Version Latest

# --- helpers ---------------------------------------------------------------
function Note($msg) { [Console]::Error.WriteLine($msg) }

function Write-Envelope($obj, [int]$exitCode) {
    # Exactly one JSON object on stdout; then exit with the given code.
    $obj | ConvertTo-Json -Depth 20 -Compress
    exit $exitCode
}

function Resolve-LocalAi {
    param([string]$Override)

    if ($Override) {
        if (Test-Path -LiteralPath $Override) { return (Resolve-Path -LiteralPath $Override).Path }
        Note "Specified -LocalAiExe not found: $Override"
        return $null
    }
    if ($env:LOCALAI_EXE -and (Test-Path -LiteralPath $env:LOCALAI_EXE)) {
        return (Resolve-Path -LiteralPath $env:LOCALAI_EXE).Path
    }
    if ($env:LOCALAI_HOME) {
        $cand = Join-Path $env:LOCALAI_HOME ".venv\Scripts\localai.exe"
        if (Test-Path -LiteralPath $cand) { return (Resolve-Path -LiteralPath $cand).Path }
    }
    $onPath = Get-Command localai -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $default = "C:\Dev\MyRepos\LocalAIExecution\.venv\Scripts\localai.exe"
    if (Test-Path -LiteralPath $default) { return $default }

    return $null
}

# Actionable messages for LocalAIExecution's documented exit codes.
$exitMap = @{
    0 = 'success'
    1 = 'unexpected error (file an issue with the stderr message)'
    2 = 'invalid arguments (sizes must be multiples of 16; check --steps/--preset)'
    3 = 'CUDA/torch unavailable or wrong build (run with -Doctor; reinstall torch from the cu128 index)'
    4 = 'no NVIDIA GPU detected (install the driver; ensure nvidia-smi is on PATH)'
    5 = 'CUDA out of memory (reduce -Width/-Height/-Batch, or lower offload)'
    6 = 'gated model / token denied (set HF_TOKEN or run huggingface-cli login; accept the model license)'
    7 = 'network / download failure (check connectivity; after the first download it runs offline)'
    8 = 'unknown capability or model (run with -Capabilities to list valid ids)'
}

# --- determine mode --------------------------------------------------------
$mode = $PSCmdlet.ParameterSetName  # Generate | Doctor | Capabilities

if ($mode -eq 'Generate' -and [string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Envelope ([ordered]@{
        ok       = $false
        exitCode = 2
        mode     = 'Generate'
        error    = 'A -Prompt is required for generation (or use -Doctor / -Capabilities).'
    }) 2
}

# --- discover the external CLI --------------------------------------------
$exe = Resolve-LocalAi -Override $LocalAiExe
if (-not $exe) {
    Write-Envelope ([ordered]@{
        ok       = $false
        exitCode = 127
        mode     = $mode
        error    = "localai CLI not found. Install LocalAIExecution (its own repo) and either add its " +
                   ".venv\Scripts to PATH, or set LOCALAI_HOME to the repo root, or LOCALAI_EXE to localai.exe."
    }) 127
}
Note "Using localai: $exe"

# --- build the argument vector --------------------------------------------
switch ($mode) {
    'Doctor'       { $argv = @('doctor', '--json') }
    'Capabilities' { $argv = @('capabilities', '--json') }
    default {
        $argv = @('generate', $Prompt, '--json')
        if ($PSBoundParameters.ContainsKey('Model'))     { $argv += @('--model', $Model) }
        if ($PSBoundParameters.ContainsKey('Steps'))     { $argv += @('--steps', "$Steps") }
        if ($PSBoundParameters.ContainsKey('Preset'))    { $argv += @('--preset', $Preset) }
        if ($PSBoundParameters.ContainsKey('Seed'))      { $argv += @('--seed', "$Seed") }
        if ($PSBoundParameters.ContainsKey('Width'))     { $argv += @('--width', "$Width") }
        if ($PSBoundParameters.ContainsKey('Height'))    { $argv += @('--height', "$Height") }
        if ($PSBoundParameters.ContainsKey('Batch'))     { $argv += @('--batch', "$Batch") }
        if ($PSBoundParameters.ContainsKey('OutputDir')) { $argv += @('--output-dir', $OutputDir) }
    }
}

$fmtArgs = ($argv | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
$display = '"{0}" {1}' -f $exe, $fmtArgs

if ($DryRun) {
    Write-Envelope ([ordered]@{
        ok      = $true
        dryRun  = $true
        mode    = $mode
        exe     = $exe
        command = $display
    }) 0
}

# --- run, capturing stdout / stderr / exit code separately -----------------
$outFile = [System.IO.Path]::GetTempFileName()
$errFile = [System.IO.Path]::GetTempFileName()
$code = $null
try {
    & $exe @argv 1> $outFile 2> $errFile
    $code = $LASTEXITCODE
}
catch {
    $code = 1
    Note "Failed to launch localai: $($_.Exception.Message)"
}
$stdout = ''
$stderr = ''
if (Test-Path -LiteralPath $outFile) { $stdout = (Get-Content -Raw -LiteralPath $outFile -ErrorAction SilentlyContinue) }
if (Test-Path -LiteralPath $errFile) { $stderr = (Get-Content -Raw -LiteralPath $errFile -ErrorAction SilentlyContinue) }
Remove-Item -LiteralPath $outFile, $errFile -ErrorAction SilentlyContinue
if ($null -eq $stdout) { $stdout = '' }
if ($null -eq $stderr) { $stderr = '' }

# --- map the result --------------------------------------------------------
if ($code -eq 0) {
    $parsed = $null
    try { $parsed = $stdout | ConvertFrom-Json -ErrorAction Stop }
    catch {
        Write-Envelope ([ordered]@{
            ok       = $false
            exitCode = 1
            mode     = $mode
            command  = $display
            error    = "localai exited 0 but its stdout was not valid JSON."
            stdout   = $stdout
            stderr   = $stderr
        }) 1
    }

    $images = @()
    if ($mode -eq 'Generate' -and ($parsed.PSObject.Properties.Name -contains 'artifacts')) {
        $images = @($parsed.artifacts | ForEach-Object { $_.path })
    }

    Write-Envelope ([ordered]@{
        ok       = $true
        exitCode = 0
        mode     = $mode
        command  = $display
        images   = $images
        result   = $parsed
    }) 0
}
else {
    $known = if ($exitMap.ContainsKey([int]$code)) { $exitMap[[int]$code] } else { "exit code $code" }
    $firstErrLine = ($stderr -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
    $message = if ($firstErrLine) { "$known — $firstErrLine" } else { $known }
    Write-Envelope ([ordered]@{
        ok       = $false
        exitCode = [int]$code
        mode     = $mode
        command  = $display
        error    = $message
        stderr   = $stderr
    }) ([int]$code)
}
