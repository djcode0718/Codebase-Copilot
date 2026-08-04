param(
    [ValidateSet("fast", "default", "full")]
    [string]$Profile = "default"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$currentPid = $PID
$managedPorts = @(8000, 3000)
$global:shutdownRequested = $false

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

function Set-EnvIfMissing {
    param(
        [string]$Name,
        [string]$Value
    )
    if (-not (Test-Path ("env:{0}" -f $Name))) {
        Set-Item -Path ("env:{0}" -f $Name) -Value $Value
    }
}

function Apply-StartupProfile {
    param([string]$SelectedProfile)

    switch ($SelectedProfile.ToLower()) {
        "fast" {
            # Fastest startup: no backend reload, no HTTP readiness gate, no model prewarm.
            Set-EnvIfMissing -Name "BACKEND_RELOAD" -Value "false"
            Set-EnvIfMissing -Name "STARTUP_REQUIRE_HTTP_READY" -Value "false"
            Set-EnvIfMissing -Name "LLAMAINDEX_PREWARM_ON_STARTUP" -Value "false"
            Set-EnvIfMissing -Name "STARTUP_TIMEOUT_SECONDS" -Value "35"
        }
        "full" {
            # Full diagnostics/UX checks: reload + HTTP readiness + startup prewarm.
            Set-EnvIfMissing -Name "BACKEND_RELOAD" -Value "true"
            Set-EnvIfMissing -Name "STARTUP_REQUIRE_HTTP_READY" -Value "true"
            Set-EnvIfMissing -Name "LLAMAINDEX_PREWARM_ON_STARTUP" -Value "true"
            Set-EnvIfMissing -Name "STARTUP_TIMEOUT_SECONDS" -Value "90"
        }
        default {
            # Balanced default: reload + HTTP readiness, prewarm disabled for faster boot.
            Set-EnvIfMissing -Name "BACKEND_RELOAD" -Value "true"
            Set-EnvIfMissing -Name "STARTUP_REQUIRE_HTTP_READY" -Value "true"
            Set-EnvIfMissing -Name "LLAMAINDEX_PREWARM_ON_STARTUP" -Value "false"
            Set-EnvIfMissing -Name "STARTUP_TIMEOUT_SECONDS" -Value "60"
        }
    }
}

function Get-DevLanIpAddress {
    $allConfigurations = @(Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object {
        $_.NetAdapter.Status -eq "Up" -and $_.IPv4Address
    })

    $configurations = @($allConfigurations | Where-Object {
        $_.IPv4DefaultGateway -and $_.IPv4DefaultGateway.NextHop
    })
    if (-not $configurations) {
        $configurations = $allConfigurations
    }

    $candidates = foreach ($config in $configurations) {
        foreach ($address in $config.IPv4Address) {
            if (-not $address -or [string]::IsNullOrWhiteSpace($address.IPAddress)) { continue }
            if ($address.IPAddress -eq "127.0.0.1" -or $address.IPAddress -like "169.254.*") { continue }

            [pscustomobject]@{
                IPAddress = $address.IPAddress
                IsPrivate = $address.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)'
                InterfaceMetric = if ($null -ne $config.InterfaceMetric) { $config.InterfaceMetric } else { 9999 }
                InterfaceAlias = [string]$config.InterfaceAlias
            }
        }
    }

    $preferred = $candidates |
        Sort-Object @{ Expression = { if ($_.InterfaceAlias -match '(?i)(vEthernet|Hyper-V|WSL|Docker|VMware|Virtual|VPN|Tailscale|ZeroTier)') { 1 } else { 0 } }; Ascending = $true }, @{ Expression = 'IsPrivate'; Descending = $true }, @{ Expression = 'InterfaceMetric'; Ascending = $true } |
        Select-Object -First 1

    if ($preferred -and $preferred.IPAddress) {
        return $preferred.IPAddress
    }

    $fallback = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
        $_.IPAddress -and $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '0.0.0.0'
    } | Select-Object -First 1

    return $fallback.IPAddress
}

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

    # Prefer OS TCP table for stable listening checks; fall back to netstat if unavailable.
    try {
        $tcp = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
        if ($tcp) {
            return @($tcp | Where-Object { $_ -gt 0 -and $_ -ne $currentPid })
        }
    }
    catch {
        # Fall back to netstat parsing below.
    }

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

$devLanIp = Get-DevLanIpAddress
$backendOrigin = "http://localhost:8000"
$frontendOrigin = "http://localhost:3000"
if ($devLanIp) {
    $backendOrigin = "http://${devLanIp}:8000"
    $frontendOrigin = "http://${devLanIp}:3000"
    $env:DEV_ORIGIN_HOST = $devLanIp
    $env:NEXT_PUBLIC_DEV_ORIGIN_HOST = $devLanIp
}
$devAllowedOrigins = @(
    'localhost',
    '127.0.0.1',
    '::1',
    $devLanIp
) | Where-Object { $_ } | Select-Object -Unique
$env:DEV_ALLOWED_ORIGINS = $devAllowedOrigins -join ','
$env:FRONTEND_URL = $frontendOrigin
$env:NEXT_PUBLIC_API_BASE_URL = $backendOrigin

Apply-StartupProfile -SelectedProfile $Profile
Write-Host ("Startup profile: {0}" -f $Profile) -ForegroundColor DarkGray

# Capture Ctrl+C for immediate shutdown
$cancelEvent = Register-ObjectEvent -InputObject ([Console]) -EventName CancelKeyPress -Action {
    $eventArgs.Cancel = $true
    $global:shutdownRequested = $true
}

