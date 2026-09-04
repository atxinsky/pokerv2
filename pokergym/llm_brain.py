"""全 LLM 出牌层：每个 bot 每次行动都问 DeepSeek。

原则：
- 只喂 BotView 能看到的公开信息 + 自己底牌，绝不泄漏他人底牌。
- LLM 输出动作 + 嘴炮（say），动作先 snap 到合法动作再落地。
- 任何失败（超时/坏 JSON/非法动作）都回退引擎 A 层，牌局永不阻塞。
- 只剩一种合法动作时不调 LLM，省钱省时间。
- 强度设定决定多少座位走 LLM（其余走频率 bot）。
"""

from __future__ import annotations

import os

from pokergym.archetypes import ARCHETYPE_ZH
from pokergym.cards import card_pretty
from pokergym.const import CHIP_PER_BB
from pokergym.deepseek import available, chat_json
from pokergym.legal import legal_actions, snap_action
from pokergym.personality import BotProfile
from pokergym.state import TableState
from pokergym.types import Action
from pokergym.view import build_bot_view

# 人设描述：让模型演出真人味，不是算牌机器
ARCHETYPE_STYLE = {
    "loose_passive": "你是条鱼：爱跟注、不爱弃牌、总想再看一张，怕输但又舍不得走。几乎不诈唬，被加注就慌，但经常硬着头皮跟。",
    "tight_passive": "你是块岩石：紧得要命，没牌就弃，别人一凶你就让。偶尔拿到大牌也只是跟注，不爱主动造池。",
    "tight_aggressive": "你是个 disciplined 的常客：挑牌打、讲位置、下注有目的。不咋呼过头，但该价值下注绝不手软。",
    "loose_aggressive": "你是个松凶玩家：牌桌搞得像你家开的，爱施压、爱咋呼、喜欢用加注把人打跑，享受别人弃牌给你看。",
    "maniac": "你是个疯子：筹码是拿来推的，不是拿来数的。大开大合，诈唬成性，嘴上还不饶人。",
}

SESSION_MOOD = {
    "normal": "今晚状态平常。",
    "tilted": "今晚你上头了，刚输了不少，想翻本，容易冲动跟注或乱加注。",
    "conservative": "今晚你打得很保守，怕输，能过就过，能弃就弃。",
    "fatigued": "今晚你很疲惫，注意力涣散，偶尔做出莫名其妙的决定。",
}

STREET_ZH = {"pre": "翻前", "flop": "翻牌", "turn": "转牌", "river": "河牌"}

KIND_ZH = {"fold": "弃牌", "check": "过牌", "call": "跟注", "bet": "下注", "raise": "加注"}

_INTENSITY_FRAC = {
    "full": 1.0,
    "high": 0.75,
    "med": 0.5,
    "low": 0.25,
    "sparse": 0.25,
}


def brain_enabled() -> bool:
    """全 LLM 出牌开关：设置里开了 + DeepSeek 可用才生效。"""
    try:
        from pokergym.store import apply_env

        apply_env()
    except Exception:
        pass
    if os.environ.get("POKERGYM_LLM_BRAIN", "0") != "1":
        return False
    return available()


def brain_timeout() -> float:
    try:
        from pokergym.store import apply_env

        apply_env()
    except Exception:
        pass
    try:
        t = float(os.environ.get("POKERGYM_LLM_BRAIN_TIMEOUT", "12"))
    except (TypeError, ValueError):
        t = 12.0
    return max(3.0, min(30.0, t))


def brain_intensity(mode: str | None = None) -> str:
    try:
        from pokergym.store import apply_env

        apply_env()
    except Exception:
        pass
    v = (os.environ.get("POKERGYM_LLM_BRAIN_INTENSITY") or "full").strip().lower()
    if v not in _INTENSITY_FRAC:
        v = "full"
    if mode:
        try:
            from pokergym.modes import effective_intensity

            return effective_intensity(v, mode)
        except Exception:
            return v
    return v


def seat_uses_llm(seat: int, hero_seat: int, n_seats: int, mode: str | None = None) -> bool:
    """按强度决定该座位是否走 LLM。确定性：按座位号排序后取前 k 个对手。"""
    if not brain_enabled():
        return False
    frac = _INTENSITY_FRAC.get(brain_intensity(mode), 1.0)
    bots = [s for s in range(n_seats) if s != hero_seat]
    if not bots:
        return False
    k = max(1, int(round(len(bots) * frac))) if frac > 0 else 0
    if frac >= 0.999:
        k = len(bots)
    chosen = sorted(bots)[:k]
    return seat in chosen


def _cards_text(cards) -> str:
    return " ".join(card_pretty(c) for c in cards)


def _history_lines(view, names: dict[int, str]) -> list[str]:
    """公开行动日志转中文流水。只含公共信息。"""
    lines = []
    for a in view.action_log[-24:]:
        who = names.get(a.seat, f"座位{a.seat}")
        street = STREET_ZH.get(a.street, a.street)
        kind = KIND_ZH.get(a.kind, a.kind)
        if a.kind in ("bet", "raise"):
            lines.append(f"[{street}] {who} {kind}到 {a.to_chips / CHIP_PER_BB:.1f}bb")
        elif a.kind == "call":
            lines.append(f"[{street}] {who} 跟注 {a.put_chips / CHIP_PER_BB:.1f}bb")
        else:
            lines.append(f"[{street}] {who} {kind}")
    return lines


