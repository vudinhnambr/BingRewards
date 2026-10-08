# Script tu dong dang ky Windows Task Scheduler cho Bing Rewards Bot

$TaskName = "BingRewardsDaily"
$WorkingDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$PythonExe = "$WorkingDir\.venv\Scripts\python.exe"
$Arguments = "main.py --all --headless"
$RunTime = "19:00"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "   THIET LAP TU DONG CHAY HANG NGAY TREN WINDOWS     " -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "Ten tac vu: $TaskName"
Write-Host "Thoi gian chay: Hang ngay luc $RunTime (7h toi)"
Write-Host "Thu muc: $WorkingDir"
Write-Host "Che do: An ngam (Headless) - 1 lan / ngay"
Write-Host ""

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $WorkingDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Tu dong kiem diem Microsoft Rewards hang ngay luc 19:00." | Out-Null
    Write-Host "[THANH CONG] Da tao Task Scheduler '$TaskName' thanh cong!" -ForegroundColor Green
    Write-Host "Bot se tu dong chay vao luc $RunTime (7h toi) moi ngay (1 lan/ngay)." -ForegroundColor Green
}
catch {
    Write-Host "[LOI] Khong the tao task: $_" -ForegroundColor Red
    Write-Host "Vui long chay script nay voi quyen 'Run as Administrator'." -ForegroundColor Yellow
}
