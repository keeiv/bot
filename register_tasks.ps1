<#
.SYNOPSIS
  Register scheduled task to run the project's run_bot.bat at startup and logon.

USAGE (Run as Administrator):
  Right-click -> Run with PowerShell (Run as administrator)
  or in an elevated PowerShell:
    powershell -ExecutionPolicy Bypass -File .\register_tasks.ps1
#>

Set-StrictMode -Version Latest

$bat = Join-Path $PSScriptRoot 'run_bot.bat'
if (-not (Test-Path $bat)) {
    Write-Error "Batch file not found: $bat"
    exit 1
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$bat`""
$trigStartup = New-ScheduledTaskTrigger -AtStartup
$trigLogon = New-ScheduledTaskTrigger -AtLogOn
$triggers = @($trigStartup, $trigLogon)

try {
    Register-ScheduledTask -TaskName 'NewBot_AutoStart' -Action $action -Trigger $triggers -RunLevel Highest -Force -ErrorAction Stop
    Write-Output "Scheduled task 'NewBot_AutoStart' registered successfully."
} catch {
    Write-Error "Failed to register scheduled task: $_"
    exit 1
}

Get-ScheduledTask -TaskName 'NewBot_AutoStart' | Format-List *
