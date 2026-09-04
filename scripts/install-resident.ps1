# PokerGym 常驻服务安装（开机自启 + 崩溃自动拉起，无窗口后台跑）
# 用法：右键用 PowerShell 运行，或 powershell -File scripts\install-resident.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    # pythonw 不存在就退回 python（会多个黑窗，但能用）
    $pythonw = Join-Path $root ".venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonw)) { throw "找不到虚拟环境：$root\.venv，先 uv sync" }

$taskName = "PokerGym"
$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "-m pokergym serve --port 8765" `
    -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -StartWhenAvailable

# 幂等：有旧任务先卸
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "PokerGym 本地常驻服务 http://127.0.0.1:8765/" | Out-Null

# 立刻拉起一次，不用等重启
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2

try {
    $null = Invoke-RestMethod "http://127.0.0.1:8765/api/settings" -TimeoutSec 5
    Write-Host "OK：PokerGym 已常驻，地址 http://127.0.0.1:8765/"
    Write-Host "打牌入口：双击 scripts\open-table.bat（建议给它建个桌面快捷方式）"
    Write-Host "卸载：powershell -File scripts\uninstall-resident.ps1"
} catch {
    Write-Host "任务已注册但服务还没起来，等几秒后访问 http://127.0.0.1:8765/ 看看"
}