Write-Host "Starting backend (uvicorn) ..." -ForegroundColor Cyan
$backendReloadEnabled = $true
if ($env:BACKEND_RELOAD -and $env:BACKEND_RELOAD.ToLower() -in @("0", "false", "no")) {
    $backendReloadEnabled = $false
}

$backend = Start-Job -Name "backend" -ScriptBlock {
    param($r, $pythonExe, $reloadEnabled)
    Set-Location $r
    $uvicornArgs = @("-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000")
    if ($reloadEnabled) {
        $uvicornArgs += @(
            "--reload",
            "--reload-dir", "api",
            "--reload-dir", "app",
            "--reload-exclude=data/repos/*",
            "--reload-exclude=data/index/*",
            "--reload-exclude=frontend/.next/*",
            "--reload-exclude=venv_copilot/*",
            "--reload-exclude=.venv/*",
            "--reload-exclude=*.log",
            "--reload-exclude=*.pyc",
            "--reload-exclude=__pycache__/*"
        )
    }
    & $pythonExe @uvicornArgs 2>&1
} -ArgumentList $root, $backendPython, $backendReloadEnabled

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
    param([int[]]$Ports, [int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $backendDownChecks = 0
    $frontendDownChecks = 0
    $maxStartupDownChecks = 80  # ~20 seconds with 250ms loop for slower dev laptops

    function Test-HttpReady {
        param([string]$Url)
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
        } catch {
            return $false
        }
    }

    $requireHttpReady = $true
    if ($env:STARTUP_REQUIRE_HTTP_READY -and $env:STARTUP_REQUIRE_HTTP_READY.ToLower() -in @("0", "false", "no")) {
        $requireHttpReady = $false
    }

    while ((Get-Date) -lt $deadline) {
        # Stream startup logs while waiting so failures are visible immediately.
        Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
        Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"

        $backendPortUp = [bool](Get-PortPids -Port 8000)
        $frontendPortUp = [bool](Get-PortPids -Port 3000)
        $allReady = $backendPortUp -and $frontendPortUp

        if ($allReady -and $requireHttpReady) {
            $backendHttpReady = Test-HttpReady -Url "http://127.0.0.1:8000/api/health"
            $frontendHttpReady = Test-HttpReady -Url "http://127.0.0.1:3000/"
            $allReady = $backendHttpReady -and $frontendHttpReady
        }

        if ($allReady) { return $true }

        if ($backend.State -eq "Failed" -or $frontend.State -eq "Failed") {
            return $false
        }

        # Do not fail immediately on wrapper-job completion; in some shells
        # child processes may outlive the wrapper briefly while ports settle.

        # Fail quickly if the wrapper job is no longer alive and its port never came up.
        if ($backendPortUp -or $backend.State -in @("Running", "NotStarted")) {
            $backendDownChecks = 0
        } else {
            $backendDownChecks++
        }

        if ($frontendPortUp -or $frontend.State -in @("Running", "NotStarted")) {
            $frontendDownChecks = 0
        } else {
            $frontendDownChecks++
        }

        if ($backendDownChecks -ge $maxStartupDownChecks -or
            $frontendDownChecks -ge $maxStartupDownChecks) {
            return $false
        }

        Start-Sleep -Milliseconds 250
    }

    return $false
}

$startupTimeoutSeconds = 60
if ($env:STARTUP_TIMEOUT_SECONDS) {
    [int]$parsedStartupTimeout = 0
    if ([int]::TryParse($env:STARTUP_TIMEOUT_SECONDS, [ref]$parsedStartupTimeout)) {
        $startupTimeoutSeconds = $parsedStartupTimeout
    }
}
$ready = Wait-ForPortsReady -Ports $managedPorts -TimeoutSeconds $startupTimeoutSeconds
if ($ready) {
    Write-Host "Both servers are running. Press Ctrl+C to stop." -ForegroundColor Green
    Write-Host "  Backend:  $backendOrigin" -ForegroundColor Yellow
    Write-Host "  Frontend: $frontendOrigin" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "One or more servers exited before becoming ready." -ForegroundColor Red
    Write-JobOutput -Job $backend -Prefix "backend" -Color "DarkCyan"
    Write-JobOutput -Job $frontend -Prefix "frontend" -Color "DarkYellow"
    $global:shutdownRequested = $true
}

$backendDownChecks = 0
$frontendDownChecks = 0
$maxDownChecksBeforeShutdown = 150  # ~30 seconds with 200ms loop


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

        # Immediate-fail on explicit job failure.
        if ($backend.State -eq "Failed" -or $frontend.State -eq "Failed") {
            $global:shutdownRequested = $true
        }

        $backendPortUp = [bool](Get-PortPids -Port 8000)
        $frontendPortUp = [bool](Get-PortPids -Port 3000)

        # Detect real exits: port is gone and wrapper job is no longer alive.
        if ($backendPortUp -or $backend.State -in @("Running", "NotStarted")) {
            $backendDownChecks = 0
        } else {
            $backendDownChecks++
        }

        if ($frontendPortUp -or $frontend.State -in @("Running", "NotStarted")) {
            $frontendDownChecks = 0
        } else {
            $frontendDownChecks++
        }

        if ($backendDownChecks -ge $maxDownChecksBeforeShutdown) {
            Write-Host "Backend appears down for an extended period; initiating shutdown." -ForegroundColor Red
            $global:shutdownRequested = $true
        }
        if ($frontendDownChecks -ge $maxDownChecksBeforeShutdown) {
            Write-Host "Frontend appears down for an extended period; initiating shutdown." -ForegroundColor Red
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
