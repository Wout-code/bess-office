# Assumptions — bess-office
The file has two model versions: V1 is the rule-based model
(`dispatch_sim.py`) only; V2 adds the LP optimization (`optimize.py`) and
corrects some V1 assumptions. The data assumptions apply to both.

ID scheme: every assumption has a unique ID per category: `DATA-n` (input data),
`BAT-n` (battery), `TIME-n` (time/foresight), `NET-n` (market and grid) and
`ARCH-n` (model architecture). Numbers are never reused: a new assumption gets
the next free number in its category. When an assumption is corrected, the
correction gets a new ID that refers back to the old one (e.g. BAT-7
"corrects BAT-1").

Replaced data assumptions are removed from this file, so gaps in the numbering
(such as DATA-3 and DATA-4) are expected. V1 assumptions that V2 corrects stay
listed, marked as corrected, because V1 still describes the rule-based model.
This file shows only what currently applies.

Code comments refer to these IDs, so when you change an assumption here, also
check the matching comment in the code.

## Data & reference case (applies to both V1 and V2 — concerns the input, not the calculation)

**DATA-1 — Time zone**
- All data (load, PV, prices) is converted to Europe/Amsterdam, not UTC: the
  Liander profile is in local time, and the monthly peak is billed per calendar
  month in local time. The cost is that clock changes must be handled per source
  (DATA-5, DATA-6).

**DATA-2 — Resolution**
- Quarter-hour, because the monthly peak is billed on the highest quarter-hour.
  PV (hourly from PVGIS) is interpolated linearly to quarter-hours rather than
  averaging the load to hours, so the quarter-hour peak is preserved. Prices
  (hourly in 2023, before the 15-minute market of October 2025) are held
  constant within each hour.

**DATA-5 — PV data (PVGIS)**
- PVGIS has hourly resolution, so short cloud transients within the hour are not represented.
  Together with the smoothed load profile (DATA-7), the model sees fewer and
  milder short-term net-load peaks than a real building.
- PVGIS's default shading model uses an elevation map: it sees hills, but not
  buildings. Shading from taller neighbouring buildings is not included, so PV
  yield may be overestimated.

**DATA-6 — Load data (Liander K&O profile)**
- Liander's own standard profile for offices, built from telemetry of large
  consumers and used by Liander to estimate new large-consumer connections
  (source: Liander, "MOOI EIGEN SBI-profielen"). It is a normalized shape, not
  a measurement of one building; the absolute level comes from the scaling in
  DATA-8. This matches the modeled building: at that scale its peak (99.4 kW)
  is well above the large-consumer threshold.
- Because it is a normalized 365 × 96 profile without real clock changes, it
  is made tz-aware pragmatically: the missing hour in March is shifted forward
  (duplicates dropped), and the double hour in October is assigned to summer
  time. Prices and PV, which are real time series, are converted exactly,
  including the clock changes (DATA-1).

**DATA-7 — Load profile smoothing**
- The Liander K&O profile averages many buildings, and their peaks do not
  coincide, so the curve is smoother than that of any single building. A real
  building with the same annual consumption has higher, sharper peaks. Two
  consequences: the 99.4 kW peak (DATA-8) is lower than a real building's, and
  the value of peak reduction is probably underestimated. Real peaks are,
  however, short and erratic, so in practice they are harder to predict and to
  eliminate than here with perfect foresight (TIME-2).

**DATA-8 — Reference building, large-consumer scale**
- Hypothetical reference building, not a real site. 4,500 m² office at
  115 kWh/m²/year
- 4,500 m² office at 115 kWh/m²/year (Dutch average for offices, range
  100–150) gives 517.5 MWh/year. The area is chosen so that the peak lands well
  above the large-consumer threshold (3x80A, ~55 kVA) instead of right at it.
- Peak: scaling the profile to this annual total gives 24.85 kWh in the
  busiest quarter-hour, i.e. 99.4 kW
  (517,500 kWh / profile sum 20,824.42 = 24.85 kWh per quarter-hour).
- The peak is derived from area and intensity in code
  (`derive_peak_kwh_per_quarter`), not set separately, so the two cannot drift
  apart.

**DATA-9 — Battery, BOLT-241**
- Boltainer BOLT-241 (Dutch manufacturer, LFP): 241 kWh, power options
  49/60/99/120 kW. 99 kW chosen to match the 99.4 kW peak (DATA-8), so the
  battery could in principle cover the full peak. Capacity is about 17% of the
  average daily consumption (1,418 kWh/day); no further sizing optimization was
  done.
