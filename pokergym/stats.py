"""HUD 统计。"""

from __future__ import annotations

from dataclasses import dataclass, field

from pokergym.digest import HandHist


@dataclass
class SeatStats:
    hands: int = 0
    vpip: int = 0
    pfr: int = 0
    saw_flop: int = 0
    to_sd: int = 0
    won_flop: int = 0
    agg_bet: int = 0
    agg_call: int = 0
    threebet: int = 0
    vs_open: int = 0

    @property
    def vpip_pct(self) -> float:
        return self.vpip / max(self.hands, 1)

    @property
    def pfr_pct(self) -> float:
        return self.pfr / max(self.hands, 1)

    @property
    def af(self) -> float:
        return self.agg_bet / max(self.agg_call, 1)

    @property
    def wwsf(self) -> float:
        return self.won_flop / max(self.saw_flop, 1)

    @property
    def wtsd(self) -> float:
        return self.to_sd / max(self.saw_flop, 1)

    @property
    def vpip_pfr_gap(self) -> float:
        return self.vpip_pct - self.pfr_pct


def collect(hands: list[HandHist], n: int) -> dict[int, SeatStats]:
    out = {s: SeatStats() for s in range(n)}
    for h in hands:
        for s in range(n):
            st = out[s]
            st.hands += 1
            if h.vpip.get(s):
                st.vpip += 1
            if h.pfr.get(s):
                st.pfr += 1
            if h.saw_flop.get(s):
                st.saw_flop += 1
                if h.won_chips.get(s, 0) > 0:
                    st.won_flop += 1
            if h.to_sd.get(s):
                st.to_sd += 1
        for node in h.nodes:
            st = out[node.seat]
            if node.action in ("bet", "raise"):
                st.agg_bet += 1
            if node.action == "call":
                st.agg_call += 1
            if node.street == "pre" and node.faced == "open":
                st.vs_open += 1
                if node.action == "raise":
                    st.threebet += 1
    return out


def population_wwsf(stats: dict[int, SeatStats]) -> float:
    sf = sum(s.saw_flop for s in stats.values())
    won = sum(s.won_flop for s in stats.values())
    return won / max(sf, 1)


def population_wtsd(stats: dict[int, SeatStats]) -> float:
    sf = sum(s.saw_flop for s in stats.values())
    sd = sum(s.to_sd for s in stats.values())
    return sd / max(sf, 1)


def gap_std(stats: dict[int, SeatStats]) -> float:
    gaps = [s.vpip_pfr_gap for s in stats.values() if s.hands >= 20]
    if len(gaps) < 2:
        return 0.0
    mean = sum(gaps) / len(gaps)
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    return var ** 0.5
