# Development launch script for OAK Tower Watcher Web Application
# Usage: .\start_dev.ps1 (from web directory)

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Change to the web directory
Set-Location $ScriptDir

Write-Host "Starting OAK Tower Watcher Web Application in development mode..." -ForegroundColor Green
Write-Host ""

# Check if Docker Desktop is running
try {
    docker version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running"
    }
} catch {
    Write-Host "❌ Error: Docker Desktop is not running or not installed." -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

# Check if docker-compose.dev.win.yml exists
if (-not (Test-Path "docker-compose.dev.win.yml")) {
    Write-Host "❌ Error: docker-compose.dev.win.yml not found." -ForegroundColor Red
    Write-Host "This file should be present in the web directory for development." -ForegroundColor Yellow
    exit 1
}

# Load environment variables from .env file if it exists
if (Test-Path "../env/.env") {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content "../env/.env" | Where-Object { $_ -match "^[^#]" -and $_ -match "=" } | ForEach-Object {
        $name, $value = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Set development-specific environment variables
[Environment]::SetEnvironmentVariable("APP_ENV", "development", "Process")
[Environment]::SetEnvironmentVariable("FLASK_ENV", "development", "Process")

Write-Host "Environment: development" -ForegroundColor Cyan
Write-Host "Port: 8080 (accessible at http://localhost:8080)" -ForegroundColor Cyan
Write-Host ""

# Build and start the containers
Write-Host "Building and starting Docker containers..." -ForegroundColor Blue
docker compose -f docker-compose.dev.win.yml up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Development environment started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 Web Application: http://localhost:8080" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To view logs: docker compose -f docker-compose.yml -f docker-compose.dev.win.yml logs -f" -ForegroundColor Yellow
    Write-Host "To stop: .\stop_dev.ps1" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "❌ Failed to start development environment." -ForegroundColor Red
    Write-Host "Check the logs with: docker compose -f docker-compose.yml -f docker-compose.dev.win.yml logs" -ForegroundColor Yellow
    exit 1
}