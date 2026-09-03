"""8-max 100bb 现金 GTO 参考范围（开池 / 3bet / 大盲防守）。

这是训练用的静态表，不是求解器输出。标注为参考。
"""

from __future__ import annotations

from pokergym.cards import RANKS
from pokergym.ranges import hole_code

# 从强到弱，用于 plus 记号
R = "AKQJT98765432"
RI = {c: i for i, c in enumerate(R)}


def _pair_plus(start: str) -> set[str]:
    i = RI[start[0]]
    return {R[k] * 2 for k in range(0, i + 1)}


def _suited_plus(code: str) -> set[str]:
    a, b = code[0], code[1]
    return {f"{a}{R[k]}s" for k in range(RI[a] + 1, RI[b] + 1)}  # 不含对子


def _off_plus(code: str) -> set[str]:
    a, b = code[0], code[1]
    return {f"{a}{R[k]}o" for k in range(RI[a] + 1, RI[b] + 1)}


def _parse(spec: str) -> set[str]:
    out: set[str] = set()
    for tok in spec.split():
        if tok.endswith("+") and len(tok) == 3 and tok[0] == tok[1]:
            out |= _pair_plus(tok[:2])
        elif tok.endswith("+") and tok.endswith("s+"):
            out |= _suited_plus(tok[:-1])
        elif tok.endswith("+") and tok.endswith("o+"):
            out |= _off_plus(tok[:-1])
        else:
            out.add(tok)
    return out


# 开池（无人入池时加注）。BB 没有开池。
OPEN = {
    "UTG": _parse("77+ ATs+ A5s A4s AKo AQo KQs KJs QJs JTs T9s 98s"),
    "UTG1": _parse("66+ ATs+ A5s A4s A3s AKo AQo AJo KQs KJs KTs QJs QTs JTs T9s 98s 87s"),
    "MP": _parse("55+ A9s+ A5s A4s A3s A2s ATo+ KQo KTs+ QTs+ JTs T9s 98s 87s 76s"),
    "HJ": _parse("22+ A2s+ ATo+ KJo+ K9s+ QJo Q9s+ J9s+ T8s+ 97s+ 87s 76s 65s"),
    "CO": _parse("22+ A2s+ A9o+ KTo+ K7s+ QTo+ Q8s+ JTo J8s+ T8s+ 97s+ 86s+ 76s 65s 54s"),
    "BTN": _parse(
        "22+ A2s+ A4o+ K5s+ K9o+ Q6s+ Q9o+ J6s+ J8o+ T6s+ T8o 96s+ 86s+ 75s+ 65s 64s 54s 53s 43s"
    ),
    "SB": _parse("22+ A2s+ A8o+ K9o+ K7s+ Q9o+ Q8s+ J8s+ J9o T8s+ T9o 97s+ 87s 76s 65s 54s"),
    "BB": set(),
}

# 面对开池的 3bet（偏 IP / 后位）。前位更紧。
THREEBET = {
    "UTG": _parse("QQ+ AKs AKo"),
    "UTG1": _parse("QQ+ AKs AKo A5s"),
    "MP": _parse("JJ+ AKs AKo AQs A5s A4s"),
    "HJ": _parse("JJ+ AKs AKo AQs AJs A5s A4s KQs 76s"),
    "CO": _parse("TT+ AKs AKo AQs AJs A5s A4s A3s KQs KJs 87s 76s"),
    "BTN": _parse("TT+ AQs+ AKo A5s A4s A3s A2s KQs KJs QJs 76s 87s 65s"),
    "SB": _parse("JJ+ AQs+ AKo A5s A4s KQs"),
    "BB": _parse("TT+ AQs+ AKo A5s A4s A3s KQs QJs 76s"),
}

