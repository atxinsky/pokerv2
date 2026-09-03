"""五种原型。夹逼盒子防止适应后全体漂成 TAG。"""

from __future__ import annotations

ARCHETYPES = (
    "loose_passive",
    "tight_passive",
    "tight_aggressive",
    "loose_aggressive",
    "maniac",
)

ARCHETYPE_ZH = {
    "loose_passive": "松被动（鱼）",
    "tight_passive": "紧被动（岩石）",
    "tight_aggressive": "紧凶（TAG）",
    "loose_aggressive": "松凶（LAG）",
    "maniac": "疯子",
}

# 线下低级别桌：鱼多
ARCHETYPE_MIX = {
    "loose_passive": 0.32,
    "tight_passive": 0.14,
    "tight_aggressive": 0.20,
    "loose_aggressive": 0.20,
    "maniac": 0.14,
}

PARAM_KEYS = (
    "vpip",
    "pfr",
    "limp_rate",
    "threebet_freq",
    "squeeze_freq",
    "fold_to_3bet",
    "cbet_freq",
    "fold_to_cbet",
    "call_station_idx",
    "river_bluff_freq",
    "bluff_mult",
    "value_mult",
    "fold_bias",
    "sizing_bias",
    "iso_freq",
    "donk_freq",
    "fourbet_freq",
)

# 原型盒子
ARCHETYPE_RANGE: dict[str, dict[str, tuple[float, float]]] = {
    "loose_passive": {
        "vpip": (0.45, 0.70),
        "pfr": (0.03, 0.10),
        "limp_rate": (0.55, 0.90),
        "threebet_freq": (0.005, 0.03),
        "squeeze_freq": (0.0, 0.03),
        "fold_to_3bet": (0.25, 0.50),
        "cbet_freq": (0.20, 0.45),
        "fold_to_cbet": (0.15, 0.40),
        "call_station_idx": (0.70, 0.95),
        "river_bluff_freq": (0.01, 0.08),
        "bluff_mult": (0.15, 0.50),
        "value_mult": (0.85, 1.15),
        "fold_bias": (-0.18, -0.05),
        "sizing_bias": (0.70, 0.95),
        "iso_freq": (0.02, 0.12),
        "donk_freq": (0.08, 0.22),
        "fourbet_freq": (0.0, 0.02),
    },
    "tight_passive": {
        "vpip": (0.08, 0.18),
        "pfr": (0.05, 0.12),
        "limp_rate": (0.05, 0.25),
        "threebet_freq": (0.02, 0.06),
        "squeeze_freq": (0.0, 0.04),
        "fold_to_3bet": (0.55, 0.80),
        "cbet_freq": (0.40, 0.65),
        "fold_to_cbet": (0.50, 0.75),
        "call_station_idx": (0.08, 0.25),
        "river_bluff_freq": (0.02, 0.10),
        "bluff_mult": (0.20, 0.60),
        "value_mult": (0.90, 1.10),
        "fold_bias": (0.02, 0.10),
        "sizing_bias": (0.90, 1.10),
        "iso_freq": (0.15, 0.35),
        "donk_freq": (0.01, 0.06),
        "fourbet_freq": (0.01, 0.04),
    },
    "tight_aggressive": {
        "vpip": (0.15, 0.26),
        "pfr": (0.13, 0.22),
        "limp_rate": (0.00, 0.08),
        "threebet_freq": (0.06, 0.12),
        "squeeze_freq": (0.06, 0.14),
        "fold_to_3bet": (0.55, 0.75),
        "cbet_freq": (0.60, 0.80),
        "fold_to_cbet": (0.45, 0.65),
        "call_station_idx": (0.12, 0.30),
        "river_bluff_freq": (0.08, 0.20),
        "bluff_mult": (0.75, 1.30),
        "value_mult": (0.95, 1.15),
        "fold_bias": (-0.01, 0.05),
        "sizing_bias": (0.95, 1.15),
        "iso_freq": (0.55, 0.85),
        "donk_freq": (0.01, 0.05),
        "fourbet_freq": (0.04, 0.10),
    },
    "loose_aggressive": {
        "vpip": (0.26, 0.40),
        "pfr": (0.20, 0.32),
        "limp_rate": (0.02, 0.12),
        "threebet_freq": (0.10, 0.18),
        "squeeze_freq": (0.10, 0.20),
        "fold_to_3bet": (0.40, 0.62),
        "cbet_freq": (0.65, 0.88),
        "fold_to_cbet": (0.30, 0.50),
        "call_station_idx": (0.20, 0.42),
        "river_bluff_freq": (0.15, 0.32),
        "bluff_mult": (1.20, 2.00),
        "value_mult": (0.95, 1.20),
        "fold_bias": (-0.10, 0.00),
        "sizing_bias": (1.00, 1.30),
        "iso_freq": (0.60, 0.90),
        "donk_freq": (0.04, 0.12),
        "fourbet_freq": (0.06, 0.14),
    },
    "maniac": {
        "vpip": (0.55, 0.80),
        "pfr": (0.35, 0.55),
        "limp_rate": (0.10, 0.40),
        "threebet_freq": (0.16, 0.30),
        "squeeze_freq": (0.14, 0.28),
        "fold_to_3bet": (0.15, 0.40),
        "cbet_freq": (0.70, 0.95),
        "fold_to_cbet": (0.10, 0.35),
        "call_station_idx": (0.40, 0.70),
        "river_bluff_freq": (0.22, 0.45),
        "bluff_mult": (1.80, 2.80),
        "value_mult": (0.90, 1.25),
        "fold_bias": (-0.15, -0.02),
        "sizing_bias": (1.05, 1.50),
        "iso_freq": (0.50, 0.90),
        "donk_freq": (0.10, 0.28),
        "fourbet_freq": (0.10, 0.22),
    },
}

