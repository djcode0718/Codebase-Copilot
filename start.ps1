$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentPid = $PID
$managedJobNames = @("backend", "frontend")
$managedPorts = @(8000, 3000)
$global:shutdownRequested = $false

function Stop-ProcessTree {
    param([int]$ProcessId)

    if (-not $ProcessId -or $ProcessId -eq $currentPid) {
        return
    }

    # PID can disappear between netstat lookup and kill call; treat as benign.
    if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        return
    }

    $null = & cmd.exe /c "taskkill /PID $ProcessId /T /F >NUL 2>&1"
}

function Get-PortPids {
    param([int]$Port)

    $pids = @()
    foreach ($line in (netstat -ano -p tcp | Select-String ":$Port\s")) {
        $pidToken = ($line -split "\s+")[-1]
        if ($pidToken -match "^\d+$") {
            $pidValue = [int]$pidToken
            if ($pidValue -gt 0 -and $pidValue -ne $currentPid) {
                $pids += $pidValue
            }
        }
    }

    $pids | Select-Object -Unique
}

function Cleanup-ManagedProcesses {
    # Stop any known jobs first.
    foreach ($job in (Get-Job -ErrorAction SilentlyContinue | Where-Object { $_.Name -in $managedJobNames })) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }

    # Force-kill anything still attached to managed ports.
    foreach ($port in $managedPorts) {
        foreach ($portPid in (Get-PortPids -Port $port)) {
            Write-Host "Freeing port $port (PID $portPid) ..." -ForegroundColor Magenta
            Stop-ProcessTree -ProcessId $portPid
        }
    }
}

# Kill any other running start.ps1 instances.
Get-WmiObject Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" |
    Where-Object {
        $_.ProcessId -ne $currentPid -and
        $_.CommandLine -like "*start.ps1*"
    } | ForEach-Object {
        Write-Host "Killing previous start.ps1 instance (PID $($_.ProcessId)) ..." -ForegroundColor Magenta
        Stop-ProcessTree -ProcessId $_.ProcessId
    }

# Clean previous state and free ports before starting.
Cleanup-ManagedProcesses
Start-Sleep -Milliseconds 400

# Capture Ctrl+C and switch to immediate scripted shutdown.
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

Write-Host ""
Write-Host "Both servers are running. Press Ctrl+C to stop." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""

function Write-JobOutput {
    param(
        [Parameter(Mandatory = $true)]$Job,
        [Parameter(Mandatory = $true)][string]$Prefix,
        [Parameter(Mandatory = $true)][string]$Color
    )

    foreach ($item in (Receive-Job -Job $Job -ErrorAction SilentlyContinue)) {
        $line = $null

        if ($item -is [System.Management.Automation.ErrorRecord]) {
            $line = $item.Exception.Message
        }
        elseif ($item -is [System.Management.Automation.WarningRecord]) {
            $line = $item.Message
        }
        elseif ($item -is [System.Management.Automation.VerboseRecord]) {
            $line = $item.Message
        }
        else {
            $line = [string]$item
        }

        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        # Hide remoting wrapper noise; keep the actual app message lines.
        if ($line -eq "System.Management.Automation.RemoteException") {
            continue
        }

        Write-Host ("[{0}] {1}" -f $Prefix, $line) -ForegroundColor $Color
    }
}

try {
    while (-not $global:shutdownRequested) {
        Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
        Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"

        if ($backend.State -in @("Failed", "Stopped", "Completed") -or $frontend.State -in @("Failed", "Stopped", "Completed")) {
            $global:shutdownRequested = $true
        }

        Start-Sleep -Milliseconds 200
    }
}
finally {
    Write-Host "`nStopping servers..." -ForegroundColor Red
    Unregister-Event -SourceIdentifier $cancelEvent.Name -ErrorAction SilentlyContinue
    Remove-Job -Id $cancelEvent.Id -Force -ErrorAction SilentlyContinue
    Cleanup-ManagedProcesses
}
