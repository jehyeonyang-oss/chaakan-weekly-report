$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = (& python -c "import sys; print(sys.executable)").Trim()
$pythonWindowless = Join-Path (Split-Path $pythonPath -Parent) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw 'pythonw.exe not found' }
$taskName = 'ChaakanWeeklyReportSync'
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Task already exists; inspect before replacing' }
$syncScript = Join-Path $projectRoot 'tools\sync.py'
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument ('"' + $syncScript + '"') -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Sync team workbooks and existing report data to GitHub Pages every 2 minutes' | Select-Object TaskName,State
Start-ScheduledTask -TaskName $taskName
[xml]$definition = Export-ScheduledTask -TaskName $taskName
$definition.Task.Triggers.TimeTrigger.Repetition