ARCHETYPE_BASE: dict[str, dict[str, float]] = {
    a: {k: (lo + hi) / 2 for k, (lo, hi) in box.items()}
    for a, box in ARCHETYPE_RANGE.items()
}

# 翻前位置宽度（占 169 的百分位上限，越小越紧）
# 值是「进入该动作的最弱百分位」
OPEN_PCT = {
    "loose_passive": {"UTG": 0.08, "UTG1": 0.09, "MP": 0.10, "HJ": 0.12, "CO": 0.16, "BTN": 0.22, "SB": 0.14, "BB": 0.00},
    "tight_passive": {"UTG": 0.07, "UTG1": 0.08, "MP": 0.09, "HJ": 0.11, "CO": 0.14, "BTN": 0.18, "SB": 0.12, "BB": 0.00},
    "tight_aggressive": {"UTG": 0.10, "UTG1": 0.12, "MP": 0.14, "HJ": 0.18, "CO": 0.26, "BTN": 0.40, "SB": 0.30, "BB": 0.00},
    "loose_aggressive": {"UTG": 0.16, "UTG1": 0.18, "MP": 0.22, "HJ": 0.28, "CO": 0.38, "BTN": 0.52, "SB": 0.40, "BB": 0.00},
    "maniac": {"UTG": 0.38, "UTG1": 0.42, "MP": 0.48, "HJ": 0.55, "CO": 0.65, "BTN": 0.78, "SB": 0.62, "BB": 0.00},
}

LIMP_PCT = {
    "loose_passive": {"UTG": 0.50, "UTG1": 0.52, "MP": 0.55, "HJ": 0.58, "CO": 0.60, "BTN": 0.55, "SB": 0.62, "BB": 0.00},
    "tight_passive": {"UTG": 0.10, "UTG1": 0.10, "MP": 0.12, "HJ": 0.12, "CO": 0.10, "BTN": 0.08, "SB": 0.18, "BB": 0.00},
    "tight_aggressive": {"UTG": 0.02, "UTG1": 0.02, "MP": 0.02, "HJ": 0.02, "CO": 0.02, "BTN": 0.01, "SB": 0.08, "BB": 0.00},
    "loose_aggressive": {"UTG": 0.06, "UTG1": 0.06, "MP": 0.06, "HJ": 0.05, "CO": 0.04, "BTN": 0.02, "SB": 0.10, "BB": 0.00},
    "maniac": {"UTG": 0.52, "UTG1": 0.55, "MP": 0.58, "HJ": 0.60, "CO": 0.58, "BTN": 0.50, "SB": 0.62, "BB": 0.00},
}


def clamp_params(archetype: str, params: dict) -> dict:
    box = ARCHETYPE_RANGE[archetype]
    out = {}
    for k, v in params.items():
        if k in box:
            lo, hi = box[k]
            out[k] = min(max(v, lo), hi)
        else:
            out[k] = v
    return out
