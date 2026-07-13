# ChickHub — Start Server
Write-Host "=== ChickHub Starting ===" -ForegroundColor Cyan

# Cek Mosquitto
$mq = Get-Service mosquitto -ErrorAction SilentlyContinue
if ($mq -and $mq.Status -ne 'Running') {
    Write-Host "Starting Mosquitto..." -ForegroundColor Yellow
    Start-Service mosquitto
}

# Start server
Write-Host "Server: http://localhost:3000" -ForegroundColor Green
Write-Host "Login : admin / admin" -ForegroundColor Green
cd "$PSScriptRoot\server"
node index.js
