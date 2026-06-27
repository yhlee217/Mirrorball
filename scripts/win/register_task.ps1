# 매일 새벽 동기화를 Windows Task Scheduler 에 등록.
# 관리자 PowerShell 에서 실행:  powershell -ExecutionPolicy Bypass -File scripts\win\register_task.ps1
# 시간 바꾸려면:               ... register_task.ps1 -Time 02:30

param(
  [string]$Time = "03:10",
  [string]$TaskName = "Mirrorball-HandSOS-Sync"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$bat  = Join-Path $repo "scripts\win\run_sync.bat"
if (-not (Test-Path $bat)) { throw "run_sync.bat 없음: $bat" }

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
# 절전 중이면 깨워서 실행 + 예약 시각 놓쳤으면 가능할 때 실행
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
            -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
            -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "핸드SOS 매일 자동 동기화" -Force | Out-Null

Write-Host "[OK] 등록 완료: 매일 $Time → $bat"
Write-Host "확인:   schtasks /Query /TN $TaskName"
Write-Host "즉시 실행: schtasks /Run /TN $TaskName"
Write-Host ""
Write-Host "참고: PC가 그 시각에 켜져 있어야 합니다(절전은 깨우지만 완전 종료는 불가)."
Write-Host "      로그인 없이 돌리려면 작업 스케줄러 GUI에서 '사용자 로그온 여부와 관계없이 실행'으로 변경하세요."
