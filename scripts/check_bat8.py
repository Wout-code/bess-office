"""BAT-8 check: quarter-hours with simultaneous charge and discharge, per solver
and degradation cost (the base case from config and 0 = free wear, BAT-10). Data prep
copied from main.main() (not importable separately).

Usage: uv run python scripts/check_bat8.py [solver ...]   (default: appsi_highs)

kWh lost = sum over the simultaneous quarter-hours of min(charge, discharge)
x (1 - round-trip efficiency); the EUR upper bound values that at the lowest
price of the year. lost(charge) is a looser bound (all charging in those
quarter-hours) and is printed for reference only.
"""

import dataclasses
import sys
import warnings

import pandas as pd
import pyomo.environ as pyo

from bess_office.config import CONFIG
from bess_office.fetch_load import derive_peak_kwh_per_quarter, get_relative_profile
from bess_office.fetch_prices import get_day_ahead_prices
from bess_office.fetch_pv import get_pv_profile
import bess_office.optimize as opt

warnings.filterwarnings("ignore", category=UserWarning)

ts = CONFIG.sim.timestep_hours
pv = get_pv_profile().resample("15min").interpolate("linear") * ts / 1000
rel = get_relative_profile()
load = rel * derive_peak_kwh_per_quarter(CONFIG.building.area_m2, CONFIG.building.annual_kwh_per_m2, rel)
prices = get_day_ahead_prices(
    pd.Timestamp(f"{CONFIG.pv.year}-01-01", tz="Europe/Amsterdam"),
    pd.Timestamp(f"{CONFIG.pv.year + 1}-01-01", tz="Europe/Amsterdam"),
).resample("15min").ffill()
pv, load = pv.align(load, join="inner")
prices = prices.reindex(load.index, method="ffill")

# base case, then free wear as the upper bound (BAT-10)
DEGRADATION_COSTS_EUR_PER_KWH = (CONFIG.battery.degradation_cost_eur_per_kwh, 0.0)
eta = CONFIG.battery.round_trip_efficiency
usable = (CONFIG.battery.max_soc_fraction - CONFIG.battery.min_soc_fraction) * CONFIG.battery.capacity_kwh

_orig_factory = pyo.SolverFactory
solvers = sys.argv[1:] or ["appsi_highs"]
print(f"n quarter-hours: {len(load)}, negative-price qh: {(prices < 0).sum()}, min price {prices.min():.2f} EUR/MWh")
for solver in solvers:
    opt.pyo.SolverFactory = lambda name, _s=solver: _orig_factory(_s)
    for degradation_cost in DEGRADATION_COSTS_EUR_PER_KWH:
        battery = dataclasses.replace(CONFIG.battery, degradation_cost_eur_per_kwh=degradation_cost)
        name = f"deg={degradation_cost:.2f}"
        r = opt.run_lp_dispatch(pv, load, prices, battery, CONFIG.grid_tariff, timestep_hours=ts)
        for eps in (1e-6, 1e-3):
            mask = (r["charge_kwh"] > eps) & (r["discharge_kwh"] > eps)
            p = prices[mask]
            overlap = pd.concat([r["charge_kwh"], r["discharge_kwh"]], axis=1).min(axis=1)[mask]
            lost_overlap = (overlap * (1 - eta)).sum()
            lost_charge = (r["charge_kwh"][mask] * (1 - eta)).sum()
            bound_overlap_min = lost_overlap * abs(prices.min()) / 1000
            bound_charge_min = lost_charge * abs(prices.min()) / 1000
            print(
                f"{solver:12} {name} eps={eps:g}: n={mask.sum():4d}, neg={int((p < 0).sum()):4d}, "
                f"price range [{p.min() if len(p) else float('nan'):.2f}, {p.max() if len(p) else float('nan'):.2f}], "
                f"lost(min(c,d))={lost_overlap:7.1f} kWh -> <= EUR {bound_overlap_min:6.1f}; "
                f"lost(charge)={lost_charge:7.1f} kWh -> <= EUR {bound_charge_min:6.1f}; "
                f"cycles={r['discharge_kwh'].sum() / usable:.1f}"
            )
