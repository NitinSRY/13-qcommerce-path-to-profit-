"""Tests for the real-geography path: OSM density grids + real order timing.

These run against the committed real artifacts (data/geo/*_density.csv and
data/order_timing.csv). They need no network and no raw downloads. If the artifacts
are missing they skip.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qcom.costs import CostModel
from qcom.desim import REAL_TIMING_PATH, real_hourly_weights
from qcom.geo import GridCity
from qcom.scenarios import REAL_CITIES, real_city_comparison, real_city_demand

_HAVE_GEO = all(Path(c["csv"]).exists() for c in REAL_CITIES.values())
_HAVE_TIMING = REAL_TIMING_PATH.exists()
pytestmark = pytest.mark.skipif(
    not (_HAVE_GEO and _HAVE_TIMING), reason="real geo/timing artifacts not built"
)


def test_density_grid_loads_and_anchors_population():
    cfg = REAL_CITIES["bengaluru"]
    city = GridCity.from_density_csv(
        cfg["csv"], center=cfg["center"], cell_km=cfg["cell_km"], population=cfg["population"]
    )
    assert city.n == city.density.shape[0]
    # rescaled so the grid holds the anchored population
    assert city.total_population() == pytest.approx(cfg["population"], rel=1e-6)
    assert (city.density > 0).all()  # floor keeps empty cells non-zero


def test_real_hourly_weights_are_a_distribution():
    w = real_hourly_weights()
    assert len(w) == 16
    assert w.sum() == pytest.approx(1.0)
    assert (w >= 0).all()


def test_metro_is_denser_than_tier2_from_real_data():
    """The real OSM grids must reproduce the metro / tier-2 order-density gap."""
    metro = real_city_demand("bengaluru")
    t2 = real_city_demand("lucknow")
    assert metro["orders_per_day"] > t2["orders_per_day"]


def test_real_geography_reproduces_the_tier2_penalty():
    """On real geography the tier-2 store must be worse off per order than the metro,
    which is the whole thesis of the project."""
    rows = real_city_comparison(CostModel(), replications=6)
    metro = next(r for r in rows if r["label"] == "metro")
    t2 = next(r for r in rows if r["label"] == "tier-2")
    assert metro["contribution_per_order"] > t2["contribution_per_order"]
    # both bleed at this cost model, but the tier-2 store bleeds materially more
    assert t2["contribution_per_order"] < 0


def test_drop_distance_comes_from_geometry():
    d = real_city_demand("bengaluru")
    # a real q-commerce catchment: sub-2km mean drop
    assert 0.1 < d["mean_drop_km"] < 2.0
