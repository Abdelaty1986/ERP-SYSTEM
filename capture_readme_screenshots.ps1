$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = "C:\Users\Hany.Abdelatty\AppData\Local\Programs\Python\Python313\python.exe"
$browserCandidates = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Google\Chrome\Application\chrome.exe"
)
$browserExe = $browserCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browserExe) {
    throw "No supported browser found for screenshots."
}

$outputDir = Join-Path $projectRoot "static\readme"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$profileDir = Join-Path $env:TEMP "erp-readme-browser-profile"
if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
}
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

& $pythonExe "generate_readme_snapshots.py" | Out-Null

$htmlDir = Join-Path $outputDir "html"
$targets = @(
    @{ Html = (Join-Path $htmlDir "dashboard.html"); File = "dashboard.png" },
    @{ Html = (Join-Path $htmlDir "journal.html"); File = "journal.png" },
    @{ Html = (Join-Path $htmlDir "sales.html"); File = "sales.png" },
    @{ Html = (Join-Path $htmlDir "purchases.html"); File = "purchases.png" },
    @{ Html = (Join-Path $htmlDir "trial-balance.html"); File = "trial-balance.png" }
)

foreach ($target in $targets) {
    $pageUri = "file:///" + ($target.Html -replace "\\", "/")
    & $browserExe --headless --disable-gpu --hide-scrollbars --window-size=1440,2200 --virtual-time-budget=5000 --user-data-dir=$profileDir --screenshot="$outputDir\$($target.File)" $pageUri | Out-Null
}
