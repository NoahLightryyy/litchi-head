# 荔枝头 · 一键启动（Windows）
# 用法：双击仓库根目录的 start.bat（停止：在窗口里按回车，或双击 stop.bat）
# 做的事：检查环境 → 首次自动安装依赖 → 启动后端(8000)和前端(3000) → 打开浏览器。
param([switch]$Stop)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

$BackendPort = 8000
$FrontendPort = 3000
$BackendUrl = "http://127.0.0.1:$BackendPort/api/health"
$FrontendUrl = "http://localhost:$FrontendPort"
$LogDir = Join-Path $Root "logs"
$BackendLog = Join-Path $LogDir "launcher-backend.log"
$FrontendLog = Join-Path $LogDir "launcher-frontend.log"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
$Backend = $null
$Frontend = $null

function Step($msg) { Write-Host ""; Write-Host "▶ $msg" -ForegroundColor Cyan }
function Fail($msg, [string[]]$hints) {
    Stop-Tree $script:Frontend
    Stop-Tree $script:Backend
    Write-Host ""
    Write-Host "❌ $msg" -ForegroundColor Red
    foreach ($h in $hints) { Write-Host "   $h" }
    Write-Host ""
    Read-Host "按回车键关闭窗口" | Out-Null
    exit 1
}
function Test-Http($url) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $url | Out-Null; return $true }
    catch { return $false }
}
function Test-Port($port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", $port); return $true }
    catch { return $false }
    finally { $client.Close() }
}
function Stop-Tree($proc) {
    if ($null -ne $proc -and -not $proc.HasExited) {
        & taskkill.exe /PID $proc.Id /T /F 2>$null | Out-Null
    }
}
function Stop-PortOwner($port) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $owners) {
        if ($procId -gt 4) { & taskkill.exe /PID $procId /T /F 2>$null | Out-Null }
    }
}
function Wait-Ready($url, $proc, $seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (Test-Http $url) { return "ok" }
        if ($proc.HasExited) { return "exited" }
        Start-Sleep -Seconds 1
    }
    return "timeout"
}
function Show-Tail($path) {
    foreach ($p in @($path, "$path.err")) {
        if (Test-Path $p) { Get-Content $p -Tail 30 -Encoding UTF8 }
    }
}

if ($Stop) {
    Stop-PortOwner $FrontendPort
    Stop-PortOwner $BackendPort
    Write-Host "已停止荔枝头服务（端口 $BackendPort / $FrontendPort）。"
    exit 0
}

Write-Host "🍒 荔枝头 · 一键启动" -ForegroundColor Green
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── 0. 已经在运行？直接打开浏览器 ──────────────────────────────
if ((Test-Http $BackendUrl) -and (Test-Http $FrontendUrl)) {
    Write-Host "服务已经在运行，直接打开浏览器。"
    Start-Process $FrontendUrl
    exit 0
}
foreach ($port in @($BackendPort, $FrontendPort)) {
    if (Test-Port $port) {
        Fail "端口 $port 已被其他程序占用。" @(
            "如果是上一次没关干净的荔枝头：双击 stop.bat 后重试。"
        )
    }
}

# ── 1. Python ──────────────────────────────────────────────────
Step "检查 Python（需要 3.12 或更高）"
$VersionCheck = "import sys; sys.exit(sys.version_info < (3, 12))"
$Py = $null
if (Test-Path $VenvPy) {
    & $VenvPy -c $VersionCheck 2>$null
    if ($LASTEXITCODE -eq 0) { $Py = $VenvPy }
}
if ($null -eq $Py) {
    $candidates = @(@("py", "-3.13"), @("py", "-3.12"), @("python"))
    foreach ($c in $candidates) {
        $exe = $c[0]
        $pre = @($c | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        & $exe @pre -c $VersionCheck 2>$null
        if ($LASTEXITCODE -ne 0) { continue }
        Write-Host "创建虚拟环境（首次运行）…"
        & $exe @pre -m venv (Join-Path $Root ".venv")
        if ($LASTEXITCODE -eq 0 -and (Test-Path $VenvPy)) { $Py = $VenvPy }
        break
    }
}
if ($null -eq $Py) {
    Fail "没有找到 Python 3.12+。" @(
        "请从 https://www.python.org/downloads/ 安装（勾选 Add python.exe to PATH）后重试。"
    )
}
Write-Host (& $Py --version)

# ── 2. Python 依赖（按 constraints.txt 锁定版本） ───────────────
$DepsStamp = Join-Path $Root ".venv\.litchi-deps"
$DepsWant = ((Get-FileHash pyproject.toml).Hash + (Get-FileHash constraints.txt).Hash)
$DepsHave = if (Test-Path $DepsStamp) { (Get-Content $DepsStamp -Raw).Trim() } else { "" }
if ($DepsHave -ne $DepsWant) {
    $ready = $false
    if (-not (Test-Path $DepsStamp)) {
        & $Py -c "import fastapi, uvicorn, langgraph, akshare, src" 2>$null
        $ready = ($LASTEXITCODE -eq 0)
    }
    if (-not $ready) {
        Step "安装 Python 依赖（首次或依赖有更新，需要几分钟）"
        & $Py -m pip install --disable-pip-version-check -q -e ".[dev]" -c constraints.txt
        if ($LASTEXITCODE -ne 0) {
            Fail "Python 依赖安装失败。" @("请检查网络后重试；完整输出见上方。")
        }
    }
    Set-Content -Path $DepsStamp -Value $DepsWant -NoNewline -Encoding ASCII
}
Write-Host "Python 依赖已就绪。"

# ── 3. 配置与密钥提示（不阻断：行情浏览不需要密钥） ─────────────
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已从 .env.example 生成 .env。"
}
$envHasKey = [bool](Select-String -Path ".env" -Pattern '^DEEPSEEK_API_KEY=.+' -Quiet)
if (-not $envHasKey) {
    & $Py -c "import keyring,sys; sys.exit(0 if keyring.get_password('litchi-head','DEEPSEEK_API_KEY') else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  未检测到 DeepSeek 密钥：行情与图表可用，AI 研究会提示不可用。" -ForegroundColor Yellow
        Write-Host "   设置方法：.venv\Scripts\python.exe scripts\store-api-keys.py --set DEEPSEEK_API_KEY"
    }
}

