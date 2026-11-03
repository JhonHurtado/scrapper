# run.ps1 - Inicia el Colombia Tourist Scraper (backend + frontend) en Windows
# Uso:  .\run.bat   (o: powershell -ExecutionPolicy Bypass -File run.ps1)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONUTF8 = "1"   # logs con acentos/emoji sin errores de codificacion

function Log($msg)  { Write-Host "[run.ps1] $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[run.ps1] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[run.ps1] $msg" -ForegroundColor Yellow }

# --- Localizar Python (python o py launcher) --------------------------------
$PyLauncher = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $PyLauncher = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PyLauncher = "py" }
else { throw "Python 3.9+ no encontrado en el PATH. Instalalo desde https://www.python.org" }

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm no encontrado en el PATH. Instala Node.js 18+ desde https://nodejs.org"
}

# --- Entorno virtual de Python -----------------------------------------------
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Warn "No existe .venv - creandolo..."
    if ($PyLauncher -eq "py") { py -3 -m venv $Venv } else { python -m venv $Venv }
}

# Reinstala dependencias cuando cambia requirements.txt (un .venv viejo no
# trae los paquetes nuevos).
$Requirements = Join-Path $Root "requirements.txt"
$ReqStamp = Join-Path $Venv ".requirements.sha"
$ReqHash = (Get-FileHash $Requirements -Algorithm SHA256).Hash
if (-not (Test-Path $ReqStamp) -or (Get-Content $ReqStamp -Raw).Trim() -ne $ReqHash) {
    Warn "Instalando dependencias de Python..."
    & $Python -m pip install -q --upgrade pip
    & $Python -m pip install -q -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install fallo" }
    Set-Content -Path $ReqStamp -Value $ReqHash
    Ok "Dependencias de Python instaladas."
}

# --- Navegador (solo para el respaldo de Google Maps) --------------------------
# Se usa el navegador Chromium instalado (Brave, Chrome, Edge); no se descarga
# nada. Elige otro con SCRAPER_BROWSER o SCRAPER_BROWSER_PATH.
if ($env:GEOCODER_GOOGLE_FALLBACK -ne "false") {
    # En PowerShell 5.1, con "Stop", cualquier texto en stderr de un programa
    # externo se vuelve error fatal: aqui stderr solo trae avisos.
    $PrevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    Push-Location $Root
    $BrowserExe = & $Python -m backend.scraper.official.browser 2>$null
    Pop-Location
    $ErrorActionPreference = $PrevPref
    if ($LASTEXITCODE -eq 0 -and $BrowserExe -and $BrowserExe -ne "playwright") {
        Ok "Navegador para el respaldo de Google Maps: $BrowserExe"
    } else {
        Warn "No se encontro Brave, Chrome ni Edge: el respaldo de Google Maps no estara disponible."
        Warn "El scraping de fuentes oficiales funciona igual. Para activarlo instala Brave o Chrome,"
        Warn "o descarga Chromium con: $Python -m playwright install chromium"
    }
}

# --- Dependencias de Node ------------------------------------------------------
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Warn "Ejecutando npm install..."
    Push-Location (Join-Path $Root "frontend")
    npm install --silent
    Pop-Location
    Ok "Dependencias de Node instaladas."
}

# --- Arrancar backend y frontend -----------------------------------------------
Log "Iniciando backend FastAPI en http://localhost:8000 ..."
$Backend = Start-Process -FilePath $Python `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $Root -PassThru -NoNewWindow

Log "Iniciando frontend React en http://localhost:5173 ..."
$Frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev -- --open" `
    -WorkingDirectory (Join-Path $Root "frontend") -PassThru -NoNewWindow

Ok "Ambos servicios corriendo. Presiona Ctrl+C para detenerlos."
try {
    Wait-Process -Id $Backend.Id, $Frontend.Id
}
finally {
    Log "Deteniendo..."
    foreach ($proc in @($Backend, $Frontend)) {
        if ($proc -and -not $proc.HasExited) {
            # /T mata el arbol completo (uvicorn/vite crean procesos hijos)
            taskkill /PID $proc.Id /T /F 2>$null | Out-Null
        }
    }
    Ok "Listo."
}
