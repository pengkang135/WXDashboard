# Register wxGuardian scheduled task: runs every 2 minutes, kills stale wx-cli processes
# Run once to install: powershell -File scripts\register_wx_guardian.ps1

$taskName = "wxGuardian"
$taskPath = "\OpenClaw\"
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
$silentPy = Join-Path $projectDir "scripts\wx_guardian_silent.py"

if (-not (Test-Path $pythonw)) {
    Write-Error "pythonw.exe not found at $pythonw — run 'python -m venv .venv' first"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "`"$silentPy`""

$trigger = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 2)

$settings = New-ScheduledTaskSettingsSet -Hidden `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -Compatibility Win8

$principal = New-ScheduledTaskPrincipal -UserId (whoami) `
    -LogonType Interactive -RunLevel Limited

$task = Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Force -ErrorAction SilentlyContinue

if ($task) {
    Write-Output "wxGuardian registered: every 2 min via $pythonw"
} else {
    Write-Output "wxGuardian: already exists or failed to create"
}
