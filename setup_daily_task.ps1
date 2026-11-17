<#
.SYNOPSIS
    Registers a Windows Scheduled Task to run Email Organizer daily.

.DESCRIPTION
    Creates a scheduled task that executes 'run_daily.bat' once every day at the specified time.
    Also supports removing the task or running it on demand.

.PARAMETER Time
    The time of day to trigger the task (default: "08:00"). Format: "HH:mm" (24-hour).

.PARAMETER Uninstall
    If specified, removes the scheduled task.

.PARAMETER RunNow
    If specified, triggers the scheduled task immediately for testing.
#>

[CmdletBinding()]
param (
    [string]$Time = "08:00",
    [switch]$Uninstall,
    [switch]$RunNow
)

$TaskName = "EmailOrganizerDaily"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "run_daily.bat"

if ($Uninstall) {
    Write-Host "Removing scheduled task: $TaskName..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Scheduled task '$TaskName' removed successfully." -ForegroundColor Green
    exit 0
}

if ($RunNow) {
    Write-Host "Triggering scheduled task '$TaskName' now..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[OK] Task triggered." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $BatPath)) {
    Write-Error "Runner script not found at '$BatPath'."
    exit 1
}

Write-Host "Setting up Daily Email Organizer Scheduled Task..." -ForegroundColor Cyan
Write-Host "  Task Name: $TaskName"
Write-Host "  Trigger  : Daily at $Time"
Write-Host "  Action   : $BatPath"

$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($Time, "HH:mm", $null))
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    # Unregister existing if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName `
                           -Action $Action `
                           -Trigger $Trigger `
                           -Settings $Settings `
                           -Description "Automated Daily Gmail Organizer & Digest" | Out-Null

    Write-Host ""
    Write-Host "[OK] Successfully registered scheduled task '$TaskName'!" -ForegroundColor Green
    Write-Host "Your emails will now be automatically organized every day at $Time." -ForegroundColor Green
    Write-Host "Digest summaries will be generated in: $ScriptDir\daily_summaries" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To test run now: .\setup_daily_task.ps1 -RunNow" -ForegroundColor DarkGray
    Write-Host "To remove task:  .\setup_daily_task.ps1 -Uninstall" -ForegroundColor DarkGray
} catch {
    Write-Error "Failed to register scheduled task: $_"
}
