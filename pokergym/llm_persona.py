"""C/B 层 DeepSeek：异步，失败则保持规则人格。"""

from __future__ import annotations

import threading

from pokergym.archetypes import ARCHETYPE_RANGE, ARCHETYPE_ZH, clamp_params
from pokergym.deepseek import available, chat_json, clamp_delta
from pokergym.digest import hero_digest, n_obs
from pokergym.params import ParamUpdate, SessionState, SignatureLeak

_lock = threading.Lock()


def format_digest(d: dict) -> str:
    lines = [
        f"观察手数：{d['hands_observed']}",
        f"入池率约 {d['vpip']:.0%}，翻前加注率约 {d['pfr']:.0%}",
    ]
    for name in ("vs_3bet", "vs_open", "vs_cbet", "river_faced_bet", "river_agg"):
        tot = d["counters"].get(f"{name}.total", 0)
        if tot < 2:
            continue
        parts = [
            f"{a}{d['counters'].get(f'{name}.{a}', 0)}"
            for a in ("fold", "call", "raise", "bet", "check")
            if d["counters"].get(f"{name}.{a}")
        ]
        lines.append(f"{name}（{tot}次）：{' / '.join(parts)}")
    return "\n".join(lines)


def enrich_bots_async(bots: dict, rng_seed: int = 1) -> None:
    if not available() or not bots:
        return

    def work():
        payload = []
        for seat, b in bots.items():
            payload.append(
                {
                    "seat": seat,
                    "archetype": b.archetype,
                    "archetype_zh": ARCHETYPE_ZH[b.archetype],
                    "base": {k: round(v, 3) for k, v in list(b.base_params.items())[:8]},
                }
            )
        sys = (
            "你是线下俱乐部发牌员，给德州训练器生成 NPC 人格。"
            "只输出 JSON：{\"bots\":[...]}。"
            "每个 bot：name(2-4字中文昵称), session(normal|tilted|conservative|fatigued),"
            "leaks: 最多2条 {trigger, delta}。"
            "trigger 只能是 faced_3bet/multiway_pot/river_faced_bet/just_lost_big_pot/in_blinds。"
            "delta 只能调 fold_to_3bet/bluff_mult/call_station_idx/cbet_freq，绝对值≤0.15。"
            "禁止计算胜率。"
        )
        user = "生成这些座位的人格：\n" + json_dumps(payload)
        data = chat_json(sys, user, timeout=14)
        if not data or "bots" not in data:
            return
        with _lock:
            for item in data["bots"]:
                try:
                    seat = int(item.get("seat"))
                except (TypeError, ValueError):
                    continue
                bot = bots.get(seat)
                if not bot:
                    continue
                name = str(item.get("name") or "").strip()
                if 2 <= len(name) <= 4:
                    bot.name = name
                sess = item.get("session")
                if sess in ("normal", "tilted", "conservative", "fatigued"):
                    from pokergym.personality import SESSION_MULT

                    bot.session = SessionState(
                        kind=sess,
                        multipliers=dict(SESSION_MULT.get(sess, {})),
                        start_hand=bot.session.start_hand,
                        decay_hands=bot.session.decay_hands,
                    )
                leaks = []
                for lk in item.get("leaks") or []:
                    trig = lk.get("trigger")
                    delta = clamp_delta(lk.get("delta") or {})
                    # leaks 用的键可能不在 ALLOWED_DELTA，放行 fold_to_3bet
                    extra = {}
                    if isinstance(lk.get("delta"), dict):
                        for k, v in lk["delta"].items():
                            if k in ("fold_to_3bet", "bluff_mult", "call_station_idx", "cbet_freq"):
                                try:
                                    extra[k] = max(-0.15, min(0.15, float(v)))
                                except (TypeError, ValueError):
                                    pass
                    extra.update(delta)
                    if trig and extra:
                        leaks.append(SignatureLeak(trigger=str(trig), delta=extra))
                if leaks:
                    bot.leaks = leaks[:2]
                bot.hero_notes = ["DeepSeek 人格已加载"][:3]

    threading.Thread(target=work, daemon=True).start()


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def adapt_bots_async(bots: dict, hands, hero_seat: int, hand_idx: int, mode: str) -> None:
    if not available() or hero_seat is None:
        return
    due = [b for b in bots.values() if b.hands_since_update >= b.next_update_at]
    if not due:
        return
    d = hero_digest(hands, hero_seat, window=20 if mode == "train" else 40)
    if d["hands_observed"] < 8:
        return
    text = format_digest(d)

    def work():
        specs = [
            {
                "seat": b.seat,
                "name": b.name,
                "archetype": b.archetype,
                "zh": ARCHETYPE_ZH[b.archetype],
            }
            for b in due
        ]
        sys = (
            "你是牌桌上的老玩家。根据对手统计调整自己的参数。"
            "只输出 JSON：{\"updates\":[{\"seat\":0,\"delta\":{},\"notes\":[\"...\"]}] }。"
            "delta 键只能是 threebet_freq/squeeze_freq/bluff_mult/cbet_freq/"
            "fold_to_cbet/call_station_idx/river_bluff_freq/fold_bias，"
            "值为相对增量，绝对值≤0.15。"
            "松被动不会突然猛诈唬。样本少就少改。"
        )
        user = f"对手摘要：\n{text}\n\n这些座位要调整：\n{json_dumps(specs)}"
        data = chat_json(sys, user, timeout=14)
        if not data:
            return
        with _lock:
            for item in data.get("updates") or []:
                try:
                    seat = int(item.get("seat"))
                except (TypeError, ValueError):
                    continue
                bot = bots.get(seat)
                if not bot:
                    continue
                delta = clamp_delta(item.get("delta"))
                if not delta:
                    continue
                if bot.archetype == "loose_passive":
                    delta.pop("bluff_mult", None)
                bot.updates.append(
                    ParamUpdate(
                        delta=delta,
                        applied_at=hand_idx,
                        decay_hands=50,
                        confidence=0.7,
                    )
                )
                notes = item.get("notes") or []
                bot.hero_notes = [str(x) for x in notes][:3] or [f"{k}:{v:+.2f}" for k, v in delta.items()][:3]
                bot.hands_since_update = 0
                bot.next_update_at = 18 if mode == "train" else 28

    for b in due:
        b.hands_since_update = 0  # 避免重复排队
        b.next_update_at = 18 if mode == "train" else 28
    threading.Thread(target=work, daemon=True).start()
