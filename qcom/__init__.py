"""Quick-commerce path-to-profit engine.

A spatial dark-store digital twin: gravity demand catchment, a hand-rolled
discrete-event simulation of one dark store (arrivals, picking queue, rider
dispatch with batching over a road graph), a per-order contribution-margin
model calibrated to published FY26 financials, a from-scratch facility-location
optimizer, a derivative-free breakeven-frontier search, and Sobol global
sensitivity analysis.

The package is deliberately dependency-light (numpy + scipy + networkx) so it
runs offline on a laptop and every line is defensible.
"""

__version__ = "0.1.0"

from qcom.geo import GridCity, haversine_km
from qcom.demand import DemandModel
from qcom.costs import CostModel, OrderEconomics
from qcom.desim import DarkStoreSim, SimConfig, SimResult

__all__ = [
    "GridCity",
    "haversine_km",
    "DemandModel",
    "CostModel",
    "OrderEconomics",
    "DarkStoreSim",
    "SimConfig",
    "SimResult",
    "__version__",
]
