@echo off
setlocal enabledelayedexpansion

REM VATSIM Tower Monitor - Docker Deployment Script (Windows)
REM This script helps deploy the Docker version of the headless monitor

echo ==========================================
echo VATSIM Tower Monitor - Docker Deployment
echo ==========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop from: https://docs.docker.com/desktop/windows/install/
    pause
    exit /b 1
)

REM Check if docker compose is available
docker compose --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] docker compose not found, trying 'docker compose'...
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Neither docker compose nor 'docker compose' is available
        pause
        exit /b 1
    ) else (
        set DOCKER_COMPOSE_CMD=docker compose
    )
) else (
    set DOCKER_COMPOSE_CMD=docker compose
)

echo [SUCCESS] Prerequisites check passed
echo.

REM Setup environment file
echo [INFO] Setting up environment configuration...
if not exist ".env" (
    if exist ".env.sample" (
        copy ".env.sample" ".env" >nul
        echo [SUCCESS] Created .env file from sample
    ) else (
        echo [ERROR] .env.sample file not found
        pause
        exit /b 1
    )
) else (
    echo [WARNING] .env file already exists, skipping creation
)

REM Check if Pushover credentials need to be updated
findstr /C:"your_pushover_api_token_here" .env >nul
if not errorlevel 1 (
    echo [WARNING] Please update your Pushover credentials in .env file
    echo Edit .env and set:
    echo   PUSHOVER_API_TOKEN=your_actual_token
    echo   PUSHOVER_USER_KEY=your_actual_user_key
    echo.
    pause
)

REM Build and start the service
echo [INFO] Building and starting VATSIM Tower Monitor...
echo.

echo [INFO] Building Docker image...
%DOCKER_COMPOSE_CMD% build
if errorlevel 1 (
    echo [ERROR] Failed to build Docker image
    pause
    exit /b 1
)

echo [INFO] Starting the service...
%DOCKER_COMPOSE_CMD% up -d
if errorlevel 1 (
    echo [ERROR] Failed to start the service
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [SUCCESS] Deployment completed!
echo ==========================================
echo.

REM Show status
echo [INFO] Checking service status...
%DOCKER_COMPOSE_CMD% ps
echo.

echo [INFO] Recent logs (last 20 lines):
%DOCKER_COMPOSE_CMD% logs --tail=20
echo.

echo [INFO] The service will test Pushover notifications on startup.
echo Check the logs above for 'Pushover test successful' message.
echo.

echo [INFO] Useful commands:
echo   View logs:           %DOCKER_COMPOSE_CMD% logs -f
echo   Stop service:        %DOCKER_COMPOSE_CMD% down
echo   Restart service:     %DOCKER_COMPOSE_CMD% restart
echo   Update service:      %DOCKER_COMPOSE_CMD% down ^&^& %DOCKER_COMPOSE_CMD% build --no-cache ^&^& %DOCKER_COMPOSE_CMD% up -d
echo.

echo [INFO] To follow logs in real-time, run:
echo   %DOCKER_COMPOSE_CMD% logs -f
echo.

pause