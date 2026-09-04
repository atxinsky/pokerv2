"""脚本英雄 + 泄漏训练 + 弱项定向 drill。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pokergym.preflop import classify_preflop, materialize_preflop
from pokergym.ranges import percentile
from pokergym.table import HeroPolicy, run_session
from pokergym.types import Action, BotView

# ---------------------------------------------------------------------------
# Static theme packs (always available; no network)
# ---------------------------------------------------------------------------

THEME_PACKS: dict[str, dict[str, Any]] = {
    "overfold_3bet": {
        "id": "overfold_3bet",
        "label": "面对 3bet 防守",
        "tags": ["overfold_3bet"],
        "keywords": ["3bet", "过弃", "面对加注", "四赌", "4bet"],
        "focus": "练习面对 3bet 时用强牌跟注/4bet，而不是习惯性弃牌。",
        "bot_prefer": ["tight_aggressive", "loose_aggressive", "maniac"],
        "param_boost": {"threebet_freq": 1.35},
        "hero_pos": "BTN",
    },
    "threebet_pot": {
        "id": "threebet_pot",
        "label": "3bet 底池",
        "tags": ["overfold_3bet"],
        "keywords": ["3bet 底池", "三赌底池", "SPR"],
        "focus": "进入 3bet 底池后按 SPR 与牌力规划 c-bet / 弃牌。",
        "bot_prefer": ["tight_aggressive", "loose_aggressive"],
        "param_boost": {"threebet_freq": 1.25, "cbet_freq": 1.15},
        "hero_pos": "CO",
    },
    "cbet": {
        "id": "cbet",
        "label": "持续下注 c-bet",
        "tags": [],
        "keywords": ["c-bet", "cbet", "持续下注", "翻后下注"],
        "focus": "作为翻前进攻方，在合适纹理上用正确频率做 c-bet。",
        "bot_prefer": ["loose_passive", "tight_passive"],
        "param_boost": {"fold_to_cbet": 1.1},
        "hero_pos": "BTN",
    },
    "river_bluff_catch": {
        "id": "river_bluff_catch",
        "label": "河牌抓诈",
        "tags": ["overfold_river"],
        "keywords": ["河牌", "抓诈", "bluff catch", "过弃河牌", "摊牌价值"],
        "focus": "河牌面对下注时，用中等牌力按赔率决定跟注还是弃牌。",
        "bot_prefer": ["loose_aggressive", "maniac"],
        "param_boost": {"bluff_mult": 1.3},
        "hero_pos": "BB",
    },
    "overfold_river": {
        "id": "overfold_river",
        "label": "河牌过弃",
        "tags": ["overfold_river"],
        "keywords": ["河牌过弃", "overfold", "摊牌"],
        "focus": "纠正河牌面对下注时弃掉仍有摊牌价值的牌。",
        "bot_prefer": ["loose_aggressive", "maniac"],
        "param_boost": {"bluff_mult": 1.25},
        "hero_pos": "BB",
    },
    "underopen": {
        "id": "underopen",
        "label": "该开却弃",
        "tags": ["underopen"],
        "keywords": ["该开", "开池", "underopen", "偷盲"],
        "focus": "在后位用范围内的牌正常开池，不要乱弃。",
        "bot_prefer": ["loose_passive", "tight_passive"],
        "param_boost": {},
        "hero_pos": "CO",
    },
    "no_iso": {
        "id": "no_iso",
        "label": "对 limp 加注",
        "tags": ["no_iso"],
        "keywords": ["limp", "iso", "隔离", "平跟 limp"],
        "focus": "面对 limp 用强牌隔离加注，而不是平跟进池。",
        "bot_prefer": ["loose_passive"],
        "param_boost": {"vpip": 1.15},
        "hero_pos": "BTN",
    },
    "calling_station": {
        "id": "calling_station",
        "label": "避免跟注站",
        "tags": ["calling_station"],
        "keywords": ["跟注站", "calling station", "空气跟注", "赔率不够"],
        "focus": "赔率不够且牌力弱时果断弃牌，不要变成跟注站。",
        "bot_prefer": ["tight_aggressive", "loose_aggressive"],
        "param_boost": {"cbet_freq": 1.2, "bluff_mult": 1.15},
        "hero_pos": "BB",
    },
}

DEFAULT_THEME_ID = "cbet"


class AlwaysFoldTo3Bet(HeroPolicy):
    """面前总开却面对 3bet 永远弃——训练 B 层。"""

    def decide(self, view: BotView, st) -> Action:
        if view.street != "pre":
            if view.to_call_bb > 0:
                return Action("fold") if "fold" in view.legal_kinds else Action("call")
            return Action("check") if "check" in view.legal_kinds else Action("fold")
        seq = classify_preflop(view.action_log)
        if seq.facing == "threebet":
            return Action("fold")
        if seq.facing == "unopened" and percentile(view.hole) <= 0.40:
            return materialize_preflop("open", view, {"sizing_bias": 1.0})
        if seq.facing == "limp":
            return materialize_preflop("iso", view, {"sizing_bias": 1.0})
        return Action("fold")


class CallingStation(HeroPolicy):
    def decide(self, view: BotView, st) -> Action:
        if "check" in view.legal_kinds:
            return Action("check")
        if "call" in view.legal_kinds:
            return Action("call")
        return Action("fold")


class AlwaysFoldRiver(HeroPolicy):
    def decide(self, view: BotView, st) -> Action:
        if view.street == "river" and view.to_call_bb > 0:
            return Action("fold")
        if view.street == "pre":
            seq = classify_preflop(view.action_log)
            if seq.facing == "unopened" and percentile(view.hole) <= 0.25:
                return materialize_preflop("open", view, {"sizing_bias": 1.0})
        if "check" in view.legal_kinds:
            return Action("check")
        if "call" in view.legal_kinds:
            return Action("call")
        return Action("fold")


def threebet_rate(result, start: int, end: int, hero_seat: int = 0) -> float:
    """只统计：英雄开池之后是否遭遇 3bet。"""
    hands = result.hands[start:end]
    opens = 0
    threes = 0
    for h in hands:
        hero_opened = False
        got_3bet = False
        for n in h.nodes:
            if n.street != "pre":
                continue
            if n.seat == hero_seat and n.action in ("raise", "open") and n.faced in (
                "unopened",
                "limp",
            ):
                hero_opened = True
            if (
                hero_opened
                and n.seat != hero_seat
                and n.action == "raise"
                and n.faced in ("open", "open_calls")
            ):
                got_3bet = True
        if hero_opened:
            opens += 1
            if got_3bet:
                threes += 1
    return threes / max(opens, 1)


def _agg_threebet_mult(result) -> float:
    from pokergym.params import resolve_params

    ratios = []
    last = result.hands[-1].hand_idx if result.hands else 0
    for b in result.bots.values():
        if b.archetype not in ("tight_aggressive", "loose_aggressive", "maniac"):
            continue
        p = resolve_params(
            b.archetype, b.base_params, b.session, b.updates, b.leaks, set(), last
        )
        ratios.append(p["threebet_freq"] / max(b.base_params["threebet_freq"], 1e-6))
    return sum(ratios) / max(len(ratios), 1)


def run_fold_to_3bet_drill(seed: int = 9, hands: int = 200) -> dict:
    hero = AlwaysFoldTo3Bet()
    res = run_session(seed=seed, n_hands=hands, hero=hero, mode="train")
    early = threebet_rate(res, 0, min(50, hands // 4), hero.seat)
    late = threebet_rate(res, max(0, hands - 50), hands, hero.seat)
    param_mult = _agg_threebet_mult(res)
    return {
        "early": early,
        "late": late,
        "lift": late / max(early, 1e-6),
        "param_mult": param_mult,
        "result": res,
    }


# ---------------------------------------------------------------------------
# Weakness mining + theme selection
# ---------------------------------------------------------------------------


def list_themes() -> list[dict[str, Any]]:
    """Public catalog for CLI / API / UI."""
    out = []
    for tid, pack in THEME_PACKS.items():
        out.append(
            {
                "id": tid,
                "label": pack["label"],
                "focus": pack["focus"],
                "tags": list(pack.get("tags") or []),
            }
        )
    return out


def get_theme(theme_id: str | None) -> dict[str, Any]:
    tid = (theme_id or "").strip()
    if tid in THEME_PACKS:
        pack = THEME_PACKS[tid]
        return {
            "id": pack["id"],
            "label": pack["label"],
            "focus": pack["focus"],
            "tags": list(pack.get("tags") or []),
            "source": "theme",
        }
    pack = THEME_PACKS[DEFAULT_THEME_ID]
    return {
        "id": pack["id"],
        "label": pack["label"],
        "focus": pack["focus"],
        "tags": list(pack.get("tags") or []),
        "source": "default",
    }


def _hands_from_store(limit: int = 200) -> list[dict]:
    try:
        from pokergym.store import list_hands

        return list_hands(limit=limit)
    except Exception:
        return []


def _tag_counts(hands: list[dict]) -> Counter:
    c: Counter = Counter()
    for h in hands:
        for t in h.get("tags") or []:
            if isinstance(t, str) and t:
                c[t] += 1
        rev = h.get("review") or {}
        if isinstance(rev, dict):
            for t in rev.get("tags") or []:
                if isinstance(t, str) and t:
                    c[t] += 1
    return c


def _keyword_hits(text: str) -> Counter:
    c: Counter = Counter()
    if not text:
        return c
    low = text.lower()
    for tid, pack in THEME_PACKS.items():
        for kw in pack.get("keywords") or []:
            if kw.lower() in low:
                c[tid] += 1
                break
    return c


def mine_weaknesses(
    hands: list[dict] | None = None,
    *,
    limit: int = 200,
    archive: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Rank themes by stored leak tags + llm_review keyword hits."""
    rows = list(hands) if hands is not None else _hands_from_store(limit)
    if archive:
        rows = list(rows) + list(archive)
    tags = _tag_counts(rows)
    review_hits: Counter = Counter()
    for h in rows:
        parts = []
        lr = h.get("llm_review")
        if lr:
            parts.append(str(lr))
        rev = h.get("review") or {}
        if isinstance(rev, dict):
            if rev.get("llm"):
                parts.append(str(rev["llm"]))
            for n in rev.get("notes") or []:
                parts.append(str(n))
            if rev.get("summary"):
                parts.append(str(rev["summary"]))
        review_hits.update(_keyword_hits("\n".join(parts)))

    scored: list[dict[str, Any]] = []
    for tid, pack in THEME_PACKS.items():
        tag_score = sum(tags.get(t, 0) for t in (pack.get("tags") or []))
        kw_score = review_hits.get(tid, 0)
        score = tag_score * 3 + kw_score
        scored.append(
            {
                "id": tid,
                "label": pack["label"],
                "focus": pack["focus"],
                "tags": list(pack.get("tags") or []),
                "tag_hits": tag_score,
                "review_hits": kw_score,
                "score": score,
                "hands_scanned": len(rows),
            }
        )
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    return scored


