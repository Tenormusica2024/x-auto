$action = New-ScheduledTaskAction -Execute "C:\Users\Tenormusica\.bun\bin\claude.exe" -Argument '--chrome --dangerously-skip-permissions -p "Execute x-auto like-back skill. Read C:\Users\Tenormusica\x-auto\skills\like-back\PROMPT.md and follow the instructions."'
$trigger = New-ScheduledTaskTrigger -Daily -At "21:30"
Register-ScheduledTask -TaskName "x-auto-like-back" -Action $action -Trigger $trigger -Description "x-auto like-back daily execution (21:30 JST)"
