# Task Plan: PokerGym v0.2

## Goal
在 D:\pokerv2 落地可玩、可测、可复现的 8-max 100bb NLH 训练场。

## Phases
- [x] Phase 0: 项目初始化（uv + pytest）
- [x] Phase 1: 牌局引擎 + 视角隔离 + 可复现采样
- [x] Phase 2: 意图状态机 + 翻前/面对下注/limp/多人池
- [x] Phase 3: 原型夹逼 + C 层人格 + B 层适应
- [x] Phase 4: Session / HUD / drill / 数学教练 / CLI
- [x] Phase 5: 22 tests 全绿，sim/drill/play 可跑

## Decisions Made
- 8-max 100bb，每手重载，盲注 0.5/1，内部 1bb=100 整数
- 不做 D 层；C 层表抽样；B 层规则，train/realism
- 强听 ≥8 outs
- 统计按原型盒子；WTSD 偏高是 8 人 limp 多人池的真实特征，不按线上 6-max 区间砍

## Status
**Done** — 引擎 22 测 + 桌面 UI（LiveSession/HTTP/夜场牌桌）。`uv run pytest` 26 passed。
`uv run python -m pokergym ui` 开桌。
