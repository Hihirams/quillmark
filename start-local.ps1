# Quillmark - lanzador local para este equipo (Windows / CPU)
# Uso:
#   .\start-local.ps1                      # perfil standard, solo localhost
#   .\start-local.ps1 -Profile lite        # menos RAM/workers (modo juego)
#   .\start-local.ps1 -Port 8080
#   .\start-local.ps1 -HostAddr 0.0.0.0    # accesible en la LAN
#   .\start-local.ps1 -Open                # abre el navegador cuando el puerto responde
#   .\start-local.ps1 -Threads 4           # hilos de inferencia (menos CPU, mas lento)
#   .\start-local.ps1 -NoCache             # recalcula siempre, ignora reportes guardados
param(
    [ValidateSet("lite", "standard", "performance")]
    [string]$Profile = "standard",
    [int]$Port = 8000,
    [string]$HostAddr = "127.0.0.1",
    [int]$Threads = 8,
    [switch]$NoCache,
    [switch]$Open
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# La consola de Windows usa cp1252 y el banner de arranque lleva caracteres
# Unicode: sin esto, el servidor muere con UnicodeEncodeError.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Los pesos de Hugging Face viven en H: (carpeta con el nombre original para no
# volver a descargar 9 GB)
$env:HF_HOME = "H:/sloptotal-models"
# Reportes y SQLite del proyecto
$env:SLOPTOTAL_DATA_DIR = Join-Path $PSScriptRoot "data"
# Forzamos CPU: torch instalado es el build cpu
$env:SLOPTOTAL_DEVICE = "cpu"
$env:SLOPTOTAL_PROFILE = $Profile
$env:SLOPTOTAL_PORT = "$Port"
# Hilos de inferencia. El perfil standard deja 1 por defecto, que en este
# equipo (12 nucleos fisicos) tardaba ~44 s por analisis. Medido aqui:
#   1 hilo -> 43.9 s | 6 -> 11.0 s | 12 -> 9.3 s
# Con 8 quedan nucleos libres para las 2 peticiones simultaneas que permite
# la cola. Los scores son identicos con cualquier valor.
$env:SLOPTOTAL_TORCH_THREADS = "$Threads"
# Con cache activa, un texto identico devuelve el reporte guardado al instante
# (mismo contenido y misma puntuacion, solo se salta el calculo). -NoCache
# obliga a recalcular siempre.
$env:SLOPTOTAL_CACHE_ENABLED = if ($NoCache) { "false" } else { "true" }

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No se encontro el entorno virtual en venv\. Crealo con: py -3.12 -m venv venv"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "El puerto $Port ya esta en uso (PID $($listener.OwningProcess)). Usa -Port o ejecuta .\stop-local.ps1"
}

$freeGb = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)

Write-Host ""
Write-Host "  Quillmark -> http://localhost:$Port" -ForegroundColor Cyan
$cacheTxt = if ($NoCache) { "desactivada (siempre recalcula)" } else { "activa (texto identico = al instante)" }
Write-Host "  Perfil:   $Profile   (dispositivo: cpu, hilos: $Threads)" -ForegroundColor DarkGray
Write-Host "  Cache:    $cacheTxt" -ForegroundColor DarkGray
Write-Host "  Modelos:  $env:HF_HOME" -ForegroundColor DarkGray
Write-Host "  Datos:    $env:SLOPTOTAL_DATA_DIR" -ForegroundColor DarkGray
Write-Host "  RAM libre al arrancar: $freeGb GB (los modelos usan ~8-9 GB)" -ForegroundColor DarkGray
Write-Host "  Parar con CTRL+C, o desde otra consola: .\stop-local.ps1" -ForegroundColor DarkGray

if ($Open) {
    # Espera a que el puerto acepte conexiones (los modelos tardan en cargar) y
    # abre el navegador por defecto. Corre en un job aparte para no bloquear.
    $url = "http://localhost:$Port"
    Start-Job -ArgumentList $Port, $url -ScriptBlock {
        param($port, $url)
        $deadline = (Get-Date).AddSeconds(300)
        while ((Get-Date) -lt $deadline) {
            $client = New-Object Net.Sockets.TcpClient
            try {
                $client.Connect("127.0.0.1", $port)
                Start-Process $url
                return
            } catch {
                Start-Sleep -Milliseconds 700
            } finally {
                $client.Dispose()
            }
        }
    } | Out-Null
    Write-Host "  Navegador: se abrira solo en cuanto el servidor responda." -ForegroundColor DarkGray
}

Write-Host ""

& $python -m uvicorn app.main:app --host $HostAddr --port $Port
