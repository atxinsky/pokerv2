"""牌桌状态。holes 只允许 step/view/showdown 访问。"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from pokergym.const import BB_CHIPS, N_SEATS, POS_6, POS_8, SB_CHIPS, START_STACK
from pokergym.types import PublicAction


@dataclass
class Player:
    seat: int
    stack: int = START_STACK
    bet_street: int = 0
    committed: int = 0
    folded: bool = False
    allin: bool = False
    acted_this_street: bool = False


@dataclass
class TableState:
    n: int = N_SEATS
    button: int = 0
    street: str = "over"
    board: list[int] = field(default_factory=list)
    deck: list[int] = field(default_factory=list)
    players: list[Player] = field(default_factory=list)
    current_bet: int = 0
    min_raise_by: int = BB_CHIPS
    to_act: int = 0
    raise_is_open: bool = True
    last_aggressor: int | None = None
    pfr_seat: int | None = None
    action_log: list[PublicAction] = field(default_factory=list)
    holes: dict[int, tuple[int, int]] = field(default_factory=dict)
    intent: dict[int, str] = field(default_factory=dict)
    hand_idx: int = -1
    revealed: dict[int, tuple[int, int]] = field(default_factory=dict)
    winners: list[tuple[int, int]] = field(default_factory=list)  # seat, chips
    sb_chips: int = SB_CHIPS
    bb_chips: int = BB_CHIPS
    start_stack: int = START_STACK
    rng: Random = field(default_factory=Random)

    @property
    def pot_chips(self) -> int:
        return sum(p.committed for p in self.players)

    def pos_name(self, seat: int) -> str:
        names = POS_8 if self.n == 8 else POS_6
        return names[(seat - self.button) % self.n]


def new_table(n: int, rng: Random, button: int = 0) -> TableState:
    players = [Player(seat=i) for i in range(n)]
    return TableState(n=n, button=button, players=players, rng=rng)
