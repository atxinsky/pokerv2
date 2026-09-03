# PokerGym v0.2

8 人桌、100bb 现金、无限注德州训练场。动作由引擎按频率采样，LLM 不选动作，v1 不做 D 层。

## 钉死的规格

- 格式：8-max，盲注 0.5/1，每手重载 100bb
- 对手：鱼 / 岩石 / TAG / LAG / 疯子，参数夹在原型盒子里
- C 层：表抽样人格（今晚状态 + 标志漏洞），不调 LLM
- B 层：规则适应。`train` 快狠，`realism` 慢且鱼/岩石几乎不改
- 强听：≥8 outs（同花听算强听）
- 视角隔离：bot 决策只看 `BotView`，CI 断言他人底牌进不去

## 命令

```bash
cd D:\pokerv2
uv run pytest
uv run python -m pokergym ui
uv run python -m pokergym sim --hands 400 --seed 3
uv run python -m pokergym drill --hands 200
uv run python -m pokergym play --seed 1
```

`ui` 会起本地夜场窗口（Edge/Chrome `--app`，否则系统浏览器）。

对手拟人（C/B 层）接 DeepSeek：在 `D:\pokerv2\.env` 写入 `DEEPSEEK_API_KEY`。没密钥时用规则人格，牌局不阻塞。

**全 LLM 出牌模式**（设置页开关，或环境变量 `POKERGYM_LLM_BRAIN=1`）：每个 bot 每次行动都实时问 DeepSeek，按人设（鱼/岩石/TAG/LAG/疯子 + 今晚状态 + 老毛病）做决定，还会飙嘴炮（座位气泡）。慢（每决策约 1 秒）且烧钱；LLM 超时/乱答时引擎自动兜底，牌局永不卡死。只剩一种合法动作时不调 LLM。LLM 只能看到 BotView 公开信息，CI 断言你的底牌进不了 prompt。

不开此模式时：动作仍由引擎采样，LLM 只改性格和适应。

快捷键：`F` 弃 · `X` 过 · `C` 跟 · 空格 过/跟 · `A` 全下 · 回车 确认尺度 / 下一手。

`play` 输入：`f` 弃 / `x` 过 / `c` 跟 / `b 12` 下注到 12bb / `r 9` 加到 9bb / `a` 全下 / `q` 退出。

## 结构

```
pokergym/     引擎 + bot + LiveSession + HTTP
web/          夜场牌桌（HTML/CSS/JS）
tests/        评估器 / 边池 / 泄漏 / 复现 / 适应 / API
```
