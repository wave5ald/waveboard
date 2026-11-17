# Builds Wave Board and its installer, then prints the update manifest entry.
#
#   .\build.ps1                 # version from main.py
#   .\build.ps1 -Version 1.3.0  # stamp a different version
#   .\build.ps1 -WriteManifest  # also refresh version.json with size + SHA-256
[CmdletBinding()]
param(
    [string]$Version = "",
    [switch]$WriteManifest
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $Version) {
    $Version = (Select-String -Path "main.py" -Pattern '^APP_VERSION = "([^"]+)"').Matches[0].Groups[1].Value
    if (-not $Version) { throw "Could not read APP_VERSION from main.py" }
}

$installerSource = Get-Content "installer.py" -Raw
$installerSource = [regex]::Replace($installerSource, '(?m)^VERSION = "[^"]+"', "VERSION = `"$Version`"")
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "installer.py"), $installerSource, (New-Object System.Text.UTF8Encoding($false)))
$mainSource = Get-Content "main.py" -Raw
$mainSource = [regex]::Replace($mainSource, '(?m)^APP_VERSION = "[^"]+"', "APP_VERSION = `"$Version`"")
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "main.py"), $mainSource, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Building Wave Board $Version"

python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Wave Board" `
    --icon icon.ico --distpath dist --workpath build main.py
if ($LASTEXITCODE -ne 0) { throw "App build failed" }

python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Wave Board Setup" `
    --icon icon.ico --add-data "icon.ico;." --add-data "dist\Wave Board.exe;payload" --distpath dist --workpath build_installer installer.py
if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }

$setup = Join-Path $PWD "dist\Wave Board Setup.exe"
$asset = Join-Path $PWD ("dist\WaveBoard-$Version-Setup.exe")
Copy-Item $setup $asset -Force
$digest = (Get-FileHash $asset -Algorithm SHA256).Hash.ToLowerInvariant()
$size = (Get-Item $asset).Length

$manifest = [ordered]@{
    version       = $Version
    download_url  = "https://github.com/wave5ald/waveboard/releases/download/v$Version/WaveBoard-$Version-Setup.exe"
    release_notes = ""
    release_page  = "https://github.com/wave5ald/waveboard/releases"
    sha256        = $digest
    size_bytes    = $size
}

if ($WriteManifest) {
    $existing = if (Test-Path "version.json") { Get-Content "version.json" -Raw | ConvertFrom-Json } else { $null }
    if (-not $manifest.release_notes) {
        $manifest.release_notes = if ($existing) { $existing.release_notes } else { "Bug fixes and improvements" }
    }
    $json = $manifest | ConvertTo-Json -Depth 4
    $json = $json -replace '(?m)^(\s*"[^"]+"):\s+', '$1: '
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "version.json"), $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Updated version.json"
}

Write-Host ""
Write-Host "Asset: $asset"
Write-Host "Size:  $size bytes"
Write-Host "SHA256: $digest"
Write-Host ""
Write-Host ($manifest | ConvertTo-Json -Depth 4)
