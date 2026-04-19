<#
用途：
- 一键打开 3 个 CMD 终端窗口，并自动激活 conda 环境 `ITS_Multi_Agent`。
- 分别启动：
  1) backend/app 的 FastAPI (8000)
  2) backend/knowledge 的 FastAPI (8001)
  3) front/agent_web_ui 的前端开发服务

使用方法：
1) 在项目根目录打开终端（例如：C:\Users\Lenovo\Desktop\geo_multi_agent）
2) 执行：
   powershell -ExecutionPolicy Bypass -File .\start-dev-terminals.ps1

可选：
- 若想调整启动速度，修改 `$StartupDelaySeconds`（单位：秒）。
- 若要更换 conda 环境，修改 `$CondaEnv`。
#>

$ErrorActionPreference = 'Stop'

# 项目根目录（当前执行目录）
$ProjectRoot = (Get-Location).Path
$CondaEnv = 'ITS_Multi_Agent'

# 启动间隔（秒），避免三个终端瞬间同时抢资源
$StartupDelaySeconds = 3

function Start-CmdDevTerminal {
    param(
        [string]$Title,
        [string[]]$Commands
    )

    # 在 cmd 中执行：切到项目根目录 -> 激活 conda 环境 -> 执行业务命令
    $all = @(
        "title $Title",
        "cd /d ""$ProjectRoot""",
        "call conda activate $CondaEnv"
    ) + $Commands

    $cmdLine = ($all -join ' && ')

    Start-Process -FilePath 'cmd.exe' -ArgumentList @('/k', $cmdLine)
}

# 1) backend/app API
Start-CmdDevTerminal -Title 'GeoAgent-Backend-App' -Commands @(
    'cd /d "backend\app"',
    'python -m uvicorn api.main:create_fast_api --factory --reload'
)
Start-Sleep -Seconds $StartupDelaySeconds

# 2) backend/knowledge: 先上传知识，再启动 API(8001)
Start-CmdDevTerminal -Title 'GeoAgent-Knowledge' -Commands @(
    'cd /d "backend\knowledge"',
    # 'python -m cli.upload_cli',
    'python -m uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8001 --reload'
)
Start-Sleep -Seconds $StartupDelaySeconds

# 3) front/agent_web_ui
Start-CmdDevTerminal -Title 'GeoAgent-Frontend' -Commands @(
    'cd /d "front\agent_web_ui"',
    'npm run dev'
)

Write-Host 'Started 3 CMD terminal windows (with conda activation + startup delay).'
