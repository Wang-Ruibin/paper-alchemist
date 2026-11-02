$ErrorActionPreference = 'Stop'
$runtimeRoot = if ($env:PAPER_ALCHEMIST_RUNTIME) { [IO.Path]::GetFullPath($env:PAPER_ALCHEMIST_RUNTIME) } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) 'AppData\Local\PaperAlchemist\runtime' }
$digest = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt') -Algorithm SHA256).Hash.ToLowerInvariant().Substring(0,16)
$pythonPath = Join-Path $runtimeRoot "envs\$digest\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Plugin runtime is not ready. Ask Codex to run runtime/setup.ps1 during installation.' }
& $pythonPath -I (Join-Path (Split-Path -Parent $PSScriptRoot) 'skills\paper-alchemist\scripts\run.py') @args
exit $LASTEXITCODE
