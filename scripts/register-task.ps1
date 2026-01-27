$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File C:\Users\Tenormusica\x-auto\scripts\wrapper.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At '12:00'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName 'X-Auto-Posting' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'X Auto Posting System - Daily at 12:00' -Force

Write-Host "Task 'X-Auto-Posting' registered successfully for 12:00 daily"
