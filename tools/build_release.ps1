<#
.SYNOPSIS
    Build and verify one complete de-Mail Desktop Windows release.

.DESCRIPTION
    Run from the repository root. Every gate stops on failure so an old frozen
    executable can never be wrapped in a newly numbered installer.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Step {
    param([string]$Name, [scriptblock]$Work)
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Work
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

$releaseRoot = Split-Path -Parent $PSScriptRoot
Push-Location $releaseRoot
try {
    $python = Join-Path $releaseRoot '.venv\Scripts\python.exe'
    $deploy = Join-Path $releaseRoot '.venv\Scripts\pyside6-deploy.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "The project virtual environment is missing: $python"
    }
    if (-not (Test-Path -LiteralPath $deploy -PathType Leaf)) {
        throw "The deployment command is missing: $deploy"
    }

    Step "Checking synchronized release versions" { & $python tools\check_version.py }
    $versionOutput = & $python -c "from tools.versioning import read_version; print(read_version())"
    if ($LASTEXITCODE -ne 0 -or $null -eq $versionOutput) {
        throw "The authoritative version could not be read"
    }
    $version = ($versionOutput | Select-Object -Last 1).Trim()
    if ([string]::IsNullOrWhiteSpace($version)) {
        throw "The authoritative version is blank"
    }
    Write-Host "    version: $version"

    Step "Linting release sources" { & $python -m ruff check . }
    Step "Running the complete test suite" { & $python -m pytest }

    $payload = Join-Path $releaseRoot 'dist\de-Mail Desktop.dist'
    $payloadFull = [IO.Path]::GetFullPath($payload)
    $distFull = [IO.Path]::GetFullPath((Join-Path $releaseRoot 'dist')) + [IO.Path]::DirectorySeparatorChar
    if (-not $payloadFull.StartsWith($distFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear an output directory outside dist: $payloadFull"
    }
    if (Test-Path -LiteralPath $payloadFull) {
        Remove-Item -LiteralPath $payloadFull -Recurse -Force
    }

    Step "Building the standalone application" {
        $env:NUITKA_CACHE_DIR = Join-Path $releaseRoot '.nuitka-cache'
        $env:PYTHONPATH = Join-Path $releaseRoot 'src'
        & $deploy --config-file pysidedeploy.spec --extra-ignore-dirs=tools --force
    }

    $exe = Join-Path $payloadFull 'main.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "The standalone builder produced no executable: $exe"
    }
    Step "Checking the standalone Windows version" {
        $builtVersion = (Get-Item -LiteralPath $exe).VersionInfo.FileVersion
        Write-Host "    main.exe reports $builtVersion"
        if ($builtVersion -ne "$version.0") {
            throw "main.exe is $builtVersion, expected $version.0"
        }
    }

    Step "Self-testing the frozen application" {
        $process = Start-Process -FilePath $exe -ArgumentList '--selftest' `
            -Wait -PassThru -NoNewWindow
        if ($process.ExitCode -ne 0) {
            throw "Frozen self-test failed with exit code $($process.ExitCode)"
        }
    }
    Step "Launch-testing the frozen application" {
        $process = Start-Process -FilePath $exe -ArgumentList '--launchtest' `
            -Wait -PassThru -NoNewWindow
        if ($process.ExitCode -ne 0) {
            throw "Frozen launch test failed with exit code $($process.ExitCode)"
        }
    }

    Step "Building the setup executable" { & $python tools\build_installer.py }
    $setup = Join-Path $releaseRoot "dist\installer\de-Mail-Desktop-Setup-$version.exe"
    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
        throw "The installer compiler produced no setup executable: $setup"
    }
    Step "Checking the setup Windows version" {
        $setupVersion = (Get-Item -LiteralPath $setup).VersionInfo.FileVersion
        Write-Host "    setup reports $setupVersion"
        if ($setupVersion -notlike "$version*") {
            throw "Setup is $setupVersion, expected $version"
        }
    }

    $checksumPath = Join-Path $releaseRoot 'dist\installer\SHA256SUMS.txt'
    $hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        $checksumPath,
        "$hash  $([System.IO.Path]::GetFileName($setup))`n",
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host ""
    Write-Host "Verified release: $setup" -ForegroundColor Green
    Write-Host "Checksum: $checksumPath" -ForegroundColor Green
}
finally {
    Pop-Location
}
