"""Build a real intraday order-timing profile from real order timestamps.

The digital twin fires order arrivals as a non-homogeneous Poisson process, and the
shape of that process over the day drives peak-hour congestion in the picking queue
and the rider fleet. Rather than hand-pick the hourly weights, this derives them from
real data: the hour-of-day distribution of ~25,900 real online-retail orders (UCI
"Online Retail", InvoiceDate timestamps).

Honest note on fit: this is a real *online-retail* ordering curve, which peaks around
midday and tails off by early evening. Indian quick-commerce skews later (a dinner
peak), so this is a real, defensible arrival shape but not a q-commerce-specific one;
the twin keeps its synthetic bimodal profile available for comparison. What is real
here is that the intraday shape comes from observed orders, not from assumption.

Source: UCI Machine Learning Repository, "Online Retail" (id 352). Download and
unzip into data/raw/ (see data/raw/README.md), then:

    python scripts/fetch_order_timing.py

Output: data/order_timing.csv  (hour 0-23, share of orders)
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

RAW_GLOB = "data/raw/*.xlsx"
OUT = Path("data/order_timing.csv")


def build_profile() -> pd.DataFrame:
    files = glob.glob(RAW_GLOB)
    if not files:
        raise FileNotFoundError(
            "raw Online Retail file not found under data/raw/ - see data/raw/README.md"
        )
    df = pd.read_excel(files[0], usecols=["InvoiceNo", "InvoiceDate"]).dropna()
    # One row per order (invoice), not per line item.
    orders = df.drop_duplicates("InvoiceNo")
    hour = pd.to_datetime(orders["InvoiceDate"]).dt.hour
    counts = hour.value_counts().reindex(range(24), fill_value=0).sort_index()
    share = counts / counts.sum()
    return pd.DataFrame({"hour": range(24), "orders": counts.values, "share": share.values})


def main() -> None:
    prof = build_profile()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prof.to_csv(OUT, index=False)
    active = prof[prof["orders"] > 0]
    peak = prof.loc[prof["share"].idxmax()]
    print(f"wrote {OUT} from {int(prof['orders'].sum())} real orders")
    print(f"  active hours {int(active['hour'].min())}-{int(active['hour'].max())}, "
          f"peak at {int(peak['hour'])}h ({peak['share']:.1%})")


if __name__ == "__main__":
    main()