- Round-trip efficiency and usable SoC range are not stated in the datasheet.
  The model uses typical LFP values: 90% round-trip and SoC 10–95%. Price and
  availability are not verified. Manufacturer cycle life: ≥ 6,000 cycles,
  without stated test conditions (see BAT-3).

**DATA-10 — PV sizing**
- 190 kWp (~409 panels of 465 Wp, ~740 m² of panel area), producing
  186.6 MWh/year: about 36% of annual consumption.
- Two reasons for this size rather than covering the full annual consumption
  (~670 kWp, ~2,600 m² of panels):
  - Roof area: 190 kWp needs ~740 m² of panels, which fits on the roof of a
    multi-storey 4,500 m² office. Full coverage (~2,600 m²) would need a roof
    of more than half the total floor area, i.e. a building of at most one or
    two floors.
  - Export value: for large consumers, exported energy is worth less than
    self-consumed energy (no net metering, no avoided transport and tax, see
    ARCH-5). At 190 kWp, 78% of PV production is consumed on site even without
    a battery; a larger system would mainly add low-value export.
- Not optimized: the PV size was not optimized together with the battery.

---

## V1 — dispatch_sim.py only (rule-based)

**Battery**
- **BAT-1** — Symmetric charge/discharge power — same power in both
  directions (simplification, not physically correct — corrected in V2,
  see BAT-7)
- **BAT-2** — Discharging is lossless; charging losses occur only when charging
- **BAT-3** — No degradation over time — capacity/efficiency remain
  constant.
  Degradation is therefore also deliberately **not** in the LP objective (no
  cycle cost). Rationale: measured
  equivalent full cycles/year (`main.py`, 2023 data) are RBC 102, LP
  scenario A 487 (1.33/day), LP scenario B 264. That compares with ≥ 6000 cycles for the BOLT-241 (manufacturer's
  specification, not verified, see DATA-9): even at 487/year ~12 years. At low
  C-rates, ageing is mainly determined by time, temperature and throughput,
  and hardly by depth of discharge (DoD) (Wang et al., 2011);
  their tests started at C/2, this system runs at 99 kW / 241 kWh ≈ 0.41C.
  A DoD-dependent cost is therefore not needed; a cost per kWh of throughput
  is, but that is not implemented.
- **BAT-4** — No minimum on/off time — battery switches freely
- **BAT-5** — Efficiency/capacity constant, regardless of SoC, charging rate
  or temperature
- **BAT-6** — No self-discharge

**Time**
- **TIME-1** — No look-ahead — purely reactive, each quarter-hour on its own

**Market/Grid**
- **NET-1** — One fixed, static peak threshold for the whole year
  (corrected in V2, see NET-4)
- **NET-2** — Peak shaving responds only to import, not to export peaks
- **NET-3** — Unlimited feed-in — no export limit/curtailment

**Architecture**
- **ARCH-1** — No costs/prices in the model itself — purely a physical
  energy-flow simulation, the financial translation happens elsewhere
- **ARCH-2** — Battery can structurally never charge from the grid — only
  from PV surplus (corrected in V2, see ARCH-3)
- **ARCH-5 — Symmetric import/export prices** — `compute_financial_metrics`
  values import and export at the same day-ahead price. In
  reality, export misses the avoided transport tariff that
  self-consumption does save, and feed-in for large consumers is
  usually compensated below the full import price
  (market-price-linked supplier contract — for large consumers there is
  no net metering (saldering), so no fixed 1-to-1 settlement to
  fall back on). Direction of the error: this overvalues export, and therefore a
  larger PV installation relative to a smaller one (see DATA-10). A quantitative
  correction requires a real feed-in contract figure that is currently not
  available — TODO. Remains in force unchanged for V2:
  `optimize.py` does not use `main.py`'s `compute_financial_metrics`
  itself, but the financial post-processing in `main.py` is identical for
  both dispatch versions.

---

# V2 — dispatch_sim.py + optimize.py

`dispatch_sim.py` does not disappear in V2 — it remains alongside
`optimize.py`, and receives the fixes that are not a matter of algorithm but
of correct physics or better parameters.

## Shared between both files in V2

**Battery**
- **BAT-7** — Asymmetric charge/discharge power — corrects BAT-1.
  **Planned, not yet implemented**: both files still use
  `power_kw` for charging and discharging, so BAT-1 is effectively still in force.
- BAT-2 through BAT-6 remain in force unchanged

