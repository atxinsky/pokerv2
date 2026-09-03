"""英雄行为摘要。给 B 层用，窗口可配。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from pokergym.preflop import classify_preflop
from pokergym.types import PublicAction


@dataclass
class Node:
    seat: int
    street: str
    faced: str
    action: str
    is_pfr: bool
    pot_bb: float


@dataclass
class HandHist:
    hand_idx: int
    nodes: list[Node] = field(default_factory=list)
    vpip: dict[int, bool] = field(default_factory=dict)
    pfr: dict[int, bool] = field(default_factory=dict)
    saw_flop: dict[int, bool] = field(default_factory=dict)
    to_sd: dict[int, bool] = field(default_factory=dict)
    won_chips: dict[int, int] = field(default_factory=dict)
    folded_pre: dict[int, bool] = field(default_factory=dict)


def snapshot_hand(st) -> HandHist:
    """一手结束后从桌面状态抽出历史。"""
    n = st.n
    reached_flop = len(st.board) >= 3
    folded_pre = {a.seat for a in st.action_log if a.street == "pre" and a.kind == "fold"}
    flop_seen = {s: reached_flop and s not in folded_pre for s in range(n)}
    return build_hand_hist(
        st.hand_idx, n, st.action_log, st.winners, st.revealed, st.pfr_seat, flop_seen
    )


def build_hand_hist(hand_idx: int, n: int, log: list[PublicAction], winners, revealed, pfr_seat, flop_seen) -> HandHist:
    h = HandHist(hand_idx=hand_idx)
    for s in range(n):
        h.vpip[s] = False
        h.pfr[s] = False
        h.saw_flop[s] = flop_seen.get(s, False)
        h.to_sd[s] = s in revealed
        h.folded_pre[s] = True
    for i, a in enumerate(log):
        faced = "none"
        if a.street == "pre":
            seq = classify_preflop(tuple(x for x in log[:i] if x.street == "pre"))
            faced = seq.facing
        elif a.kind in ("call", "fold", "raise"):
            faced = "bet"
        node_act = a.kind
        if a.street == "pre" and a.kind == "call" and faced in ("unopened", "limp"):
            node_act = "limp" if faced != "open" else "call"
        h.nodes.append(
            Node(
                seat=a.seat,
                street=a.street,
                faced=faced,
                action=node_act,
                is_pfr=(pfr_seat == a.seat),
                pot_bb=a.pot_chips / 100,
            )
        )
        if a.street == "pre" and a.kind in ("call", "bet", "raise"):
            h.vpip[a.seat] = True
            h.folded_pre[a.seat] = False
        if a.street == "pre" and a.kind == "raise":
            h.pfr[a.seat] = True
        if a.street != "pre":
            h.folded_pre[a.seat] = False
    for seat, chips in winners:
        h.won_chips[seat] = h.won_chips.get(seat, 0) + chips
    return h


def hero_digest(hands: list[HandHist], hero_seat: int, window: int = 30) -> dict:
    recent = hands[-window:]
    c: Counter = Counter()
    for h in recent:
        c["hands"] += 1
        c["vpip.total"] += 1
        if h.vpip.get(hero_seat):
            c["vpip.yes"] += 1
        c["pfr.total"] += 1
        if h.pfr.get(hero_seat):
            c["pfr.yes"] += 1
        for n in h.nodes:
            if n.seat != hero_seat:
                continue
            name = None
            if n.street == "pre" and n.faced == "threebet":
                name = "vs_3bet"
            elif n.street == "pre" and n.faced == "open":
                name = "vs_open"
            elif n.street == "flop" and n.faced == "bet":
                name = "vs_cbet"
            elif n.street == "river" and n.faced == "bet":
                name = "river_faced_bet"
            elif n.street == "river" and n.action in ("bet", "raise"):
                name = "river_agg"
            if name:
                act = n.action if n.action != "limp" else "call"
                c[f"{name}.{act}"] += 1
                c[f"{name}.total"] += 1
    vpip = c["vpip.yes"] / max(c["vpip.total"], 1)
    pfr = c["pfr.yes"] / max(c["pfr.total"], 1)
    return {"hands_observed": c["hands"], "counters": dict(c), "vpip": vpip, "pfr": pfr}


def rate(digest: dict, node: str, action: str) -> float:
    tot = digest["counters"].get(f"{node}.total", 0)
    if tot < 1:
        return 0.0
    return digest["counters"].get(f"{node}.{action}", 0) / tot


def n_obs(digest: dict, node: str) -> int:
    return int(digest["counters"].get(f"{node}.total", 0))
