"""轮到英雄时，用 DeepSeek 说一句人话。数值用引擎的，模型不准自己算。"""

from __future__ import annotations

from pokergym.deepseek import available, chat_json
from pokergym.ranges import hole_code
from pokergym.store import log_llm
from pokergym.types import BotView


def comment_spot(view: BotView, local: dict) -> str | None:
    if not available():
        return None
    code = hole_code(view.hole)
    payload = {
        "position": view.position,
        "street": view.street,
        "hand": code,
        "pot_bb": round(view.pot_bb, 2),
        "to_call_bb": round(view.to_call_bb, 2),
        "n_opponents": view.n_opponents,
        "equity": local.get("equity"),
        "engine_action": local.get("action_zh"),
        "engine_why": local.get("why"),
    }
    sys = (
        "你是线下现金局教练，站在玩家身后说话。"
        "只输出 JSON：{\"comment\":\"...\"}。"
        "comment 一两句中文口语，不要复述数字，不要自己计算胜率，直接用给定结论。"
        "可以同意或补充引擎建议。"
    )
    data = chat_json(sys, "当前决策点：" + str(payload), timeout=10)
    if not data:
        log_llm("教练点评调用失败")
        return None
    text = str(data.get("comment") or "").strip()
    if not text:
        return None
    log_llm("DeepSeek 点评：" + text[:80])
    return text[:160]
