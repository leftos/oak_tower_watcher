# Development shutdown script for OAK Tower Watcher Web Application
# Usage: .\stop_dev.ps1 (from web directory)

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Change to the web directory
Set-Location $ScriptDir

Write-Host "Stopping OAK Tower Watcher Web Application..." -ForegroundColor Yellow
Write-Host ""

# Check if Docker Desktop is running
try {
    docker version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running"
    }
} catch {
    Write-Host "❌ Error: Docker Desktop is not running." -ForegroundColor Red
    Write-Host "Cannot stop containers without Docker Desktop." -ForegroundColor Yellow
    exit 1
}

# Stop and remove containers, networks
Write-Host "Stopping Docker containers..." -ForegroundColor Blue
docker compose -f docker-compose.dev.win.yml down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Development environment stopped successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Check for any remaining containers
    $remainingContainers = docker ps -a --filter "name=vatsim" --format "table {{.Names}}\t{{.Status}}" | Select-Object -Skip 1
    
    if ($remainingContainers) {
        Write-Host "⚠️  Some containers may still exist:" -ForegroundColor Yellow
        $remainingContainers | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        Write-Host ""
        Write-Host "To completely remove all containers and volumes:" -ForegroundColor Cyan
        Write-Host "   docker compose -f docker-compose.yml -f docker-compose.dev.win.yml down --volumes --remove-orphans" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "❌ Error occurred while stopping containers." -ForegroundColor Red
    Write-Host "You may need to stop them manually:" -ForegroundColor Yellow
    Write-Host "   docker compose -f docker-compose.yml -f docker-compose.dev.win.yml down --remove-orphans" -ForegroundColor Gray
    exit 1
}

Write-Host "Shutdown complete." -ForegroundColor Green