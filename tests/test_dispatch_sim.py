"""Tests for the rule-based dispatch (dispatch_sim.py).

Draaien bewust met timestep_hours=0.25: bij uurdata is kWh == kW en
blijven eenheidsfouten onzichtbaar (zie CLAUDE.md, Eenheden).
"""

import pandas as pd
import pytest

from bess_office.config import BatteryConfig
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch

DT = 0.25  # uur per tijdstap (kwartier)
THRESHOLD_KW = 40.0


def _series(values_kw: list[float]) -> pd.Series:
    """Build a quarter-hour kWh series from a list of power values in kW."""
    index = pd.date_range("2023-01-02 08:00", periods=len(values_kw), freq="15min", tz="Europe/Amsterdam")
    return pd.Series([v * DT for v in values_kw], index=index, dtype=float)


@pytest.fixture
def battery() -> BatteryConfig:
    return BatteryConfig(capacity_kwh=100.0, power_kw=50.0)


def test_rbc_discharges_above_threshold_and_not_below(battery):
    load_kw = [60.0, 60.0, 20.0, 20.0, 60.0]
    load = _series(load_kw)
    pv = _series([0.0] * len(load_kw))

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    above = [lk > THRESHOLD_KW for lk in load_kw]
    assert (result.loc[above, "discharge_kwh"] > 0).all()
    # Import teruggebracht tot precies de drempel (genoeg SoC beschikbaar).
    assert result.loc[above, "grid_import_kwh"].div(DT).to_numpy() == pytest.approx(THRESHOLD_KW)
    below = [not a for a in above]
    assert (result.loc[below, "discharge_kwh"] == 0).all()


def test_metrics_report_peaks_in_kw(battery):
    load = _series([60.0, 20.0, 20.0])
    pv = _series([0.0, 0.0, 0.0])

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)
    metrics = compute_dispatch_metrics(result, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    assert metrics["peak_import_no_battery_kw"] == pytest.approx(60.0)  # niet 15 (kWh/kwartier)
    assert metrics["peak_import_with_battery_kw"] == pytest.approx(THRESHOLD_KW)


def test_rbc_grid_charges_up_to_threshold(battery):
    load = _series([20.0, 20.0])
    pv = _series([0.0, 0.0])

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    # Ruimte tot drempel: (40 - 20) kW x 0,25 h = 5 kWh, onder power (12,5 kWh/stap).
    assert result["charge_kwh"].to_numpy() == pytest.approx([5.0, 5.0])
    assert result["grid_import_kwh"].div(DT).to_numpy() == pytest.approx([THRESHOLD_KW, THRESHOLD_KW])
    initial_soc = battery.initial_soc_fraction * battery.capacity_kwh
    eta = battery.round_trip_efficiency
    assert result["soc_kwh"].to_numpy() == pytest.approx([initial_soc + 5 * eta, initial_soc + 10 * eta])


def test_rbc_grid_charging_respects_power_and_max_soc():
    load = _series([0.0, 0.0])
    pv = _series([0.0, 0.0])

    # Ruimte tot drempel 40 kW x 0,25 = 10 kWh, maar power is 20 kW -> 5 kWh/stap.
    small = BatteryConfig(capacity_kwh=100.0, power_kw=20.0)
    result = run_baseline_dispatch(pv, load, small, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)
    assert result["charge_kwh"].to_numpy() == pytest.approx([5.0, 5.0])

    full = BatteryConfig(capacity_kwh=100.0, power_kw=50.0, initial_soc_fraction=0.95)
    result = run_baseline_dispatch(pv, load, full, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)
    assert (result["charge_kwh"] == 0).all()
    assert (result["soc_kwh"] <= full.max_soc_fraction * full.capacity_kwh + 1e-9).all()


def test_rbc_import_never_exceeds_threshold_with_enough_soc(battery):
    load_kw = [10.0, 35.0, 55.0, 25.0, 45.0, 5.0]
    load = _series(load_kw)
    pv = _series([0.0, 0.0, 0.0, 30.0, 0.0, 10.0])

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    assert result["grid_import_kwh"].div(DT).max() <= THRESHOLD_KW + 1e-9
    # Energiebalans sluit per stap.
    balance = (
        result["pv_kwh"] + result["discharge_kwh"] + result["grid_import_kwh"]
        - result["load_kwh"] - result["charge_kwh"] - result["grid_export_kwh"]
    )
    assert balance.abs().max() < 1e-9
