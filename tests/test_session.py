from pokergym.archetypes import ARCHETYPE_RANGE
from pokergym.rngutil import sample_action
from pokergym.stats import collect, gap_std, population_wtsd, population_wwsf
from pokergym.table import run_session


def test_freq_sums_and_sample():
    f = {"fold": 0.2, "call": 0.3, "raise": 0.5}
    assert abs(sum(f.values()) - 1) < 1e-9
    from random import Random

    rng = Random(0)
    got = {sample_action(f, rng) for _ in range(200)}
    assert got <= set(f)


def test_replay_determinism():
    a = run_session(seed=42, n_hands=40)
    b = run_session(seed=42, n_hands=40)
    assert a.action_trace == b.action_trace


def test_no_illegal_kind_in_trace():
    s = run_session(seed=1, n_hands=80)
    kinds = {k for _, _, k, _ in s.action_trace}
    assert kinds <= {"fold", "check", "call", "bet", "raise"}


def test_archetype_boxes_not_collapsed():
    s = run_session(seed=7, n_hands=250)
    stats = collect(s.hands, s.n)
    gaps = []
    for seat, bot in s.bots.items():
        st = stats[seat]
        lo, hi = ARCHETYPE_RANGE[bot.archetype]["vpip"]
        # 250 手方差大，给盒子外 ±12% 容忍
        assert lo - 0.18 <= st.vpip_pct <= hi + 0.18, (
            bot.archetype, st.vpip_pct, lo, hi
        )
        gaps.append(st.vpip_pfr_gap)
    assert gap_std(stats) > 0.02


def test_population_stats_reasonable():
    s = run_session(seed=3, n_hands=300)
    stats = collect(s.hands, s.n)
    wwsf = population_wwsf(stats)
    wtsd = population_wtsd(stats)
    assert 0.20 <= wwsf <= 0.80
    assert 0.10 <= wtsd <= 0.70
    for st in stats.values():
        assert 0.05 <= st.vpip_pct <= 0.90
        assert 0.0 <= st.pfr_pct <= 0.70
