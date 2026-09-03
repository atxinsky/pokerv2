"""文本牌桌。"""

from __future__ import annotations

from pokergym.cards import card_pretty
from pokergym.coach import snapshot
from pokergym.const import CHIP_PER_BB
from pokergym.state import TableState
from pokergym.types import BotView
from pokergym.view import build_bot_view


def _bb(ch: int) -> str:
    v = ch / CHIP_PER_BB
    return f"{v:.1f}".rstrip("0").rstrip(".")


def render_table(st: TableState, hero_seat: int | None) -> str:
    lines = [f"#{st.hand_idx} {st.street.upper()}  底池 {_bb(st.pot_chips)}bb  按钮{st.button}"]
    if st.board:
        lines.append("公共牌 " + " ".join(card_pretty(c) for c in st.board))
    for p in st.players:
        mark = ">" if p.seat == st.to_act and st.street != "over" else " "
        pos = st.pos_name(p.seat)
        flags = []
        if p.folded:
            flags.append("弃")
        if p.allin:
            flags.append("全下")
        if p.seat == hero_seat:
            flags.append("你")
        hole = ""
        if hero_seat is not None and p.seat == hero_seat and p.seat in st.holes:
            hole = " " + " ".join(card_pretty(c) for c in st.holes[p.seat])
        if p.seat in st.revealed:
            hole = " " + " ".join(card_pretty(c) for c in st.revealed[p.seat])
        lines.append(
            f"{mark} {p.seat}:{pos:4} 栈{_bb(p.stack):>6} 本街{_bb(p.bet_street):>5}  "
            f"{' '.join(flags)}{hole}"
        )
    return "\n".join(lines)


def render_hero_prompt(st: TableState, hero_seat: int) -> str:
    view = build_bot_view(hero_seat, st)
    math = snapshot(view)
    lines = [
        render_table(st, hero_seat),
        f"合法: {', '.join(view.legal_kinds)}  需跟 {view.to_call_bb:.1f}bb  SPR {view.spr:.1f}",
        f"数学: 赔率{math['pot_odds']:.0%}  MDF{math['mdf']:.0%}  牌力{math['hand_class']}  结构{math['texture']}",
        "输入 f弃 x过 c跟 b下注 r加注 a全下  尺度如 b 12 或 r 9",
    ]
    return "\n".join(lines)