**Market/Grid**
- **NET-4** — Optimized peak threshold instead of a fixed annual threshold —
  corrects NET-1. Internally in `optimize.py`: one peak variable per
  calendar month. In `dispatch_sim.py` it remains one threshold for the whole
  year, but it is no longer chosen by hand: `main.py`
  (`select_rbc_threshold`) scans 50–98 kW in steps of 2 kW
  (`DispatchConfig.threshold_scan_*`) and selects the threshold with the lowest
  annual net cost (2023: 52 kW). Prices appear only in that scan;
  the rule itself remains price-agnostic and reactive (ARCH-1, TIME-1). Note:
  this is an ex-post choice on the same year (in-sample), and thus favourable
  to the RBC.
- **NET-5** — Energy tax (energiebelasting) as a fixed rate per imported kWh
  (`GridTariffConfig.energy_tax_eur_per_kwh = 0.03735`): the marginal bracket
  50,000–10 million kWh, 2026 rate excl. VAT, applied to 2023 prices.
  Only on import, no net metering (saldering) (large consumer). Included both in the
  LP objective and in `compute_financial_metrics`. The higher rates of the
  first 50,000 kWh are not modeled: that is a fixed cost, not
  decision-relevant.
- **NET-6** — Scenario B: hypothetical double energy tax on storage,
  an additional 0.03735 EUR per kWh that goes into the battery
  (`storage_charge_tax_eur_per_kwh`, default 0.0 = scenario A). Based on
  the debate about double energy taxation on storage, which in
  reality mainly applies behind small-consumer connections. It is
  an upper bound, because PV charging (all `charge_kwh`) is taxed as well. The
  LP is re-solved for B; the RBC dispatch is price-agnostic and stays
  the same, only its costs are recalculated.
- See ARCH-5 (under V1 — Architecture) for export/import priced symmetrically
  — applies identically to V2, no separate NET ID needed.
- NET-2, NET-3 remain in force unchanged

**Architecture**
- **ARCH-3** — Grid charging becomes possible — corrects ARCH-2.
  Implemented in both files. `optimize.py`: free, the solver
  decides. `dispatch_sim.py`: standard peak-shaving rule — as long as the
  import (kW) stays below the threshold, charge from the grid with at most the
  remaining headroom up to the threshold, limited by `power_kw` (minus what is already
  being charged from PV) and max SoC, with the same charging loss as PV charging
  (BAT-2). Side effect: RBC self-consumption drops (2023, threshold 52 kW: 83.1%
  without vs. 78.6% with grid charging; without battery 78.3%), because the
  battery is more often full when PV surplus arrives: peak shaving and
  self-consumption compete for the same SoC, and the threshold makes that
  trade-off implicitly. The net cost of the RBC at the same threshold is also slightly
  higher with grid charging (€63,558 vs. €63,300).

## dispatch_sim.py specific (remains rule-based)

**Time**
- TIME-1 remains in force unchanged — still no look-ahead,
  inherent to a reactive rule, not something that gets "fixed"

**Architecture**
- ARCH-1 remains in force unchanged for this file — still no
  costs in the model itself, the financial translation happens elsewhere

## optimize.py

**Time**
- **TIME-2** — Perfect forecast within the horizon — replaces TIME-1
  for this file ("no look-ahead" no longer applies)

**Architecture**
- **ARCH-4** — Costs sit directly in the objective, no separate
  financial layer — replaces ARCH-1 for this file

**Battery**
- **BAT-8** — Assumed that charging and discharging never happen simultaneously
  because the solver always chooses the most efficient solution. **Checked
  (2023 data): does not hold at negative prices.** Scenario A: 399 of the
  35,032 quarter-hours with simultaneous charging and discharging, all at a
  negative price (1,256 quarter-hours < 0). In those, 546 kWh is lost to
  charging losses; even valued at the lowest price
  (−500 EUR/MWh) that is at most ~€270/year, ~3% of the LP savings.
  Scenario B: 16 quarter-hours, also all at a negative price. Deliberately
  not solved with binaries: the model remains an LP, because a MILP over
  35,040 quarter-hours solves much more slowly and does not give a guaranteed global optimum
  within practical time. The effect is financially small and visibly
  reported.
- **BAT-9** — End SoC ≥ initial SoC (`initial_soc_fraction`) at the end
  of the horizon. Without this condition, the LP drains the battery for free at the
  end and counts that energy as savings. The RBC does not have this
  condition (2023: ends at 208.8 kWh vs. 120.5 kWh at the start, a
  small disadvantage for the RBC).

## Important context, not an assumption

*Context, not an assumption*: at 99 kW, this system stays below the 100 kW
threshold above which a congestion management contract becomes relevant
(RVO Flex-e conditions: the power of the measure, not of the
connection, is decisive). A factual given, not a choice — mentioned
because it places the 99 kW choice in a broader regulatory context.
