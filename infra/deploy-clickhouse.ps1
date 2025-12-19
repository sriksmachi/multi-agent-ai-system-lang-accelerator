# Deploy ClickHouse using Docker
# This script runs ClickHouse Server in a Docker container for Langfuse

$ErrorActionPreference = "Stop"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "ClickHouse Server Deployment" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if Docker is running
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Container configuration
$ContainerName = "clickhouse-server"
$ClickHouseDB = "default"
$ClickHouseUser = "clickhouse"
$ClickHousePassword = "clickhouse"

Write-Host "📋 Configuration:" -ForegroundColor Cyan
Write-Host "   Container Name: $ContainerName" -ForegroundColor White
Write-Host "   Database: $ClickHouseDB" -ForegroundColor White
Write-Host "   User: $ClickHouseUser" -ForegroundColor White
Write-Host "   Password: $ClickHousePassword" -ForegroundColor White
Write-Host "   HTTP Port: 8123" -ForegroundColor White
Write-Host "   Native Port: 9000" -ForegroundColor White
Write-Host "   Interserver Port: 9009" -ForegroundColor White
Write-Host ""

# Check if container already exists
$ExistingContainer = docker ps -a --filter "name=^/${ContainerName}$" --format "{{.Names}}" 2>$null
if ($ExistingContainer -eq $ContainerName) {
    Write-Host "⚠️  Container '$ContainerName' already exists" -ForegroundColor Yellow
    $ContainerState = docker inspect --format='{{.State.Status}}' $ContainerName 2>$null
    
    if ($ContainerState -eq "running") {
        Write-Host "   Container is already running" -ForegroundColor Green
        Write-Host ""
        Write-Host "To stop: docker stop $ContainerName" -ForegroundColor Yellow
        Write-Host "To remove: docker rm $ContainerName" -ForegroundColor Yellow
    } else {
        Write-Host "   Starting existing container..." -ForegroundColor Cyan
        docker start $ContainerName
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Container started" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to start container" -ForegroundColor Red
            exit 1
        }
    }
} else {
    # Run ClickHouse container
    Write-Host "🐳 Starting ClickHouse Server container..." -ForegroundColor Cyan
    
    docker run --name $ContainerName `
        -e CLICKHOUSE_DB=$ClickHouseDB `
        -e CLICKHOUSE_USER=$ClickHouseUser `
        -e CLICKHOUSE_PASSWORD=$ClickHousePassword `
        -d `
        --ulimit nofile=262144:262144 `
        -p 8123:8123 `
        -p 9000:9000 `
        -p 9009:9009 `
        clickhouse/clickhouse-server

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ ClickHouse Server container started" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to start ClickHouse container" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "⏳ Waiting for ClickHouse to be ready..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Verify ClickHouse is responding
$MaxRetries = 10
$RetryCount = 0
$IsReady = $false

while (-not $IsReady -and $RetryCount -lt $MaxRetries) {
    try {
        $Response = Invoke-WebRequest -Uri "http://localhost:8123/ping" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($Response.StatusCode -eq 200) {
            $IsReady = $true
        }
    } catch {
        $RetryCount++
        Write-Host "   Waiting... (attempt $RetryCount/$MaxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if ($IsReady) {
    Write-Host "✅ ClickHouse Server is ready!" -ForegroundColor Green
} else {
    Write-Host "⚠️  ClickHouse Server may still be starting up" -ForegroundColor Yellow
    Write-Host "   Check logs with: docker logs $ContainerName" -ForegroundColor White
}

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Connection Details:" -ForegroundColor Cyan
Write-Host "   HTTP Interface: http://localhost:8123" -ForegroundColor White
Write-Host "   Native Protocol: localhost:9000" -ForegroundColor White
Write-Host "   Username: $ClickHouseUser" -ForegroundColor White
Write-Host "   Password: $ClickHousePassword" -ForegroundColor White
Write-Host "   Database: $ClickHouseDB" -ForegroundColor White
Write-Host ""
Write-Host "For Langfuse configuration, use:" -ForegroundColor Yellow
Write-Host "   CLICKHOUSE_URL=http://localhost:8123" -ForegroundColor White
Write-Host "   CLICKHOUSE_USER=$ClickHouseUser" -ForegroundColor White
Write-Host "   CLICKHOUSE_PASSWORD=$ClickHousePassword" -ForegroundColor White
Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Yellow
Write-Host "   View logs:    docker logs $ContainerName" -ForegroundColor White
Write-Host "   Stop server:  docker stop $ContainerName" -ForegroundColor White
Write-Host "   Start server: docker start $ContainerName" -ForegroundColor White
Write-Host "   Remove:       docker rm -f $ContainerName" -ForegroundColor White
Write-Host ""
Write-Host "Test connection:" -ForegroundColor Yellow
Write-Host "   Invoke-WebRequest -Uri 'http://localhost:8123/ping'" -ForegroundColor White
Write-Host ""