# ── 4. Node / pnpm ─────────────────────────────────────────────
Step "检查 Node.js（需要 20 或更高，建议 24）"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Fail "没有找到 Node.js。" @("请从 https://nodejs.org/ 安装 LTS 版本后重试。")
}
$NodeMajor = [int](& node -p "process.versions.node.split('.')[0]")
if ($NodeMajor -lt 20) {
    Fail "Node.js 版本过低（当前 $(& node --version)）。" @("请升级到 20 或更高。")
}
Write-Host "Node.js $(& node --version)"
if (Get-Command pnpm -ErrorAction SilentlyContinue) { $Pnpm = "pnpm" }
elseif (Get-Command corepack -ErrorAction SilentlyContinue) { $Pnpm = "corepack pnpm@10.33.0" }
else { Fail "没有找到 pnpm。" @("请执行：npm install -g pnpm@10.33.0 后重试。") }

if (-not (Test-Path "frontend\node_modules")) {
    Step "安装前端依赖（首次运行，需要几分钟）"
    & cmd.exe /c "$Pnpm --dir frontend install --frozen-lockfile"
    if ($LASTEXITCODE -ne 0) { Fail "前端依赖安装失败。" @("请检查网络后重试。") }
}

# ── 5. 前端构建（源码有变化才重建） ────────────────────────────
$BuildId = "frontend\.next\BUILD_ID"
$NeedBuild = -not (Test-Path $BuildId)
if (-not $NeedBuild) {
    $builtAt = (Get-Item $BuildId).LastWriteTimeUtc
    $watched = @("frontend\app", "frontend\components", "frontend\lib", "frontend\package.json",
                 "frontend\next.config.ts", "frontend\pnpm-lock.yaml")
    $newer = Get-ChildItem -Path $watched -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -gt $builtAt } | Select-Object -First 1
    $NeedBuild = ($null -ne $newer)
}
if ($NeedBuild) {
    Step "构建前端（首次或界面有更新，约 1 分钟）"
    & cmd.exe /c "$Pnpm --dir frontend build > `"$FrontendLog`" 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Show-Tail $FrontendLog
        Fail "前端构建失败。" @("完整日志：$FrontendLog")
    }
}

# ── 6. 启动后端 ────────────────────────────────────────────────
try {
    Step "启动后端（端口 $BackendPort）"
    $Backend = Start-Process -FilePath $Py -PassThru -WindowStyle Hidden `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.err"
    $state = Wait-Ready $BackendUrl $Backend 90
    if ($state -ne "ok") {
        Show-Tail $BackendLog
        $why = if ($state -eq "exited") { "后端启动后立即退出。" } else { "后端 90 秒内没有就绪。" }
        Fail $why @("完整日志：$BackendLog.err")
    }
    Write-Host "后端就绪。"

    # ── 7. 启动前端 ────────────────────────────────────────────
    Step "启动前端（端口 $FrontendPort）"
    $Frontend = Start-Process -FilePath "cmd.exe" -PassThru -WindowStyle Hidden `
        -ArgumentList @("/c", "$Pnpm --dir frontend exec next start --port $FrontendPort") `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError "$FrontendLog.err"
    $state = Wait-Ready $FrontendUrl $Frontend 60
    if ($state -ne "ok") {
        Show-Tail $FrontendLog
        $why = if ($state -eq "exited") { "前端启动后立即退出。" } else { "前端 60 秒内没有就绪。" }
        Fail $why @("完整日志：$FrontendLog.err")
    }
    Write-Host "前端就绪。"

    # ── 8. 打开浏览器并等待 ────────────────────────────────────
    Start-Process $FrontendUrl
    Write-Host ""
    Write-Host "✅ 荔枝头已启动：$FrontendUrl" -ForegroundColor Green
    Write-Host "   日志目录：$LogDir"
    Write-Host "   在本窗口按回车键即停止；直接关窗口的话，请再双击 stop.bat。"
    Read-Host | Out-Null
}
finally {
    Stop-Tree $Frontend
    Stop-Tree $Backend
}
