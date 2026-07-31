$ErrorActionPreference = "Stop"

$modelUrl = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
$modelDir = Join-Path $PSScriptRoot "..\models\qwen2.5-0.5b-gguf"
$modelPath = Join-Path $modelDir "qwen2.5-0.5b-instruct-q4_k_m.gguf"

New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
if (Test-Path -LiteralPath $modelPath) {
    Write-Host "Model already exists: $modelPath"
    exit 0
}

Write-Host "Downloading compact Qwen2.5-0.5B Q4 model..."
Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath
Write-Host "Saved: $modelPath"
