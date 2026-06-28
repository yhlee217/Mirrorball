# Register the weekly discoverability(exposure) measurement as a Windows Scheduled Task.
# Run in an ADMIN PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\win\register_expose_task.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\win\register_expose_task.ps1 -Day Monday -Time 09:00 -Slug hayewoni

param(
  [string]$Day = "Monday",
  [string]$Time = "09:00",
  [string]$Slug = "hayewoni",
  [string]$TaskName = "Mirrorball-Expose-Weekly"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$bat  = Join-Path $repo "scripts\win\run_expose_auto.bat"
if (-not (Test-Path $bat)) { throw "run_expose_auto.bat not found: $bat" }

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`" $Slug" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
            -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
            -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "Mirrorball weekly discoverability measurement" -Force | Out-Null

Write-Host "[OK] Registered: weekly $Day $Time -> $bat $Slug"
Write-Host "Check:   schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "Run now: schtasks /Run /TN $TaskName"
Write-Host "Remove:  schtasks /Delete /TN $TaskName /F"
Write-Host "Log:     $repo\expose.log"
Write-Host ""
Write-Host "After it runs, the weekly KakaoTalk text is at clients\$Slug\kakao.txt."
Write-Host "Note: the PC must be ON at that time (sleep is woken via -WakeToRun, a full shutdown is not)."
Write-Host "To run when not logged in, open Task Scheduler GUI and set 'Run whether user is logged on or not'."
