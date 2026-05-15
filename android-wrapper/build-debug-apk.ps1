Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "JARVIS Phase 19 debug APK build workflow"
Write-Host "Safety: no deploy, no production signing, no database mutation."

if (-not (Get-Command gradle -ErrorAction SilentlyContinue)) {
    throw "Gradle is not available. Install Android Studio/Gradle before running this workflow."
}

if (-not $env:ANDROID_HOME -and -not $env:ANDROID_SDK_ROOT) {
    throw "ANDROID_HOME or ANDROID_SDK_ROOT is not configured."
}

Push-Location $PSScriptRoot
try {
    gradle :app:assembleDebug
    Write-Host "Debug APK expected at android-wrapper/app/build/outputs/apk/debug/app-debug.apk"
}
finally {
    Pop-Location
}
