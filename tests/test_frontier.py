import numpy as np

from qcom.frontier import nelder_mead, default_levers, FrontierConfig


def test_nelder_mead_minimizes_quadratic():
    # Minimum of (x-3)^2 + (y+1)^2 is at (3, -1).
    f = lambda v: (v[0] - 3) ** 2 + (v[1] + 1) ** 2
    x, fx = nelder_mead(f, np.array([0.0, 0.0]), np.array([1.0, 1.0]), max_iter=200)
    assert abs(x[0] - 3) < 1e-2
    assert abs(x[1] + 1) < 1e-2
    assert fx < 1e-3


def test_effort_zero_at_baseline():
    fc = FrontierConfig(levers=default_levers())
    assert fc.effort(fc.baseline_vector()) == 0.0


def test_effort_increases_with_upward_moves():
    fc = FrontierConfig(levers=default_levers())
    base = fc.baseline_vector()
    moved = base.copy()
    moved[0] += 200  # raise density well above baseline
    assert fc.effort(moved) > 0.0


def test_clip_respects_bounds():
    fc = FrontierConfig(levers=default_levers())
    x = np.array([99999.0, 0.0, 99.0])
    c = fc.clip(x)
    for i, lv in enumerate(fc.levers):
        assert lv.low <= c[i] <= lv.high
