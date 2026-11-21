param(
    [string]$Python = '.venv/Scripts/python.exe',
    [string]$ModelRoot = "$env:USERPROFILE/.cache/huggingface",
    [int]$Port = 8000,
    [string]$DataRoot = '',
    [switch]$CheckOnly,
    [switch]$Warmup
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $DataRoot) { $DataRoot = $repo }
$data = (Resolve-Path -LiteralPath $DataRoot).Path
$snapshot = Join-Path $data 'data/demo/smartlibai-fasttrack/smartlibai-demo-v4/snapshot/smartlibai-demo-v4'
foreach ($name in @('manifest.json', 'catalog.sqlite', 'books.faiss', 'mapping.jsonl')) {
    if (-not (Test-Path -LiteralPath (Join-Path $snapshot $name) -PathType Leaf)) {
        throw "Missing $name under $snapshot. Check that your Git checkout includes the complete P3 demo data."
    }
}
if ($CheckOnly) {
    $manifest = Get-Content -LiteralPath (Join-Path $snapshot 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.snapshot_id -ne 'smartlibai-demo-v4') { throw 'Wrong snapshot' }
    foreach ($file in $manifest.files) {
        $path = Join-Path $snapshot $file.path
        if ((Get-Item -LiteralPath $path).Length -ne $file.size_bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
            throw "Snapshot checksum mismatch: $path"
        }
    }
    Write-Output "PASS: snapshot and SHA-256 resolved under $snapshot"
    return
}
$saved = @{}
foreach ($name in @('PYTHONPATH','SMARTLIBAI_DEMO_SNAPSHOT','CLASSROOM_DEMO_SNAPSHOT','MODEL_ROOT','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Push-Location $repo
try {
    $env:PYTHONPATH = "$repo/api;$repo/pipeline"
    $env:SMARTLIBAI_DEMO_SNAPSHOT = $snapshot
    $env:CLASSROOM_DEMO_SNAPSHOT = ''
    $env:MODEL_ROOT = (Resolve-Path -LiteralPath $ModelRoot).Path
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    & $Python -c 'import sys; print(sys.executable)'
    if ($LASTEXITCODE -ne 0) { throw 'Python failed to start. Create a working venv or pass -Python.' }
    if ($Warmup) {
        & $Python (Join-Path $PSScriptRoot 'scripts/p3_serve_demo.py') --port $Port
    } else {
        & $Python -m uvicorn src.main:app --host 127.0.0.1 --port $Port
    }
    if ($LASTEXITCODE -ne 0) { throw "API exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
    foreach ($name in $saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process')
    }
}
