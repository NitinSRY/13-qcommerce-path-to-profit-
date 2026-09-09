# Real demand geography (OpenStreetMap)

The twin can run on the real spatial structure of a city instead of a synthetic
density grid. The demand surface comes from the real location of shops, restaurants,
cafes, markets and pharmacies in OpenStreetMap - a proxy for where quick-commerce
demand actually originates.

## Committed files

- `bengaluru_density.csv`, `lucknow_density.csv` - 16x16 grids of POI counts per
  cell (one metro, one tier-2). These are small and committed; the twin reads them
  via `GridCity.from_density_csv`, which rescales the counts to a real population
  anchor so the *shape* of demand is real and the *level* is set by population.

Real structure captured: Bengaluru returns ~10,800 POIs spread across many cells
(polycentric metro); Lucknow returns ~520 POIs concentrated in a single core
(monocentric tier-2). That contrast - and the shorter drops but far lower volume it
implies for the tier-2 store - is the point.

## Rebuilding from source

`raw/` holds the cached Overpass API responses (not committed). To refetch and
rebuild the grids:

```
python scripts/fetch_osm_density.py
```

Source: OpenStreetMap via the Overpass API (https://overpass-api.de). Data (c)
OpenStreetMap contributors, ODbL. City centres, grid size and population anchors are
defined in `scripts/fetch_osm_density.py` and `qcom/scenarios.py`.
