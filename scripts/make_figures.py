"""Generate the report figures: the breakeven frontier, the Sobol tornado, and
the dark-store placement map. Saved under reports/.

Usage:
    python scripts/make_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qcom.costs import CostModel
from qcom.calibrate import calibrate_to_metro
from qcom.frontier import frontier_curve, aov_only_strawman
from qcom.sensitivity import run_sobol
from qcom.geo import GridCity
from qcom.place import FacilityLocator

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def fig_frontier(cost: CostModel) -> None:
    curve = frontier_curve(cost, replications=10)
    straw = aov_only_strawman(cost, replications=10)
    dens = [r["orders_per_day"] for r in curve]
    req_ad = [(r["required_ad_take"] or np.nan) * 100 for r in curve]

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(dens, req_ad, "o-", color="#1f77b4", label="required ad take to break even")
    ax1.set_xlabel("order density (orders/day)")
    ax1.set_ylabel("required ad take (% of AOV)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.set_title("Breakeven frontier: denser stores need less monetisation")

    ax2 = ax1.twinx()
    sd = [r["orders_per_day"] for r in straw]
    sc = [r["contribution"] for r in straw]
    ax2.plot(sd, sc, "s--", color="#d62728", label="AOV-only strawman contribution")
    ax2.axhline(0, color="grey", lw=0.8)
    ax2.set_ylabel("AOV-only contribution (Rs/order)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    fig.tight_layout()
    fig.savefig(REPORTS / "frontier.png", dpi=130)
    plt.close(fig)


def fig_sobol(cost: CostModel) -> None:
    sob = run_sobol(cost, n=48, replications=3)
    names = sob.names
    order = np.argsort(sob.ST)
    fig, ax = plt.subplots(figsize=(7, 4))
    y = np.arange(len(names))
    ax.barh(y, sob.ST[order], color="#2ca02c", alpha=0.85, label="total ST")
    ax.barh(y, sob.S1[order], color="#1f77b4", alpha=0.9, height=0.5, label="first-order S1")
    ax.set_yticks(y)
    ax.set_yticklabels([names[i] for i in order])
    ax.set_xlabel("Sobol index (share of margin variance)")
    ax.set_title("What actually moves margin: density and batching, not basket")
    ax.legend()
    fig.tight_layout()
    fig.savefig(REPORTS / "sobol_tornado.png", dpi=130)
    plt.close(fig)


def fig_placement() -> None:
    city = GridCity.synthetic(n=14, cell_km=0.8)
    loc = FacilityLocator(city, service_km=2.0, candidate_stride=2)
    opt = loc.solve(6, with_bound=False)
    fig, ax = plt.subplots(figsize=(6, 5.5))
    dens = city.density
    im = ax.imshow(dens, cmap="YlOrRd", origin="upper")
    for (i, j) in opt.store_cells:
        ax.scatter(j, i, marker="*", s=320, edgecolor="black", color="white", zorder=3)
    ax.set_title(f"Optimized placement: {opt.covered_fraction:.0%} of demand covered")
    fig.colorbar(im, ax=ax, label="population density (people/km^2)")
    fig.tight_layout()
    fig.savefig(REPORTS / "placement_map.png", dpi=130)
    plt.close(fig)


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    cost, _ = calibrate_to_metro(CostModel(), -3.02, 709, replications=12)
    fig_frontier(cost)
    fig_sobol(cost)
    fig_placement()
    print(f"figures written to {REPORTS}")


if __name__ == "__main__":
    main()
