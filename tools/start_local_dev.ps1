<#
.SYNOPSIS
  一键启动 AI Banking Agent 本机体验环境（后端 FastAPI + 前端 Vite dev）。
.DESCRIPTION
  - 校验首次配置（.env.local-demo.json、backend/.venv），缺失时给出 LOCAL-DEV.md 指引
  - 后端：uvicorn app.agent_platform.local_demo（用户 U1 + 管理 demo-admin），端口 8000
  - 前端：npm run dev（real-api 模式，代理 127.0.0.1:8000），端口 5173
  - 两个服务各自独立窗口运行；脚本等待期间按任意键或 Ctrl+C 停止两者（含子进程树）
  - 演示剧本见 backend/app/agent_platform/LOCAL-DEV.md（500/501/502/600 元）
.PARAMETER SkipNpmInstall
  跳过 node_modules 缺失检查（依赖已装好时更快）。
.PARAMETER BackendOnly
  只起后端（调试用）。
.EXAMPLE
  pwsh tools/start_local_dev.ps1
#>
[CmdletBinding()]
param(
  [switch]$SkipNpmInstall,
  [switch]$BackendOnly
)
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$config = Join-Path $root '.env.local-demo.json'
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

if (-not (Test-Path $config)) {
  Write-Error "缺少首次配置：$config`n请按 backend/app/agent_platform/LOCAL-DEV.md 执行首次配置（Copy-Item local_demo.example.json -> .env.local-demo.json 并填写密钥）后重试。"
  exit 1
}
if (-not (Test-Path $python)) {
  Write-Error "缺少虚拟环境：$python`n请先执行 backend/.venv/Scripts/python -m pip install -e 'backend[dev]'。"
  exit 1
}
if (-not $SkipNpmInstall -and -not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
  Write-Host '首次运行：安装前端依赖 npm ci ...'
  Push-Location $frontendDir
  try { npm ci } finally { Pop-Location }
}

$env:BANK_LOCAL_CONFIG = $config
Write-Host "配置：$config"

$backend = Start-Process -FilePath $python `
  -ArgumentList @('-m', 'uvicorn', 'app.agent_platform.local_demo:create_local_app',
                  '--factory', '--host', '127.0.0.1', '--port', '8000',
                  '--workers', '1', '--no-access-log') `
  -WorkingDirectory $backendDir -PassThru

$deadline = (Get-Date).AddSeconds(30)
$ready = $false
while ((Get-Date) -lt $deadline) {
  if (Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    $ready = $true; break
  }
  Start-Sleep -Milliseconds 500
}
if (-not $ready) {
  try { taskkill /PID $backend.Id /T /F | Out-Null } catch { }
  Write-Error '后端未在 30 秒内就绪：请查看后端窗口日志（配置错误、端口占用或凭证无效）。'
  exit 1
}
Write-Host '后端已就绪：http://127.0.0.1:8000'

if ($BackendOnly) {
  Write-Host '按任意键结束后端...'
  $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
  try { taskkill /PID $backend.Id /T /F | Out-Null } catch { }
  exit 0
}

$frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') `
  -WorkingDirectory $frontendDir -PassThru
Start-Sleep -Seconds 5

Write-Host @"

  AI Banking Agent 本机体验已启动
  ------------------------------------------------
  用户页面 : http://127.0.0.1:5173/        （用户 U1）
  管理页面 : http://localhost:5173/admin   （管理密钥见 .env.local-demo.json 的 admin_key）
  后端 API : http://127.0.0.1:8000
  演示剧本 : 给妈妈转500元(A1)=低风险 · 501=中风险(需模拟人脸) · 502=高风险终止 · 600=修改演示
  注意事项 : 风险事实为演示数据；机器人确认阶段可能"失忆"(#84)；账单/联动未上线
  按任意键（或 Ctrl+C）停止两个服务。
"@
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')

try { taskkill /PID $backend.Id /T /F | Out-Null } catch { }
if ($frontend) { try { taskkill /PID $frontend.Id /T /F | Out-Null } catch { } }
Write-Host '服务已停止。'