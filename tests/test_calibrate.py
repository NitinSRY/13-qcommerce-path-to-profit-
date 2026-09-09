from qcom.costs import CostModel
from qcom.calibrate import calibrate_to_metro, load_anchors, DEFAULT_ANCHORS_PATH


def test_load_anchors_skips_na_rows():
    anchors = load_anchors(DEFAULT_ANCHORS_PATH)
    names = {a.player for a in anchors}
    assert "Blinkit" in names
    # The industry "NA" loss-per-order row must be skipped.
    assert all(a.loss_per_order == a.loss_per_order for a in anchors)  # no NaN


def test_calibration_reproduces_published_loss():
    cal, diag = calibrate_to_metro(CostModel(), target_loss_per_order=-3.02, aov=709,
                                   replications=6)
    # The whole point: the dense regime reproduces the published loss-per-order.
    assert abs(diag["reproduced_contribution"] - (-3.02)) < 1e-2
    # Calibrated fixed cost is a realistic dark-store daily cost, not absurd.
    assert 5000 < diag["fixed_cost_per_day"] < 60000


def test_metro_meets_sla():
    _, diag = calibrate_to_metro(CostModel(), -3.02, 709, replications=6)
    # A well-provisioned metro store should rarely breach the SLA.
    assert diag["sla_breach_rate"] < 0.10
