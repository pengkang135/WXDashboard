<#
wx_guardian.ps1 — Kill stale wx-cli daemon processes running longer than 3 minutes.
Runs as a scheduled task every 2 minutes.
#>

$MAX_AGE_MINUTES = 3
$LOG_PATH = Join-Path $PSScriptRoot "..\data\wx_guardian.log"

$now = Get-Date
$killed = $false

# Find all wx.exe processes from the wx-cli package (not WeChat client)
$procs = Get-WmiObject Win32_Process -Filter "Name='wx.exe'" | Where-Object {
    $_.CommandLine -match 'wx-cli' -or $_.CommandLine -match 'wx-cli-win32'
}

foreach ($p in $procs) {
    $startTime = [Management.ManagementDateTimeConverter]::ToDateTime($p.CreationDate)
    $age = ($now - $startTime).TotalMinutes

    if ($age -gt $MAX_AGE_MINUTES) {
        $msg = "[{0:yyyy-MM-dd HH:mm:ss}] KILL wx-cli PID={1} Age={2:F1}min Cmd={3}" -f $now, $p.ProcessId, $age, $p.CommandLine
        Add-Content -Path $LOG_PATH -Value $msg -Encoding UTF8
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $killed = $true
    }
}

if ($killed) {
    Write-Output "wx-cli guardian: killed stale processes, see $LOG_PATH"
} else {
    Write-Output "wx-cli guardian: OK"
}