def _pick_theme_llm(candidates: list[dict[str, Any]]) -> str | None:
    """Optional LLM picker; returns theme id or None. No network hard-fail."""
    try:
        from pokergym.deepseek import available, chat_json
    except Exception:
        return None
    if not available():
        return None
    top = candidates[:5] if candidates else list_themes()[:5]
    payload = [
        {"id": c["id"], "label": c["label"], "score": c.get("score", 0), "focus": c["focus"]}
        for c in top
    ]
    sys = (
        "你是德州扑克教练。根据学员弱项列表选出最该先练的一个主题。"
        '只输出 JSON：{"theme_id":"...","reason":"..."}。'
        "theme_id 必须来自候选列表。reason 一句中文。"
    )
    try:
        data = chat_json(sys, str(payload), timeout=8, max_tokens=120, temperature=0.2)
    except Exception:
        return None
    if not data:
        return None
    tid = str(data.get("theme_id") or "").strip()
    if tid in THEME_PACKS:
        return tid
    return None


def select_drill_focus(
    theme_id: str | None = None,
    *,
    hands: list[dict] | None = None,
    archive: list[dict] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Choose a drill theme.
    Priority: explicit theme_id → mined top score → optional LLM among top → static default.
    """
    if theme_id and theme_id in THEME_PACKS:
        focus = get_theme(theme_id)
        focus["source"] = "requested"
        focus["reason"] = "用户指定主题"
        return focus

    ranked = mine_weaknesses(hands, archive=archive)
    top = ranked[0] if ranked else None
    if top and top["score"] > 0:
        chosen_id = top["id"]
        source = "mined"
        reason = f"复盘标签/评语命中 {top['score']} 次"
        if use_llm:
            llm_id = _pick_theme_llm(ranked)
            if llm_id:
                chosen_id = llm_id
                source = "llm"
                reason = "LLM 根据弱项列表选择"
        focus = get_theme(chosen_id)
        focus["source"] = source
        focus["reason"] = reason
        focus["ranked"] = [
            {"id": r["id"], "label": r["label"], "score": r["score"]} for r in ranked[:5]
        ]
        return focus

    # No archive signal — rotate default static pack (stable by hand count)
    n = (top or {}).get("hands_scanned", 0) if top else 0
    ids = list(THEME_PACKS.keys())
    chosen_id = ids[n % len(ids)] if ids else DEFAULT_THEME_ID
    if use_llm:
        llm_id = _pick_theme_llm([get_theme(i) for i in ids])
        if llm_id:
            focus = get_theme(llm_id)
            focus["source"] = "llm"
            focus["reason"] = "无复盘记录，LLM 从静态主题包中挑选"
            return focus
    focus = get_theme(chosen_id)
    focus["source"] = "static"
    focus["reason"] = "无复盘弱项信号，使用静态主题包"
    return focus


def _button_for_hero_pos(n: int, hero_seat: int, pos: str) -> int:
    """Map desired hero position name to button seat (8-max layout)."""
    rel = {
        "BTN": 0,
        "SB": 1,
        "BB": 2,
        "UTG": 3,
        "UTG1": 4,
        "MP": 5,
        "HJ": 6,
        "CO": 7,
    }
    offset = rel.get(pos, 0)
    if offset >= n:
        offset = 0
    return (hero_seat - offset) % n


def apply_theme_setup(sess, theme: dict[str, Any]) -> None:
    """Bias bots + button so the live table favors the theme spot."""
    pack = THEME_PACKS.get(theme.get("id") or "", {})
    prefer = list(pack.get("bot_prefer") or [])
    boost = dict(pack.get("param_boost") or {})
    hero_pos = pack.get("hero_pos") or "BTN"

    if prefer and getattr(sess, "bots", None):
        from pokergym.personality import spawn_bot

        seats = sorted(s for s in sess.bots if s != sess.hero_seat)
        for i, seat in enumerate(seats[: min(3, len(seats))]):
            arch = prefer[i % len(prefer)]
            old = sess.bots[seat]
            sess.bots[seat] = spawn_bot(sess.rng, seat, arch, name=old.name)
            bot = sess.bots[seat]
            for k, mult in boost.items():
                if k in bot.base_params:
                    bot.base_params[k] = float(bot.base_params[k]) * float(mult)

    try:
        target_btn = _button_for_hero_pos(sess.n, sess.hero_seat, hero_pos)
        # start_hand advances button by 1; pre-set so we land on target
        # start_hand only rotates button when hand_idx>0; first drill hand keeps this button.
        sess.st.button = target_btn % sess.n
    except Exception:
        pass

    sess.drill = {
        "id": theme.get("id"),
        "label": theme.get("label"),
        "focus": theme.get("focus"),
        "source": theme.get("source", "theme"),
        "reason": theme.get("reason", ""),
        "tags": list(theme.get("tags") or []),
        "active": True,
    }


def build_drill_session(
    *,
    theme_id: str | None = None,
    seed: int | None = None,
    mode: str = "train",
    use_llm: bool = True,
    wait_llm: bool = False,
    hands: list[dict] | None = None,
):
    """Create a LiveSession focused on a weakness theme."""
    from pokergym.live import LiveSession

    focus = select_drill_focus(theme_id, hands=hands, use_llm=use_llm)
    if seed is None:
        seed = (hash(focus["id"]) & 0x7FFFFFFF) % 1_000_000 or 7
    sess = LiveSession(seed=int(seed), mode=mode, wait_llm=wait_llm)
    apply_theme_setup(sess, focus)
    sess.new_hand()
    return sess, focus


def weakness_report(
    theme_id: str | None = None,
    *,
    use_llm: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    """CLI/API summary: ranked weaknesses + selected focus."""
    ranked = mine_weaknesses(limit=limit)
    focus = select_drill_focus(theme_id, use_llm=use_llm)
    return {
        "themes": list_themes(),
        "ranked": ranked,
        "focus": focus,
        "has_signal": bool(ranked and ranked[0]["score"] > 0),
    }
