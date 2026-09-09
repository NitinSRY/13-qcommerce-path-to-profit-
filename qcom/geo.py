"""Spatial primitives: a grid city and the road graph the riders travel on.

A city is modelled as a square grid of cells. Each cell carries a population
density and a longitude/latitude. Travel between points is along an 8-neighbour
road graph (a stand-in for the street network when no OSRM matrix is available),
with a detour factor that inflates straight-line distance to road distance the
way real streets do.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass
class GridCity:
    """A square demand grid for one city.

    Parameters
    ----------
    n : grid side length (n x n cells).
    cell_km : physical size of one cell edge in km.
    center : (lat, lon) of the grid centre.
    density : per-cell population density (people / km^2), shape (n, n).
    detour : multiplier turning straight-line km into road km (Indian metros ~1.4).
    """

    n: int
    cell_km: float
    center: tuple[float, float]
    density: np.ndarray
    detour: float = 1.4

    def __post_init__(self) -> None:
        if self.density.shape != (self.n, self.n):
            raise ValueError(f"density must be {self.n}x{self.n}, got {self.density.shape}")
        # Approximate degrees-per-km at this latitude for placing cell centroids.
        self._km_per_deg_lat = 111.32
        self._km_per_deg_lon = 111.32 * math.cos(math.radians(self.center[0]))

    @property
    def n_cells(self) -> int:
        return self.n * self.n

    @property
    def cell_area_km2(self) -> float:
        return self.cell_km * self.cell_km

    def cell_population(self) -> np.ndarray:
        """People per cell = density * cell area."""
        return self.density * self.cell_area_km2

    def total_population(self) -> float:
        return float(self.cell_population().sum())

    def latlon(self, i: int, j: int) -> tuple[float, float]:
        """Centroid (lat, lon) of cell (i, j); grid centred on `center`."""
        half = (self.n - 1) / 2.0
        dx_km = (j - half) * self.cell_km
        dy_km = (half - i) * self.cell_km  # row 0 is north
        lat = self.center[0] + dy_km / self._km_per_deg_lat
        lon = self.center[1] + dx_km / self._km_per_deg_lon
        return lat, lon

    def centroids(self) -> np.ndarray:
        """All cell centroids as an (n_cells, 2) array of (lat, lon)."""
        pts = np.empty((self.n_cells, 2))
        for i in range(self.n):
            for j in range(self.n):
                pts[i * self.n + j] = self.latlon(i, j)
        return pts

    def road_km(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """Road distance in km between two cells, straight-line * detour factor."""
        la, lo = self.latlon(*a)
        lb, lob = self.latlon(*b)
        return haversine_km(la, lo, lb, lob) * self.detour

    @staticmethod
    def from_density_csv(
        path: str,
        center: tuple[float, float],
        cell_km: float,
        population: float,
        floor_frac: float = 0.05,
        detour: float = 1.4,
    ) -> "GridCity":
        """Build a city from a real demand-weight grid (e.g. OSM POI counts).

        The CSV is an n x n grid of relative demand weights: the *shape* of demand
        across the city, taken from real data. It is rescaled here so the cells sum
        to a real `population`, which sets the *level*. A small floor is added so
        cells with no mapped POI still hold some residents (people live where OSM
        has no shop tagged), which keeps the catchment from ignoring them entirely.
        """
        weights = np.loadtxt(path, delimiter=",", dtype=float)
        if weights.ndim != 2 or weights.shape[0] != weights.shape[1]:
            raise ValueError(f"density csv must be square, got {weights.shape}")
        n = weights.shape[0]
        # Floor is a fraction of the mean weight, so empty cells are not exactly zero.
        floor = floor_frac * weights.mean()
        w = weights + floor
        w = w / w.sum()
        cell_area = cell_km * cell_km
        # people per cell = share of population; density = people / cell area.
        density = w * population / cell_area
        return GridCity(n=n, cell_km=cell_km, center=center, density=density, detour=detour)

    @staticmethod
    def synthetic(
        n: int = 16,
        cell_km: float = 0.75,
        center: tuple[float, float] = (26.85, 80.95),  # Lucknow-ish, a tier-2 city
        peak_density: float = 18000.0,
        floor_density: float = 800.0,
        n_centers: int = 2,
        detour: float = 1.4,
        seed: int = 7,
    ) -> "GridCity":
        """Build a realistic-looking monocentric/polycentric density grid.

        Density falls off as a sum of Gaussian bumps around a few urban centres,
        on top of a low suburban floor. This reproduces the dense-core /
        sparse-edge structure that drives the tier-2 economics.
        """
        rng = np.random.default_rng(seed)
        xs, ys = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        dens = np.full((n, n), floor_density, dtype=float)
        for _ in range(n_centers):
            cx = rng.uniform(0.25, 0.75) * (n - 1)
            cy = rng.uniform(0.25, 0.75) * (n - 1)
            sigma = rng.uniform(0.15, 0.30) * n
            bump = peak_density * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * sigma**2))
            dens += bump
        # Mild multiplicative noise so no two cells are identical.
        dens *= rng.uniform(0.85, 1.15, size=(n, n))
        return GridCity(n=n, cell_km=cell_km, center=center, density=dens, detour=detour)
