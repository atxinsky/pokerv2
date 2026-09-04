# 卸载 PokerGym 常驻服务
$taskName = "PokerGym"
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "已停止并卸载 PokerGym 常驻任务"
