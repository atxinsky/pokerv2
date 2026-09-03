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

快捷键：`F` 弃 · `X` 过 · `C` 跟 · 空格 过/跟 · `A` 全下 · 回车 确认尺度 / 下一手。

`play` 输入：`f` 弃 / `x` 过 / `c` 跟 / `b 12` 下注到 12bb / `r 9` 加到 9bb / `a` 全下 / `q` 退出。

## 结构

```
pokergym/     引擎 + bot + LiveSession + HTTP
web/          夜场牌桌（HTML/CSS/JS）
tests/        评估器 / 边池 / 泄漏 / 复现 / 适应 / API
```
