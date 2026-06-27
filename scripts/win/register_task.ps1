# Register the daily HandSOS sync as a Windows Scheduled Task.
# Run in an ADMIN PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\win\register_task.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\win\register_task.ps1 -Time 02:30

param(
  [string]$Time = "03:10",
  [string]$TaskName = "Mirrorball-HandSOS-Sync"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$bat  = Join-Path $repo "scripts\win\run_sync.bat"
if (-not (Test-Path $bat)) { throw "run_sync.bat not found: $bat" }

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
            -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
            -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "Mirrorball HandSOS daily sync" -Force | Out-Null

Write-Host "[OK] Registered: daily $Time -> $bat"
Write-Host "Check:   schtasks /Query /TN $TaskName"
Write-Host "Run now: schtasks /Run /TN $TaskName"
Write-Host ""
Write-Host "Note: the PC must be ON at that time. Sleep is woken (-WakeToRun), but a full shutdown is not."
Write-Host "To run without being logged in, open Task Scheduler GUI and set 'Run whether user is logged on or not'."
