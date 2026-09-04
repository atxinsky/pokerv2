"""命令行：play / sim / drill。"""

from __future__ import annotations

import argparse

from pokergym.const import CHIP_PER_BB, MODE_REALISM, MODE_TRAIN
from pokergym.drills import (
    list_themes,
    run_fold_to_3bet_drill,
    select_drill_focus,
    weakness_report,
)
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


def cmd_serve(args):
    """常驻模式：只起 HTTP 服务，不弹窗口（给计划任务/后台用）。"""
    from pokergym.server import serve_forever

    serve_forever(host=args.host, port=args.port)


def cmd_drill(args):
    if getattr(args, "list_themes", False):
        for th in list_themes():
            print(f"{th['id']:<22} {th['label']}  — {th['focus']}")
        return
    if getattr(args, "weakness", False) or getattr(args, "theme", None):
        theme = getattr(args, "theme", None)
        use_llm = bool(getattr(args, "use_llm", False))
        report = weakness_report(theme, use_llm=use_llm)
        focus = report["focus"]
        print(f"弱项 drill 主题: {focus['id']}  ({focus['label']})")
        print(f"来源: {focus.get('source')}  — {focus.get('reason', '')}")
        print(f"焦点: {focus['focus']}")
        ranked = report.get("ranked") or []
        hits = [r for r in ranked if r.get("score", 0) > 0][:5]
        if hits:
            print("复盘弱项排行:")
            for r in hits:
                print(f"  {r['score']:>3}  {r['id']:<22} {r['label']}")
        else:
            print("暂无复盘标签信号，已回退静态主题包。")
        if getattr(args, "start_ui", False):
            from pokergym.desktop import run_ui
            from pokergym.server import reset_session

            reset_session(
                getattr(args, "seed", None),
                mode="train",
                theme=focus["id"],
                auto_weakness=True,
                use_llm_pick=False,
            )
            print("已加载弱项牌桌，打开 UI …")
            run_ui(host=args.host, port=args.port, browser=getattr(args, "browser", False))
        return
    out = run_fold_to_3bet_drill(seed=args.seed, hands=args.hands)
    print(
        f"3bet率 前期 {out['early']:.1%}  后期 {out['late']:.1%}  "
        f"提升 {out['lift']:.2f}x  参数倍数 {out['param_mult']:.2f}"
    )
    if out["param_mult"] > 1.05 or out["late"] > out["early"] * 1.08:
        print("B 层响应有效")
    else:
        print("B 层响应偏弱（可能样本或原型偏紧）")


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
    sd = sub.add_parser("drill", help="泄漏/弱项 drill：默认测 bot 对弃 3bet 的适应；加 --weakness 做弱项训练")
    sd.add_argument("--seed", type=int, default=9)
    sd.add_argument("--hands", type=int, default=200)
    sd.add_argument("--weakness", action="store_true", help="按复盘弱项/主题包选 drill 焦点")
    sd.add_argument("--theme", default=None, help="指定主题 id（见 --list-themes）")
    sd.add_argument("--list-themes", action="store_true", help="列出静态主题包")
    sd.add_argument("--use-llm", action="store_true", help="有 Key 时让 LLM 协助选主题")
    sd.add_argument("--start-ui", action="store_true", help="选好主题后直接开 UI 牌桌")
    sd.add_argument("--host", default="127.0.0.1")
    sd.add_argument("--port", type=int, default=8765)
    sd.add_argument("--browser", action="store_true")
    sd.set_defaults(func=cmd_drill)
    su = sub.add_parser("ui", help="桌面夜场牌桌")
    su.add_argument("--host", default="127.0.0.1")
    su.add_argument("--port", type=int, default=8765)
    su.add_argument("--browser", action="store_true", help="只用系统浏览器")
    su.set_defaults(func=cmd_ui)
    sv = sub.add_parser("serve", help="只起 HTTP 服务，不弹窗（常驻用）")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
