# scripts/check.ps1
# 本地 CI 检查脚本 (Windows PowerShell)
# 用法: .\scripts\check.ps1
# 功能: 依次运行 Ruff → Pyright → Pytest 并汇总结果

$ErrorActionPreference = "Stop"
$checks = @{}

Write-Host "=== 荔枝头 litchi-head: 本地代码检查 ===" -ForegroundColor Cyan
Write-Host ""

# 1) Ruff
Write-Host "[1/3] 运行 Ruff 代码风格检查..." -ForegroundColor Yellow
try {
    $output = ruff check . 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ PASS" -ForegroundColor Green
        $checks.ruff = $true
    } else {
        Write-Host "  ❌ FAIL" -ForegroundColor Red
        $output
        $checks.ruff = $false
    }
} catch {
    Write-Host "  ⚠️  找不到 ruff，请先执行: pip install -e .[dev]" -ForegroundColor Red
    $checks.ruff = $false
}

Write-Host ""

# 2) Pyright
Write-Host "[2/3] 运行 Pyright 类型检查..." -ForegroundColor Yellow
try {
    $output = pyright src/ 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ PASS" -ForegroundColor Green
        $checks.pyright = $true
    } else {
        Write-Host "  ❌ FAIL" -ForegroundColor Red
        $output
        $checks.pyright = $false
    }
} catch {
    Write-Host "  ⚠️  找不到 pyright，请先执行: pip install -e .[dev]" -ForegroundColor Red
    $checks.pyright = $false
}

Write-Host ""

# 3) Pytest
Write-Host "[3/3] 运行 Pytest 测试..." -ForegroundColor Yellow
try {
    $output = pytest -v --tb=short 2>&1
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 5) {
        Write-Host "  ✅ PASS" -ForegroundColor Green
        $checks.pytest = $true
    } else {
        Write-Host "  ❌ FAIL" -ForegroundColor Red
        $output
        $checks.pytest = $false
    }
} catch {
    Write-Host "  ⚠️  找不到 pytest，请先执行: pip install -e .[dev]" -ForegroundColor Red
    $checks.pytest = $false
}

Write-Host ""

# 汇总
Write-Host "========== 检查汇总 ==========" -ForegroundColor Cyan
$allPassed = $true
foreach ($key in $checks.Keys) {
    $status = if ($checks[$key]) { "✅ PASS" } else { "❌ FAIL" }
    $color = if ($checks[$key]) { "Green" } else { "Red" }
    Write-Host "  $key : $status" -ForegroundColor $color
    if (-not $checks[$key]) { $allPassed = $false }
}

Write-Host ""
if ($allPassed) {
    Write-Host "🎉 所有检查通过！" -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠️  部分检查未通过，请修复后重新运行。" -ForegroundColor Red
    exit 1
}
