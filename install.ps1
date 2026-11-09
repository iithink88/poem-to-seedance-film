# poem-to-seedance-film installer for Windows (PowerShell 5.1+)
# ASCII only on purpose: avoids encoding issues with non-UTF8 consoles.
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$skillName = "poem-to-seedance-film"
$target = Join-Path $env:USERPROFILE (".workbuddy\skills\" + $skillName)

Write-Host "== poem-to-seedance-film installer =="
Write-Host "Source : $src"
Write-Host "Target : $target"

if (-not (Test-Path (Join-Path $src "SKILL.md"))) {
    Write-Error "SKILL.md not found next to this script. Keep the extracted folder intact."
    exit 1
}

if (Test-Path $target) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $bak = "$target.bak-$stamp"
    Move-Item -Path $target -Destination $bak
    Write-Host "Existing install backed up to: $bak"
}

New-Item -ItemType Directory -Path $target -Force | Out-Null
$items = @("SKILL.md", "README.md", "INSTALL.md", "LICENSE", "scripts", "references", "examples")
foreach ($i in $items) {
    $p = Join-Path $src $i
    if (Test-Path $p) {
        Copy-Item -Path $p -Destination $target -Recurse -Force
        Write-Host "  copied $i"
    }
}

Write-Host ""
Write-Host "Installed. Now checking dependencies..."

$py = $null
$candidates = @(
    (Join-Path $env:USERPROFILE ".workbuddy\binaries\python\envs\default\Scripts\python.exe"),
    "python", "python3"
)
foreach ($c in $candidates) {
    try { & $c --version 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
}
if ($py) { Write-Host "  Python : OK ($py)" } else { Write-Host "  Python : NOT FOUND - install Python 3.10+" }

try { & ffmpeg -version 2>$null | Out-Null; $ff = ($LASTEXITCODE -eq 0) } catch { $ff = $false }
if ($ff) { Write-Host "  ffmpeg : OK" } else { Write-Host "  ffmpeg : NOT FOUND - install ffmpeg and add it to PATH" }

Write-Host ""
Write-Host "Done. Restart WorkBuddy, then say: 把《山居秋暝》做成古诗词短片"
Write-Host "Full guide: INSTALL.md"