# 面对开池的跟注（不含 3bet 里的牌）。BB 最宽。
CALL = {
    "UTG": _parse("JJ TT 99 88 AQs AJs KQs"),
    "UTG1": _parse("JJ TT 99 88 77 AQs AJs ATs KQs KJs QJs"),
    "MP": _parse("TT 99 88 77 66 AJs ATs KQs KJs QJs JTs"),
    "HJ": _parse("TT 99 88 77 66 55 ATs A9s KJs KTs QJs QTs JTs 98s"),
    "CO": _parse("99 88 77 66 55 44 ATs A9s A8s KJs KTs QJs QTs JTs T9s 98s 87s"),
    "BTN": _parse(
        "99 88 77 66 55 44 33 22 AJs ATs A9s A8s A7s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s"
    ),
    "SB": _parse("TT 99 88 77 AJs ATs KQs KJs QJs"),
    "BB": _parse(
        "22+ A2s+ A7o+ K2s+ KTo+ Q6s+ QTo+ J7s+ J9o+ T7s+ T9o 96s+ 86s+ 75s+ 65s 64s 54s 53s 43s"
    ),
}

# 面对 limp 的 iso：开池范围 + 宽一点的宽牌
ISO = {pos: OPEN[pos] | _parse("A9o KJo QJo 22 33 44") for pos in OPEN}


def _pos(pos: str) -> str:
    return pos if pos in OPEN else "MP"


def in_open(pos: str, code: str) -> bool:
    return code in OPEN[_pos(pos)]


def in_3bet(pos: str, code: str) -> bool:
    return code in THREEBET[_pos(pos)]


def in_call(pos: str, code: str) -> bool:
    return code in CALL[_pos(pos)]


def in_iso(pos: str, code: str) -> bool:
    return code in ISO[_pos(pos)]


def preflop_line(pos: str, facing: str, code: str) -> str:
    """返回 fold / open / limp_iso / call / threebet。"""
    p = _pos(pos)
    if facing == "unopened":
        if p == "BB":
            return "check"
        return "open" if code in OPEN[p] else "fold"
    if facing == "limp":
        return "iso" if code in ISO[p] else ("call" if code in CALL[p] else "fold")
    if facing in ("open", "open_calls"):
        if code in THREEBET[p]:
            return "threebet"
        if code in CALL[p]:
            return "call"
        return "fold"
    if facing == "threebet":
        if code in _parse("QQ+ AKs AKo"):
            return "fourbet" if code in _parse("KK+ AKs") else "call"
        if code in _parse("JJ TT AQs AJs KQs"):
            return "call"
        return "fold"
    if facing == "fourbet":
        return "call" if code in _parse("KK+ AKs") else "fold"
    return "fold"


def grid(spot: str, pos: str, hero_code: str | None = None) -> list[list[dict]]:
    """13x13：行=高张 A..2，列=A..2。上三角 suited，对角对子，下三角 offsuit。"""
    marked = set()
    if spot == "open":
        marked = OPEN[_pos(pos)]
    elif spot == "3bet":
        marked = THREEBET[_pos(pos)]
    elif spot == "call":
        marked = CALL[_pos(pos)] | THREEBET[_pos(pos)]
    elif spot == "defend":
        marked = CALL[_pos(pos)] | THREEBET[_pos(pos)]
    cells = []
    for i, a in enumerate(R):
        row = []
        for j, b in enumerate(R):
            if i == j:
                code, kind = a + b, "pair"
            elif j > i:
                code, kind = f"{a}{b}s", "suited"
            else:
                code, kind = f"{b}{a}o", "offsuit"
            row.append(
                {
                    "code": code,
                    "kind": kind,
                    "on": code in marked,
                    "hero": code == hero_code,
                }
            )
        cells.append(row)
    return cells


def spot_label(facing: str, pos: str) -> tuple[str, str]:
    """返回 (图表类型, 中文标题)。"""
    if facing == "unopened":
        return "open", f"{pos} 开池范围"
    if facing == "limp":
        return "open", f"{pos} 开池 / 隔离 limp"
    if facing in ("open", "open_calls"):
        if pos == "BB":
            return "defend", "大盲防守（跟注+3bet）"
        return "3bet", f"{pos} 面对开池（3bet 高亮）"
    if facing == "threebet":
        return "3bet", f"{pos} 面对 3bet 的继续范围"
    return "open", f"{pos} 开池范围"
