<#
.SYNOPSIS
    Khởi chạy đồng thời FastAPI Backend và Web Frontend (React/HTML/CSS)
.DESCRIPTION
    Script tự động kiểm tra môi trường Python và Node.js, khởi động Uvicorn server tại cổng 8000
    phục vụ cả API RESTful và giao diện Web tĩnh React được build sẵn trong web/dist.
#>

$ErrorActionPreference = "Stop"
$root = (Resolve-Path ".").Path
$python = "C:\Users\DELL\AppData\Local\Python\bin\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " HỆ HỖ TRỢ CẢNH BÁO RỦI RO HỌC TẬP VÀ TỐI ƯU TÍN CHỈ (NTU)" -ForegroundColor Cyan
Write-Host " FastAPI Backend + React/HTML/CSS Dashboard" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Kiểm tra thư mục web/dist
$webDist = Join-Path $root "web\dist"
if (-not (Test-Path $webDist)) {
    Write-Host "[1/2] Đang build gói giao diện React tĩnh trong web/dist..." -ForegroundColor Yellow
    Set-Location (Join-Path $root "web")
    & "C:\Program Files\nodejs\npm.cmd" run build
    Set-Location $root
} else {
    Write-Host "[1/2] Đã tìm thấy bản build giao diện React trong web/dist." -ForegroundColor Green
}

Write-Host "[2/2] Khởi động máy chủ FastAPI tại http://localhost:8000 ..." -ForegroundColor Green
Write-Host "  -> API Docs:    http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  -> Giao diện Web: http://localhost:8000/" -ForegroundColor Cyan
Write-Host "Nhấn Ctrl + C để dừng máy chủ." -ForegroundColor Yellow
Write-Host ""

& $python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
