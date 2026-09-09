"""Build a real demand-density grid for a city from OpenStreetMap.

Quick-commerce demand is not spread evenly over a city: it clusters where people
actually live, shop and eat. The real spatial distribution of that activity is
observable in OpenStreetMap as the location of shops, restaurants, cafes, markets
and pharmacies. This script queries the Overpass API for those points inside a
city bounding box and bins them onto the same n x n grid the digital twin uses,
producing a real relative-demand surface (a committed CSV) that replaces the
synthetic Gaussian-bump density.

The count per cell is a proxy for commercial/residential intensity, not a literal
population, so the loader (`GridCity.from_density_csv`) rescales the surface to the
area's real population. What comes from OSM is the *shape* of demand across the
city; the *level* is anchored to a real population figure.

Usage:
    python scripts/fetch_osm_density.py            # builds all cities in CITIES
Output: data/geo/<city>_density.csv  (an n x n grid of relative demand weights)
"""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np

OUT_DIR = Path("data/geo")
RAW_DIR = OUT_DIR / "raw"
OVERPASS = "https://overpass-api.de/api/interpreter"
KM_PER_DEG_LAT = 111.32

# POI classes that track where q-commerce demand comes from.
POI_FILTER = (
    'node["shop"](BBOX);'
    'node["amenity"~"restaurant|cafe|fast_food|marketplace|pharmacy|food_court"](BBOX);'
)

# Real cities: a metro and a tier-2, each with a real centre and a grid geometry
# that matches the twin (n x n cells of cell_km each, centred on `center`).
CITIES = {
    "bengaluru": {"center": (12.9716, 77.5946), "n": 16, "cell_km": 0.9, "population": 900_000},
    "lucknow": {"center": (26.8467, 80.9462), "n": 16, "cell_km": 0.9, "population": 500_000},
}


def _bbox(center: tuple[float, float], n: int, cell_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) covering the whole n x n grid."""
    half_km = n * cell_km / 2.0
    km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(center[0]))
    dlat = half_km / KM_PER_DEG_LAT
    dlon = half_km / km_per_deg_lon
    return (center[0] - dlat, center[1] - dlon, center[0] + dlat, center[1] + dlon)


def _fetch_raw(name: str, bbox: tuple[float, float, float, float]) -> dict:
    """Return the Overpass JSON for a city, using a cached copy if present.

    Raw responses are cached under data/geo/raw/<city>.json so the grid can be
    rebuilt offline and the public Overpass endpoint is hit at most once per city.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{name}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    s, w, n, e = bbox
    box = f"{s},{w},{n},{e}"
    body = "[out:json][timeout:120];(" + POI_FILTER.replace("BBOX", box) + ");out;"
    # curl is the reliable HTTP client in the build environment. One try per call;
    # rerun the script to fetch a city that got rate-limited.
    proc = subprocess.run(
        [
            "curl", "-sL", "--max-time", "180",
            "-A", "qcom-path-to-profit/1.0 (research)",
            "-G", OVERPASS, "--data-urlencode", f"data={body}",
        ],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    cache.write_text(json.dumps(payload))
    return payload


def _points(payload: dict) -> list[tuple[float, float]]:
    return [(el["lat"], el["lon"]) for el in payload["elements"] if "lat" in el and "lon" in el]


def _bin_to_grid(
    pts: list[tuple[float, float]], center: tuple[float, float], n: int, cell_km: float
) -> np.ndarray:
    """Bin POI points onto the grid using the twin's cell geometry (row 0 = north)."""
    km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(center[0]))
    half = (n - 1) / 2.0
    grid = np.zeros((n, n), dtype=float)
    for lat, lon in pts:
        dy_km = (lat - center[0]) * KM_PER_DEG_LAT   # north positive
        dx_km = (lon - center[1]) * km_per_deg_lon   # east positive
        j = int(round(dx_km / cell_km + half))
        i = int(round(half - dy_km / cell_km))       # row 0 = north
        if 0 <= i < n and 0 <= j < n:
            grid[i, j] += 1.0
    return grid


def build_city(name: str, cfg: dict) -> np.ndarray:
    bbox = _bbox(cfg["center"], cfg["n"], cfg["cell_km"])
    payload = _fetch_raw(name, bbox)
    pts = _points(payload)
    grid = _bin_to_grid(pts, cfg["center"], cfg["n"], cfg["cell_km"])
    print(f"{name}: {len(pts)} real POIs -> grid sum {grid.sum():.0f}, "
          f"peak cell {grid.max():.0f}, empty cells {(grid == 0).mean():.0%}")
    return grid


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, cfg in CITIES.items():
        grid = build_city(name, cfg)
        out = OUT_DIR / f"{name}_density.csv"
        np.savetxt(out, grid, delimiter=",", fmt="%.1f")
        print(f"  wrote {out}")
        time.sleep(2)  # be polite to the public Overpass endpoint


if __name__ == "__main__":
    main()
