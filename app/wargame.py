"""Streamlit war-game: parameterise a dark-store and read its unit economics.

Set the city tier, order density, AOV, batching and ad take, and the app runs the
discrete-event twin live and reports the delivery SLA, the cost breakdown, the
contribution margin, and where the configuration sits relative to breakeven. The
calibration to the published metro loss-per-order is precomputed for instant load.

Run:  streamlit run app/wargame.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qcom.costs import CostModel
from qcom.calibrate import calibrate_to_metro
from qcom.scenarios import tier2_config, run_twin

ROOT = Path(__file__).resolve().parent.parent
CAL_PATH = ROOT / "app" / "calibration.json"


@st.cache_data(show_spinner=False)
def get_cost_model() -> tuple[CostModel, dict]:
    """Load a precomputed calibration if present, else calibrate on the fly."""
    if CAL_PATH.exists():
        d = json.loads(CAL_PATH.read_text())
        cm = CostModel(
            product_take=d["product_take"],
            packaging_per_order=d["packaging_per_order"],
            rider_cost_per_trip=d["rider_cost_per_trip"],
            picker_wage_per_day=d["picker_wage_per_day"],
            fixed_cost_per_day=d["fixed_cost_per_day"],
        )
        return cm, d.get("diag", {})
    cm, diag = calibrate_to_metro(CostModel(), -3.02, 709, replications=12)
    return cm, diag


@st.cache_data(show_spinner=False)
def run_config(opd: float, batch: int, aov: float, ad: float, reps: int, _cm_key: float):
    cm, _ = get_cost_model()
    t = run_twin(tier2_config(orders_per_day=opd, batch_target=batch), cm,
                 aov=aov, ad_take=ad, replications=reps, seed=2)
    return t.as_dict()


def main() -> None:
    st.set_page_config(page_title="Q-commerce Path-to-Profit", layout="wide")
    st.title("Quick-Commerce Path-to-Profit War-Game")
    st.caption(
        "A spatial dark-store digital twin. Calibrated to FY26 financials so the "
        "metro regime reproduces the published loss-per-order, then used to find "
        "the cheapest path to profit in tier-2 markets."
    )

    cm, diag = get_cost_model()

    with st.sidebar:
        st.header("Configuration")
        opd = st.slider("Order density (orders/day)", 200, 1000, 340, step=20)
        batch = st.select_slider("Rider batching factor", options=[1, 2, 3], value=1)
        aov = st.slider("AOV (Rs)", 480, 760, 560, step=10)
        ad = st.slider("Ad take (% of AOV)", 0.0, 6.0, 0.0, step=0.5) / 100.0
        reps = st.select_slider("Simulation replications", options=[5, 10, 20], value=10)
        st.markdown("---")
        st.caption(
            f"Calibrated fixed cost: Rs {cm.fixed_cost_per_day:,.0f}/day. "
            f"Net merchandise take: {cm.product_take:.0%}."
        )

    res = run_config(opd, batch, aov, ad, reps, cm.fixed_cost_per_day)

    contribution = res["econ_contribution"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contribution margin", f"Rs {contribution:,.1f}/order",
              delta="positive" if contribution >= 0 else "loss")
    c2.metric("SLA breach (>15 min)", f"{res['sim_sla_breach_rate']:.1%}")
    c3.metric("Rider utilisation", f"{res['sim_rider_utilization']:.0%}")
    c4.metric("Mean delivery", f"{res['sim_mean_delivery_min']:.1f} min")

    st.subheader("Per-order P&L (Rs)")
    pnl = {
        "Merchandise margin": res["econ_revenue_product"],
        "Ad revenue": res["econ_revenue_ads"],
        "Packaging": -res["econ_packaging"],
        "Rider": -res["econ_rider"],
        "Picking": -res["econ_picking"],
        "Fixed (rent/overhead)": -res["econ_fixed"],
    }
    st.bar_chart(pnl)

    st.subheader("Why this result")
    rider_share = res["econ_rider"] / max(1e-9, res["econ_cost"])
    fixed_share = res["econ_fixed"] / max(1e-9, res["econ_cost"])
    msg = []
    if contribution < 0:
        if fixed_share > 0.35:
            msg.append(
                f"Fixed cost is {fixed_share:.0%} of total cost: at {opd} orders/day "
                "the rent and roster are spread over too few orders. Density is the "
                "binding constraint, not basket size."
            )
        if res["sim_rider_utilization"] < 0.5:
            msg.append(
                f"Riders sit {1 - res['sim_rider_utilization']:.0%} idle: batching or "
                "more density would amortise them."
            )
    else:
        msg.append("This configuration is contribution-positive: entry is rational here.")
    st.write(" ".join(msg) if msg else "Adjust the levers to explore the frontier.")

    if diag:
        st.subheader("Calibration proof")
        st.write(
            f"The metro regime ({diag.get('orders_per_day', 1500):.0f} orders/day) "
            f"reproduces a contribution of Rs {diag.get('reproduced_contribution', 0):.2f}/order "
            f"against the published target of Rs {diag.get('target_loss_per_order', -3.02):.2f}."
        )


if __name__ == "__main__":
    main()
