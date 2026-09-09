"""Gravity / Huff spatial demand catchment.

Huff's model allocates each demand cell's spending probabilistically across the
competing stores in proportion to store attractiveness and inverse distance:

    P(cell -> store s) = A_s / d(cell, s)^beta  /  sum_k A_k / d(cell, k)^beta

We convert per-capita order propensity + cell population into an expected order
arrival rate (orders/day) captured by a given dark store. This is the demand
side of the twin: it turns a density grid + store locations into the order rate
each store's discrete-event simulation will draw from.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qcom.geo import GridCity


@dataclass
class DemandModel:
    """Huff catchment over a GridCity.

    Parameters
    ----------
    city : the demand grid.
    orders_per_person_day : baseline q-commerce order propensity per capita.
        India's q-commerce is roughly tens of millions of orders/day over a
        few hundred million reachable people; ~0.02-0.06 orders/person/day in a
        served urban catchment is a defensible calibration anchor.
    beta : distance-decay exponent (higher = more local; 1.5-2.0 typical).
    max_serve_km : a store does not capture demand beyond this road distance
        (10-15 min delivery implies a small catchment radius).
    assortment : store attractiveness multiplier (assortment breadth / brand).
    """

    city: GridCity
    orders_per_person_day: float = 0.035
    beta: float = 1.8
    max_serve_km: float = 3.0
    assortment: float = 1.0

    def _cell_index_to_ij(self, idx: int) -> tuple[int, int]:
        return divmod(idx, self.city.n)

    def store_cell_distances(self, store_cells: list[tuple[int, int]]) -> np.ndarray:
        """Road-distance matrix, shape (n_cells, n_stores)."""
        n_cells = self.city.n_cells
        dist = np.empty((n_cells, len(store_cells)))
        for idx in range(n_cells):
            ij = self._cell_index_to_ij(idx)
            for s, sc in enumerate(store_cells):
                dist[idx, s] = self.city.road_km(ij, sc)
        return dist

    def capture_probabilities(
        self,
        store_cells: list[tuple[int, int]],
        attractiveness: np.ndarray | None = None,
    ) -> np.ndarray:
        """Huff capture probability of each cell by each store, shape (cells, stores).

        Rows sum to <= 1; the deficit is demand that leaks out of all catchments
        (too far from every store), which is exactly the coverage gap the
        facility-location optimizer tries to close.
        """
        dist = self.store_cell_distances(store_cells)
        if attractiveness is None:
            attractiveness = np.full(len(store_cells), self.assortment)
        # Out-of-range stores get zero pull for a cell.
        eps = 1e-6
        pull = attractiveness[None, :] / np.power(np.maximum(dist, eps), self.beta)
        pull[dist > self.max_serve_km] = 0.0
        denom = pull.sum(axis=1, keepdims=True)
        probs = np.divide(pull, denom, out=np.zeros_like(pull), where=denom > 0)
        # Cells with no in-range store contribute no captured demand.
        served = (denom > 0).astype(float)
        return probs * served

    def store_order_rates(
        self,
        store_cells: list[tuple[int, int]],
        attractiveness: np.ndarray | None = None,
    ) -> np.ndarray:
        """Expected orders/day captured by each store."""
        probs = self.capture_probabilities(store_cells, attractiveness)
        pop = self.city.cell_population().reshape(-1)
        cell_orders = pop * self.orders_per_person_day  # orders/day generated per cell
        return probs.T @ cell_orders

    def covered_demand_fraction(
        self,
        store_cells: list[tuple[int, int]],
        attractiveness: np.ndarray | None = None,
    ) -> float:
        """Fraction of all generated orders/day that lands in some catchment."""
        rates = self.store_order_rates(store_cells, attractiveness)
        pop = self.city.cell_population().sum()
        total = pop * self.orders_per_person_day
        return float(rates.sum() / total) if total > 0 else 0.0
