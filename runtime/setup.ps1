param([switch]$ManagedPython)
$ErrorActionPreference = 'Stop'
$uvVersion = '0.13.6'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = if ($env:PAPER_ALCHEMIST_RUNTIME) { [IO.Path]::GetFullPath($env:PAPER_ALCHEMIST_RUNTIME) } else { Join-Path $env:LOCALAPPDATA 'PaperAlchemist\runtime' }
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$digest = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash.ToLowerInvariant().Substring(0,16)
$environmentPath = Join-Path $runtimeRoot "envs\$digest"
$pythonPath = Join-Path $environmentPath 'Scripts\python.exe'
$uvPath = Join-Path $runtimeRoot "uv-$uvVersion\uv.exe"
$lockPath = Join-Path $runtimeRoot '.setup-lock'
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
if (Test-Path -LiteralPath $lockPath) { throw 'Another setup is running. Retry when it finishes; inspect a stale lock before removing it.' }
New-Item -ItemType Directory -Path $lockPath -ErrorAction Stop | Out-Null
$stage = $null
$savedEnvironment = @{}
foreach ($name in @('UV_PYTHON_INSTALL_DIR','UV_CACHE_DIR','UV_NO_PROGRESS')) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
    $env:UV_CACHE_DIR = Join-Path $runtimeRoot 'cache'
    $env:UV_NO_PROGRESS = '1'
    if (-not (Test-Path -LiteralPath $uvPath)) {
        $architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        $platform = switch ($architecture) { 'X64' { 'windows-x86_64' }; 'ARM64' { 'windows-aarch64' }; default { throw "Unsupported Windows architecture: $architecture" } }
        $download = Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'downloads.tsv') -Delimiter "`t" | Where-Object platform -EQ $platform
        if (@($download).Count -ne 1) { throw 'Missing runtime download entry' }
        $stage = Join-Path $runtimeRoot ('.download-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage | Out-Null
        $archive = Join-Path $stage 'uv.zip'
        Invoke-WebRequest -Uri "https://github.com/astral-sh/uv/releases/download/$uvVersion/$($download.filename)" -OutFile $archive -UseBasicParsing
        if ((Get-Item -LiteralPath $archive).Length -ne [long]$download.bytes -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $download.sha256) { throw 'uv download checksum or size mismatch' }
        Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $stage 'unpacked')
        $binary = @(Get-ChildItem -LiteralPath (Join-Path $stage 'unpacked') -Filter uv.exe -Recurse -File)
        if ($binary.Count -ne 1) { throw 'Unexpected uv archive contents' }
        [IO.Directory]::CreateDirectory((Split-Path -Parent $uvPath)) | Out-Null
        Move-Item -LiteralPath $binary[0].FullName -Destination $uvPath
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        if (Test-Path -LiteralPath $environmentPath) { throw "Incomplete environment preserved: $environmentPath. Inspect it before retrying." }
        $created = $false
        if (-not $ManagedPython) {
            & $uvPath --no-config venv --python '>=3.11,<3.15' --python-preference system --no-python-downloads $environmentPath
            $created = $LASTEXITCODE -eq 0
        }
        if (-not $created) {
            & $uvPath --no-config venv --python 3.12 --managed-python $environmentPath
            if ($LASTEXITCODE -ne 0) { throw 'Private Python preparation failed' }
        }
    }
    & $uvPath --no-config pip install --python $pythonPath --link-mode copy --only-binary :all: --requirement $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency installation failed' }
    & $pythonPath -I (Join-Path $pluginRoot 'skills\paper-alchemist\scripts\run.py') --version
    if ($LASTEXITCODE -ne 0) { throw 'Plugin runtime verification failed' }
    $result = [ordered]@{ ready=$true; python=$pythonPath; runtime_root=$runtimeRoot; dependency_lock=$digest; uv_version=$uvVersion; system_path_changed=$false }
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeRoot 'runtime.json') -Encoding utf8
    $result | ConvertTo-Json
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    if ($stage -and (Test-Path -LiteralPath $stage)) {
        $resolvedStage = [IO.Path]::GetFullPath($stage)
        $expectedParent = [IO.Path]::GetFullPath($runtimeRoot).TrimEnd('\')
        if ([IO.Path]::GetDirectoryName($resolvedStage) -cne $expectedParent -or -not ([IO.Path]::GetFileName($resolvedStage).StartsWith('.download-'))) { throw 'Unexpected temporary cleanup path' }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
    Remove-Item -LiteralPath $lockPath
}