def _legal_text(view, legal) -> str:
    """把合法动作摆成选项，下注/加注给尺度区间。"""
    parts = []
    kinds = {a.kind for a in legal}
    if "fold" in kinds:
        parts.append("fold 弃牌")
    if "check" in kinds:
        parts.append("check 过牌")
    if "call" in kinds:
        parts.append(f"call 跟注（再投入 {view.to_call_bb:.1f}bb）")
    if "bet" in kinds:
        max_to = (view.my_stack_bb + view.bet_street_bb)
        parts.append(f"bet 下注，to_bb=本街累计下到多少，范围 1 ~ {max_to:.1f}")
    if "raise" in kinds:
        max_to = (view.my_stack_bb + view.bet_street_bb)
        parts.append(f"raise 加注，to_bb=本街累计加到多少，范围 {view.min_raise_to_bb:.1f} ~ {max_to:.1f}")
    return "；".join(parts)


def decide_llm(
    st: TableState,
    bot: BotProfile,
    names: dict[int, str],
    lost_big: bool = False,
    timeout: float | None = None,
    mode: str | None = None,
) -> tuple[Action, str] | None:
    """问 DeepSeek 这手怎么打。返回 (动作, 嘴炮)；不需要决策或失败返回 None。"""
    seat = bot.seat
    legal = legal_actions(st, seat)
    kinds = {a.kind for a in legal}
    if len(kinds) <= 1:
        return None  # 没得选，别浪费调用
    view = build_bot_view(seat, st)

    style = ARCHETYPE_STYLE.get(bot.archetype, "")
    mood = SESSION_MOOD.get(bot.session.kind, "")
    if lost_big:
        mood += " 你上一手刚输了个大底池，心里憋着火。"
    leaks = ""
    if bot.leaks:
        leak_txt = {
            "faced_3bet": "被 3bet 时你特别容易怂",
            "multiway_pot": "多人底池你总爱多看一张",
            "river_faced_bet": "河牌被下注你容易弃牌",
            "just_lost_big_pot": "输完大 pot 你会乱来",
            "in_blinds": "在盲注位你防守偏随意",
        }
        leaks = "你的老毛病：" + "；".join(leak_txt.get(l.trigger, l.trigger) for l in bot.leaks) + "。"

    try:
        from pokergym.modes import realism_tougher_prompt_extra

        tough = realism_tougher_prompt_extra(mode or "")
    except Exception:
        tough = ""
    sys = (
        f"你是{bot.name}，线下俱乐部 8 人桌现金局（盲注 0.5/1，100bb 买入）里的真人玩家。你不是 AI，也不提概率公式。"
        f"{ARCHETYPE_ZH.get(bot.archetype, '')}。{style}{mood}{leaks}{tough}"
        "轮到你行动时，像真人一样凭感觉和人设做决定：可以咋呼（诈唬）、可以演、可以上头了乱来，但要符合你的人设，别每手都打得一样。"
        "只输出 JSON：{\"action\":\"fold|check|call|bet|raise\",\"to_bb\":数字或null,\"say\":\"桌上说的一句话\"}。"
        "action 必须选合法动作之一；bet/raise 时 to_bb 是本街累计下注到多少 bb，必须在给定范围内；"
        "say 是嘴炮/吐槽/挑衅/自言自语，20 字以内的中文口语，符合人设，不想说就给空串。"
    )

    board_txt = _cards_text(view.board) if view.board else "（未发）"
    hist = _history_lines(view, names)
    user = {
        "街道": STREET_ZH.get(view.street, view.street),
        "你的位置": view.position,
        "你的底牌": _cards_text(view.hole),
        "公共牌": board_txt,
        "底池_bb": round(view.pot_bb, 1),
        "要跟注_bb": round(view.to_call_bb, 1),
        "你的后手_bb": round(view.my_stack_bb, 1),
        "还在局里的人数": view.n_active,
        "本手到目前为止的行动": hist or ["（你是第一个行动的）"],
        "合法动作": _legal_text(view, legal),
    }
    import json

    to = brain_timeout() if timeout is None else timeout
    data = chat_json(sys, json.dumps(user, ensure_ascii=False), timeout=to, temperature=0.85, max_tokens=220)
    if not data:
        return None
    kind = str(data.get("action") or "").strip().lower()
    if kind not in ("fold", "check", "call", "bet", "raise"):
        return None
    to_chips = None
    if kind in ("bet", "raise"):
        try:
            to_chips = int(round(float(data.get("to_bb")) * CHIP_PER_BB))
        except (TypeError, ValueError):
            return None
    say = str(data.get("say") or "").strip()[:40]
    action = snap_action(st, seat, Action(kind, to_chips))
    return action, say
