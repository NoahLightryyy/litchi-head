# 启动开发环境
Write-Host "🚀 荔枝头 · 开发环境" -ForegroundColor Green

# 激活 conda
conda activate litchi
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ conda 激活失败，请先安装 conda" -ForegroundColor Red
    exit 1
}

# 解决 Windows 中文乱码
$env:PYTHONUTF8 = "1"
$env:DEBUG = "true"

# 加载 .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^(.*?)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
    Write-Host "✅ .env 已加载" -ForegroundColor Green
}

Write-Host "✅ 就绪！用 code . 打开 VS Code" -ForegroundColor Green
