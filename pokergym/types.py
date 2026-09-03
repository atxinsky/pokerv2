"""动作与公开日志。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    kind: str  # fold / check / call / bet / raise
    to_chips: int | None = None  # 本街总下注目标


@dataclass(frozen=True)
class PublicAction:
    seat: int
    street: str
    kind: str
    to_chips: int
    put_chips: int
    pot_chips: int


@dataclass(frozen=True)
class BotView:
    """bot 可见的全部信息。不得含他人未摊牌底牌。"""

    seat: int
    hole: tuple[int, int]
    board: tuple[int, ...]
    street: str
    position: str
    pot_bb: float
    to_call_bb: float
    current_bet_bb: float
    min_raise_to_bb: float
    my_stack_bb: float
    bet_street_bb: float
    effective_stack_bb: float
    spr: float
    n_active: int
    n_opponents: int
    is_ip: bool
    can_raise: bool
    raise_is_open: bool
    action_log: tuple[PublicAction, ...]
    showdown_history: tuple[tuple[int, tuple[int, int]], ...]
    my_intent: str | None
    last_aggressor: int | None
    pfr_seat: int | None
    legal_kinds: tuple[str, ...]
