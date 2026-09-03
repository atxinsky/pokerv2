"""命令行：play / sim / drill。"""

from __future__ import annotations

import argparse

from pokergym.const import CHIP_PER_BB, MODE_REALISM, MODE_TRAIN
from pokergym.drills import run_fold_to_3bet_drill
from pokergym.legal import legal_actions, snap_action
from pokergym.personality import desc
from pokergym.stats import collect, gap_std, population_wtsd, population_wwsf
from pokergym.step import apply_action, is_hand_over, start_hand
from pokergym.state import new_table
from pokergym.table import run_session
from pokergym.bot import decide
from pokergym.personality import spawn_table_bots
from pokergym.render import render_hero_prompt, render_table
from pokergym.types import Action
import random


def _parse_user(text: str, st, seat: int) -> Action | None:
    text = text.strip().lower()
    if not text:
        return None
    parts = text.split()
    cmd = parts[0]
    legal = legal_actions(st, seat)
    kinds = {a.kind for a in legal}
    if cmd in ("f", "fold") and "fold" in kinds:
        return Action("fold")
    if cmd in ("x", "check") and "check" in kinds:
        return Action("check")
    if cmd in ("c", "call") and "call" in kinds:
        return next(a for a in legal if a.kind == "call")
    if cmd in ("a", "allin", "all-in"):
        max_to = max((a.to_chips or 0) for a in legal if a.kind in ("bet", "raise", "call"))
        kind = "raise" if "raise" in kinds else ("bet" if "bet" in kinds else "call")
        return snap_action(st, seat, Action(kind, max_to))
    if cmd in ("b", "bet") and "bet" in kinds:
        if len(parts) < 2:
            return next(a for a in legal if a.kind == "bet")
        to = int(float(parts[1]) * CHIP_PER_BB)
        return snap_action(st, seat, Action("bet", to))
    if cmd in ("r", "raise") and "raise" in kinds:
        if len(parts) < 2:
            return next(a for a in legal if a.kind == "raise")
        to = int(float(parts[1]) * CHIP_PER_BB)
        return snap_action(st, seat, Action("raise", to))
    return None


def cmd_play(args):
    rng = random.Random(args.seed)
    st = new_table(args.seats, rng)
    hero_seat = 0
    bots = spawn_table_bots(rng, args.seats, hero_seat)
    print("对手:")
    for b in bots.values():
        print(" ", desc(b))
    hands = 0
    while hands < args.hands:
        start_hand(st)
        print("\n" + "=" * 48)
        while not is_hand_over(st):
            seat = st.to_act
            if seat == hero_seat:
                print(render_hero_prompt(st, hero_seat))
                while True:
                    try:
                        raw = input("> ")
                    except EOFError:
                        return
                    if raw.strip() in ("q", "quit"):
                        return
                    act = _parse_user(raw, st, seat)
                    if act is None:
                        print("无法识别，再试")
                        continue
                    break
            else:
                act = decide(st, bots[seat], rng)
            apply_action(st, act)
        print(render_table(st, hero_seat))
        if st.winners:
            wtxt = ", ".join(f"座位{s}+{c/CHIP_PER_BB:.1f}bb" for s, c in st.winners)
            print("结算:", wtxt)
        hands += 1


def cmd_sim(args):
    res = run_session(seed=args.seed, n_hands=args.hands, n=args.seats, mode=args.mode)
    stats = collect(res.hands, res.n)
    print(f"seed={res.seed} hands={len(res.hands)} mode={res.mode}")
    print(f"{'座位':<4} {'原型':<18} {'VPIP':>6} {'PFR':>6} {'AF':>5} {'WTSD':>6}")
    for s, b in sorted(res.bots.items()):
        st = stats[s]
        print(
            f"{s:<4} {b.archetype:<18} {st.vpip_pct:6.1%} {st.pfr_pct:6.1%} {st.af:5.2f} {st.wtsd:6.1%}"
        )
    print(
        f"群体 WWSF={population_wwsf(stats):.1%}  WTSD={population_wtsd(stats):.1%}  "
        f"VPIP-PFRσ={gap_std(stats):.3f}"
    )


def cmd_ui(args):
    from pokergym.desktop import run_ui

    run_ui(host=args.host, port=args.port, browser=args.browser)


def cmd_drill(args):
    out = run_fold_to_3bet_drill(seed=args.seed, hands=args.hands)
    print(
        f"3bet率 前期 {out['early']:.1%}  后期 {out['late']:.1%}  "
        f"提升 {out['lift']:.2f}x  参数倍率 {out['param_mult']:.2f}"
    )
    if out["param_mult"] > 1.05 or out["late"] > out["early"] * 1.08:
        print("B 层适应生效")
    else:
        print("B 层适应偏弱（样本不足或被原型夹逼）")


def main(argv=None):
    p = argparse.ArgumentParser(prog="pokergym")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("play", help="真人 vs 7 bot")
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--hands", type=int, default=50)
    sp.add_argument("--seats", type=int, default=8)
    sp.set_defaults(func=cmd_play)
    ss = sub.add_parser("sim", help="全 bot 模拟")
    ss.add_argument("--seed", type=int, default=3)
    ss.add_argument("--hands", type=int, default=400)
    ss.add_argument("--seats", type=int, default=8)
    ss.add_argument("--mode", choices=[MODE_TRAIN, MODE_REALISM], default=MODE_TRAIN)
    ss.set_defaults(func=cmd_sim)
    sd = sub.add_parser("drill", help="英雄永远弃 3bet，看 bot 是否加大 3bet")
    sd.add_argument("--seed", type=int, default=9)
    sd.add_argument("--hands", type=int, default=200)
    sd.set_defaults(func=cmd_drill)
    su = sub.add_parser("ui", help="桌面夜场牌桌")
    su.add_argument("--host", default="127.0.0.1")
    su.add_argument("--port", type=int, default=8765)
    su.add_argument("--browser", action="store_true", help="只用系统浏览器")
    su.set_defaults(func=cmd_ui)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
