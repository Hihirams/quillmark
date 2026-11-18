# Quillmark - detiene el servidor local y libera la RAM de los modelos
# Uso:  .\stop-local.ps1
#       .\stop-local.ps1 -Port 8080      # comprueba tambien ese puerto
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Continue"

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*app.main*" }

if (-not $procs) {
    Write-Host "  No hay ningun servidor Quillmark corriendo." -ForegroundColor Yellow
} else {
    foreach ($p in $procs) {
        $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        $ramGb = if ($proc) { [math]::Round($proc.PrivateMemorySize64 / 1GB, 2) } else { 0 }
        Write-Host ("  Parando PID {0} (RAM privada: {1} GB)" -f $p.ProcessId, $ramGb)
        # Las transacciones pendientes quedan en el WAL de SQLite, no se pierde nada.
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 3
}

$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($still) {
    $owner = $still.OwningProcess | Select-Object -First 1
    Write-Host "  Aviso: el puerto $Port sigue escuchando (PID $owner), no era de Quillmark." -ForegroundColor Yellow
} else {
    Write-Host "  Puerto $Port libre." -ForegroundColor Green
}

Start-Sleep -Seconds 1
$os = Get-CimInstance Win32_OperatingSystem
$freeGb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$totalGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Write-Host ("  RAM libre ahora: {0} GB de {1} GB" -f $freeGb, $totalGb) -ForegroundColor Cyan
