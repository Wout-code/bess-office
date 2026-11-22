"""Tests for the LP dispatch (optimize.py).

Deliberately run with timestep_hours=0.25: with hourly data kWh == kW and
unit errors stay invisible (see CLAUDE.md, Units).
"""

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest

from bess_office.config import BatteryConfig, GridTariffConfig
from bess_office.optimize import run_lp_dispatch

DT = 0.25  # hours per timestep (quarter-hour)
STEPS_PER_DAY = int(24 / DT)
TOL = 1e-6  # HiGHS works with a feasibility tolerance of ~1e-7

CHEAP_HOURS = range(0, 6)       # 20 EUR/MWh
EXPENSIVE_HOURS = range(17, 21)  # 250 EUR/MWh


def _index() -> pd.DatetimeIndex:
    # January: no DST switch, and a single calendar month (one monthly peak).
    return pd.date_range("2023-01-10 00:00", periods=STEPS_PER_DAY, freq="15min", tz="Europe/Amsterdam")


def _series(values_kw: list[float]) -> pd.Series:
    """Build a quarter-hour kWh series from a list of power values in kW."""
    return pd.Series([v * DT for v in values_kw], index=_index(), dtype=float)


def _hours() -> list[float]:
    return [i * DT for i in range(STEPS_PER_DAY)]


def _load() -> pd.Series:
    # Low night load, so night charging does not set a new monthly peak.
    return _series([30.0 if 7 <= h < 21 else 10.0 for h in _hours()])


def _pv() -> pd.Series:
    # Bell shape 07:00-17:00, peak 60 kW: surplus (30 kW) exceeds battery power
    # (20 kW), so export is unavoidable.
    return _series([max(0.0, 60.0 * math.sin((h - 7) / 10 * math.pi)) if 7 <= h <= 17 else 0.0 for h in _hours()])


def _prices() -> pd.Series:
    def price(h: float) -> float:
        if int(h) in CHEAP_HOURS:
            return 20.0
        if int(h) in EXPENSIVE_HOURS:
            return 250.0
        return 80.0

    return pd.Series([price(h) for h in _hours()], index=_index(), dtype=float)  # EUR/MWh


@pytest.fixture(scope="module")
def battery() -> BatteryConfig:
    # 5 kWh per quarter-hour. Degradation cost pinned to 0, not the config's
    # base case: these tests check physics and price response, and at 0 only
    # the charging loss stands against needless cycling, so the price-response
    # and BAT-8 tests are at their strictest. Wear pricing (BAT-10) has its own
    # test below.
    return BatteryConfig(capacity_kwh=100.0, power_kw=20.0, degradation_cost_eur_per_kwh=0.0)


@pytest.fixture(scope="module")
def result(battery) -> pd.DataFrame:
    # Solved once and shared: keeps the test file fast.
    return run_lp_dispatch(_pv(), _load(), _prices(), battery, GridTariffConfig(), timestep_hours=DT)


def test_lp_energy_balance_closes_every_step(result):
    balance = (
        result["load_kwh"] + result["charge_kwh"] + result["grid_export_kwh"]
        - result["pv_kwh"] - result["discharge_kwh"] - result["grid_import_kwh"]
    )
    assert balance.abs().max() < TOL
    assert result["grid_export_kwh"].max() > 0  # scenario also covers export


def test_lp_soc_within_bounds(result, battery):
    min_soc = battery.min_soc_fraction * battery.capacity_kwh
    max_soc = battery.max_soc_fraction * battery.capacity_kwh
    assert (result["soc_kwh"] >= min_soc - TOL).all()
    assert (result["soc_kwh"] <= max_soc + TOL).all()


def test_lp_end_soc_at_least_initial(result, battery):
    # BAT-9: no free draining of the battery at the end of the horizon.
    initial_soc = battery.initial_soc_fraction * battery.capacity_kwh
    assert result["soc_kwh"].iloc[-1] >= initial_soc - TOL


def test_lp_power_limit_in_kwh_per_step(result, battery):
    limit_kwh = battery.power_kw * DT  # 5 kWh per quarter-hour, not 20
    assert result["charge_kwh"].max() <= limit_kwh + TOL
    assert result["discharge_kwh"].max() <= limit_kwh + TOL
    # In this scenario both limits are binding (PV surplus > battery power,
    # evening peak price), so a limit applied in kW instead of kWh/step
    # would show up here instead of passing trivially.
    assert result["charge_kwh"].max() == pytest.approx(limit_kwh, abs=TOL)
    assert result["discharge_kwh"].max() == pytest.approx(limit_kwh, abs=TOL)


def test_lp_charges_cheap_discharges_expensive(result):
    hour = result.index.hour
    cheap = hour.isin(CHEAP_HOURS)
    expensive = hour.isin(EXPENSIVE_HOURS)

    assert result.loc[cheap, "charge_kwh"].sum() > 1.0
    assert result.loc[expensive, "discharge_kwh"].sum() > 1.0
    assert (result.loc[expensive, "charge_kwh"] <= TOL).all()
    assert (result.loc[cheap, "discharge_kwh"] <= TOL).all()


def test_lp_no_simultaneous_charge_discharge_at_positive_prices(result):
    # BAT-8: simultaneous charging/discharging is not excluded in the LP, but
    # at positive prices wasting energy through charging losses costs money,
    # so the solver should never choose it.
    assert (_prices() > 0).all()  # precondition of this test
    both = (result["charge_kwh"] > TOL) & (result["discharge_kwh"] > TOL)
    assert not both.any(), result.loc[both, ["charge_kwh", "discharge_kwh"]]


def test_lp_zero_battery_matches_no_battery():
    pv, load = _pv(), _load()
    # Default degradation cost is fine here: without capacity nothing is
    # discharged, so the wear cost cannot affect the result.
    empty = BatteryConfig(capacity_kwh=0.0, power_kw=0.0)

    result = run_lp_dispatch(pv, load, _prices(), empty, GridTariffConfig(), timestep_hours=DT)

    expected_import = np.clip((load - pv).to_numpy(), 0, None)
    expected_export = np.clip((pv - load).to_numpy(), 0, None)
    assert result["grid_import_kwh"].to_numpy() == pytest.approx(expected_import, abs=TOL)
    assert result["grid_export_kwh"].to_numpy() == pytest.approx(expected_export, abs=TOL)
    assert result["charge_kwh"].abs().max() <= TOL
    assert result["discharge_kwh"].abs().max() <= TOL


def test_lp_higher_degradation_cost_cycles_less(battery):
    # BAT-10: a cost per kWh discharged can only make cycling less attractive,
    # so a higher degradation cost never leads to more discharge.
    free_battery = dataclasses.replace(battery, degradation_cost_eur_per_kwh=0.0)
    free = run_lp_dispatch(_pv(), _load(), _prices(), free_battery, GridTariffConfig(), timestep_hours=DT)
    # 0.10 EUR/kWh is a synthetic test value, chosen high enough to change the
    # dispatch on this day (lower values leave it unchanged: the spread is wide).
    costly_battery = dataclasses.replace(battery, degradation_cost_eur_per_kwh=0.10)
    costly = run_lp_dispatch(_pv(), _load(), _prices(), costly_battery, GridTariffConfig(), timestep_hours=DT)

    assert costly["discharge_kwh"].sum() <= free["discharge_kwh"].sum() + TOL
    # Not trivially equal: at this value the LP really drops some cycling.
    assert costly["discharge_kwh"].sum() < free["discharge_kwh"].sum() - 1.0
