$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentPid = $PID
$managedPorts = @(8000, 3000)
$global:shutdownRequested = $false

# Track child process IDs so we can kill them instantly on exit
$global:trackedPids = [System.Collections.Generic.List[int]]::new()

function Stop-ProcessTree {
    param([int]$ProcessId)
    if (-not $ProcessId -or $ProcessId -eq $currentPid) { return }
    $null = & cmd.exe /c "taskkill /PID $ProcessId /T /F >NUL 2>&1"
}

function Get-PortPids {
    param([int]$Port)
    $pids = @()
    foreach ($line in (netstat -ano -p tcp | Select-String ":$Port\s")) {
        $pidToken = ($line -split "\s+")[-1]
        if ($pidToken -match "^\d+$") {
            $pidValue = [int]$pidToken
            if ($pidValue -gt 0 -and $pidValue -ne $currentPid) { $pids += $pidValue }
        }
    }
    $pids | Select-Object -Unique
}

function Cleanup-Fast {
    # Kill tracked PIDs immediately (no port scan needed — we know exact PIDs)
    foreach ($pid in $global:trackedPids) {
        Stop-ProcessTree -ProcessId $pid
    }
    # Also stop any lingering PS jobs
    foreach ($job in (Get-Job -ErrorAction SilentlyContinue | Where-Object { $_.Name -in @("backend","frontend") })) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}

function Cleanup-Ports {
    foreach ($port in $managedPorts) {
        foreach ($portPid in (Get-PortPids -Port $port)) {
            Write-Host "Freeing port $port (PID $portPid) ..." -ForegroundColor Magenta
            Stop-ProcessTree -ProcessId $portPid
        }
    }
}

# Kill any other running start.ps1 instances
Get-WmiObject Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" |
    Where-Object { $_.ProcessId -ne $currentPid -and $_.CommandLine -like "*start.ps1*" } |
    ForEach-Object {
        Write-Host "Killing previous start.ps1 instance (PID $($_.ProcessId)) ..." -ForegroundColor Magenta
        Stop-ProcessTree -ProcessId $_.ProcessId
    }

# Free ports before starting
Cleanup-Ports
Start-Sleep -Milliseconds 400

# Capture Ctrl+C for immediate shutdown
$cancelEvent = Register-ObjectEvent -InputObject ([Console]) -EventName CancelKeyPress -Action {
    $eventArgs.Cancel = $true
    $global:shutdownRequested = $true
}

Write-Host "Starting backend (uvicorn) ..." -ForegroundColor Cyan
$backend = Start-Job -Name "backend" -ScriptBlock {
    param($r)
    Set-Location $r
    & ".\venv_copilot\Scripts\python.exe" -m uvicorn api.main:app --reload --port 8000 2>&1
} -ArgumentList $root

Write-Host "Starting frontend (npm run dev) ..." -ForegroundColor Cyan
$frontend = Start-Job -Name "frontend" -ScriptBlock {
    param($r)
    Set-Location "$r\frontend"
    npm run dev 2>&1
} -ArgumentList $root

# Give jobs a moment to spin up their child processes, then capture their PIDs
Start-Sleep -Milliseconds 800
foreach ($port in $managedPorts) {
    foreach ($portPid in (Get-PortPids -Port $port)) {
        if (-not $global:trackedPids.Contains($portPid)) {
            $global:trackedPids.Add($portPid)
        }
    }
}

Write-Host ""
Write-Host "Both servers are running. Press Ctrl+C to stop." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""

function Write-JobOutput {
    param($Job, [string]$Prefix, [string]$Color)
    foreach ($item in (Receive-Job -Job $Job -ErrorAction SilentlyContinue)) {
        $line = $null
        if ($item -is [System.Management.Automation.ErrorRecord]) { $line = $item.Exception.Message }
        elseif ($item -is [System.Management.Automation.WarningRecord]) { $line = $item.Message }
        elseif ($item -is [System.Management.Automation.VerboseRecord]) { $line = $item.Message }
        else { $line = [string]$item }
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -eq "System.Management.Automation.RemoteException") { continue }
        Write-Host ("[{0}] {1}" -f $Prefix, $line) -ForegroundColor $Color
    }
}

try {
    while (-not $global:shutdownRequested) {
        Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
        Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"

        # Re-capture PIDs periodically (processes may start after initial check)
        foreach ($port in $managedPorts) {
            foreach ($portPid in (Get-PortPids -Port $port)) {
                if (-not $global:trackedPids.Contains($portPid)) {
                    $global:trackedPids.Add($portPid)
                }
            }
        }

        if ($backend.State -in @("Failed","Stopped","Completed") -or
            $frontend.State -in @("Failed","Stopped","Completed")) {
            $global:shutdownRequested = $true
        }
        Start-Sleep -Milliseconds 200
    }
}
finally {
    Write-Host "`nStopping servers..." -ForegroundColor Red
    Unregister-Event -SourceIdentifier $cancelEvent.Name -ErrorAction SilentlyContinue
    Remove-Job -Id $cancelEvent.Id -Force -ErrorAction SilentlyContinue
    Cleanup-Fast
    Write-Host "Stopped." -ForegroundColor Green
}
