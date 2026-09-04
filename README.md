# PokerGym

本机 **8-max / 100bb** 现金局训练器。产品卖点是 **LLM 对手（真决策）+ LLM 教练（手后复盘 / 可选轻提示）**；右侧 GTO 范围图只作参考辅助，不是 solver 级 GTO。

既有引擎 + 频率 bot + DeepSeek 层 + 夜店风 UI。筹码为练习筹码，不联网、不真钱。

## 模式

- **训练**：教练默认开，可开决策前短提示；对手适应更快。
- **拟真**：少提示（强制关掉决策前提示），LLM 对手覆盖更猛一档；B 层适应更慢更像真人。

设置里可看 **本席 / 累计 token 用量与费用粗估**，并 **一键降档** 减少用 LLM 的对手数。

## 核心规则

- 格式：8-max，盲注 0.5/1，每手买入 100bb
- 原型：鱼 / 岩石 / TAG / LAG / 疯子（含今晚状态与漏洞）
- 对手：有 Key 时默认全桌 LLM 出牌（失败/超时回落频率 bot）；强度可配
- 教练：手后自动复盘；决策前短提示默认关；弱项 drill 仍可后续增强
- GTO：静态范围图仅供参考，勿当成 solver
- 信息隔离：bot 决策只看 `BotView`；CI 测泄漏

## 命令

```bash
cd D:\pokerv2
uv run pytest
uv run python -m pokergym ui
uv run python -m pokergym sim --hands 400 --seed 3
uv run python -m pokergym drill --hands 200
uv run python -m pokergym play --seed 1
```

`ui` 拉起本地夜店风窗口（Edge/Chrome `--app`）并挂系统托盘。

## 本机常驻

```powershell
powershell -File scripts\install-resident.ps1   # 开机托盘 + 登录自启（计划任务，无窗口）
scripts\open-table.bat                          # 一键开桌（可做桌面快捷方式）
powershell -File scripts\uninstall-resident.ps1 # 卸载
```

常驻服务固定 `http://127.0.0.1:8765/`。填 DeepSeek：`D:\pokerv2\.env` 写 `DEEPSEEK_API_KEY`，或在设置页保存。无 Key 时用规则人格/频率 bot。

快捷键：`F` 弃 · `X` 过 · `C` 跟 · 空格 过/跟 · `A` 全下 · 回车 确认尺度 / 下一手。

## 结构

```
pokergym/     引擎 + bot + LiveSession + HTTP
web/          夜店风前端（HTML/CSS/JS）
tests/        引擎 / 线程 / 泄漏 / 适应 / API / LLM mock
```
