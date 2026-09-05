# Script tu dong dang ky Windows Task Scheduler cho Bing Rewards Bot

$TaskName = "BingRewardsDaily"
$WorkingDir = "E:\BingRewards\BingRewards"
$PythonExe = "$WorkingDir\.venv\Scripts\python.exe"
$Arguments = "main.py --all --headless"
$RunTimeMorning = "07:45"
$RunTimeEvening = "20:30"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "   THIET LAP TU DONG CHAY HANG NGAY TREN WINDOWS     " -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "Ten tac vu: $TaskName"
Write-Host "Thoi gian chay: Hang ngay luc $RunTimeMorning va $RunTimeEvening"
Write-Host "Thu muc: $WorkingDir"
Write-Host "Che do: An ngam (Headless)"
Write-Host ""

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $WorkingDir
$Trigger1 = New-ScheduledTaskTrigger -Daily -At $RunTimeMorning
$Trigger2 = New-ScheduledTaskTrigger -Daily -At $RunTimeEvening
$Triggers = @($Trigger1, $Trigger2)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings -Description "Tu dong kiem diem Microsoft Rewards hang ngay." | Out-Null
    Write-Host "[THANH CONG] Da tao Task Scheduler '$TaskName' thanh cong!" -ForegroundColor Green
    Write-Host "Bot se tu dong chay vao luc $RunTimeMorning va $RunTimeEvening moi ngay." -ForegroundColor Green
}
catch {
    Write-Host "[LOI] Khong the tao task: $_" -ForegroundColor Red
    Write-Host "Vui long chay script nay voi quyen 'Run as Administrator'." -ForegroundColor Yellow
}
