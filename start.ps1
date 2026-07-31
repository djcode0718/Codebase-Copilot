$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentPid = $PID
$managedPorts = @(8000, 3000)
$global:shutdownRequested = $false

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$backendPythonCandidates = @(
    (Join-Path $root ".venv\Scripts\python.exe")
)
$backendPython = $backendPythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $backendPython) {
    throw "Python interpreter not found. Expected one of: $($backendPythonCandidates -join ', ')"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not available on PATH. Install Node.js or open a shell where npm is available."
}

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
    foreach ($trackedPid in $global:trackedPids) {
        Stop-ProcessTree -ProcessId $trackedPid
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
    param($r, $pythonExe)
    Set-Location $r
    & $pythonExe -m uvicorn api.main:app --reload --port 8000 2>&1
} -ArgumentList $root, $backendPython

Write-Host "Starting frontend (npm run dev) ..." -ForegroundColor Cyan
$frontend = Start-Job -Name "frontend" -ScriptBlock {
    param($r)
    Set-Location "$r\frontend"
    # Keep dev logs plain so PS job output remains readable.
    $env:NO_COLOR = "1"
    $env:FORCE_COLOR = "0"
    $env:CI = "1"
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

        # Remove ANSI/control artifacts and any non-ASCII symbols that print as mojibake.
        $line = $line -replace "`e\[[0-9;?]*[ -/]*[@-~]", ""
        $line = $line -replace "[^\x09\x0A\x0D\x20-\x7E]", ""
        if ([string]::IsNullOrWhiteSpace($line)) { continue }

        Write-Host ("[{0}] {1}" -f $Prefix, $line) -ForegroundColor $Color
    }
}

function Wait-ForPortsReady {
    param([int[]]$Ports, [int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        # Stream startup logs while waiting so failures are visible immediately.
        Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
        Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"

        $backendPortUp = [bool](Get-PortPids -Port 8000)
        $frontendPortUp = [bool](Get-PortPids -Port 3000)
        $allReady = $backendPortUp -and $frontendPortUp

        if ($allReady) { return $true }

        # Fail fast only if a startup job exited and its port is still down.
        if (($backend.State -in @("Failed","Stopped","Completed") -and -not $backendPortUp) -or
            ($frontend.State -in @("Failed","Stopped","Completed") -and -not $frontendPortUp)) {
            return $false
        }

        Start-Sleep -Milliseconds 250
    }

    return $false
}

$ready = Wait-ForPortsReady -Ports $managedPorts -TimeoutSeconds 30
if ($ready) {
    Write-Host "Both servers are running. Press Ctrl+C to stop." -ForegroundColor Green
    Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
    Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "One or more servers exited before becoming ready." -ForegroundColor Red
    Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
    Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"
    $global:shutdownRequested = $true
}

$backendPortMisses = 0
$frontendPortMisses = 0
$maxPortMissesBeforeShutdown = 10  # ~2 seconds with 200ms loop


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

        # Only immediate-fail on explicit job failure.
        if ($backend.State -eq "Failed" -or
            $frontend.State -eq "Failed") {
            $global:shutdownRequested = $true
        }

        if (Get-PortPids -Port 8000) {
            $backendPortMisses = 0
        } else {
            $backendPortMisses++
        }

        if (Get-PortPids -Port 3000) {
            $frontendPortMisses = 0
        } else {
            $frontendPortMisses++
        }

        if ($backendPortMisses -ge $maxPortMissesBeforeShutdown) {
            $global:shutdownRequested = $true
        }
        if ($frontendPortMisses -ge $maxPortMissesBeforeShutdown) {
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
