"""全局常量。筹码内部用整数，1bb = 100。"""

CHIP_PER_BB = 100
SB_CHIPS = 50
BB_CHIPS = 100
START_STACK = 10000  # 100bb
N_SEATS = 8

# 8-max 从按钮起顺时针
POS_8 = ("BTN", "SB", "BB", "UTG", "UTG1", "MP", "HJ", "CO")
POS_6 = ("BTN", "SB", "BB", "UTG", "HJ", "CO")

STREETS = ("pre", "flop", "turn", "river")

# 训练 / 拟真
MODE_TRAIN = "train"
MODE_REALISM = "realism"
