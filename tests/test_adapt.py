from pokergym.drills import run_fold_to_3bet_drill, threebet_rate


def test_b_layer_adapts_to_fold_vs_3bet():
    out = run_fold_to_3bet_drill(seed=9, hands=180)
    assert out["late"] > 0.0 or out["early"] > 0.0
    # 训练模式：凶型 bot 的 3bet 参数必须被推高
    assert out["param_mult"] > 1.05, out
