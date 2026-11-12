# Automated PowerShell smoke tests for Flask + MongoDB API
param (
    [string]$BaseUrl = "http://localhost:5000"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SMOKE TEST: Flask + MongoDB API at $BaseUrl" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. GET /
Write-Host "`n[1] GET / (Root Endpoint)..." -ForegroundColor Yellow
$rootRes = Invoke-RestMethod -Uri "$BaseUrl/" -Method Get
Write-Host "Response: $rootRes" -ForegroundColor Green

# 2. Health checks
Write-Host "`n[2] Checking Health Probes..." -ForegroundColor Yellow
$live = Invoke-RestMethod -Uri "$BaseUrl/health/live" -Method Get
Write-Host "Liveness: $($live | ConvertTo-Json -Compress)" -ForegroundColor Green
$ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -Method Get
Write-Host "Readiness: $($ready | ConvertTo-Json -Compress)" -ForegroundColor Green

# 3. POST /data
Write-Host "`n[3] POST /data (Insert Document)..." -ForegroundColor Yellow
$body = @{
    sampleKey = "sampleValue"
    author = "Aman"
    source = "PowerShell-SmokeTest"
} | ConvertTo-Json
$postRes = Invoke-RestMethod -Uri "$BaseUrl/data" -Method Post -Body $body -ContentType "application/json"
Write-Host "Response: $($postRes | ConvertTo-Json -Compress)" -ForegroundColor Green

# 4. GET /data
Write-Host "`n[4] GET /data (Retrieve Documents)..." -ForegroundColor Yellow
$dataRes = Invoke-RestMethod -Uri "$BaseUrl/data" -Method Get
Write-Host "Retrieved $($dataRes.Count) document(s):" -ForegroundColor Green
$dataRes | ForEach-Object { Write-Host " - $(ConvertTo-Json $_ -Compress)" }

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "ALL TESTS PASSED SUCCESSFULLY!" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

