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

These are not assumptions about how the calculation works (that is under V1/V2
below) — this is about what the data itself represents and where its
limitations lie. Applies identically regardless of which
calculation model you use.

**DATA-1 — Time zone**
- All three data sources (load, PV, prices) are explicitly converted to
  Europe/Amsterdam, not UTC. Reason: the capacity tariff and
  dispatch decisions are tied to local clock time (e.g.
  "evening peak at 18:00"), not to UTC. The price paid for this:
  the clock changes in March/October must be handled explicitly
  (see DATA-5/DATA-6 below) — UTC would have avoided that complexity,
  but would make results less directly recognizable relative to the
  actual local usage situation.

**DATA-2 — Resolution**
- Quarter-hour, identical for both files — no V1/V2 difference. This was
  always a `main.py` choice (which data you supply), never something in
  `dispatch_sim.py`/`optimize.py` itself: both simply take
  `timestep_hours` as a parameter and compute with whatever they get. `main.py`
  upsamples PV to quarter-hours (instead of downsampling load to hours), so that the
  billing-relevant quarter-hour peak is not averaged away.

**DATA-5 — PV data (PVGIS)**
- By default (`usehorizon=True`, no `userhorizon`), PVGIS uses a
  terrain shading model based on an elevation map — it sees natural
  elevations (hills), but not buildings. If the reference building is on
  a business park/in an urban area with taller neighbouring buildings that
  cast shade early/late in the day, PVGIS structurally underestimates those losses,
  without any warning in the output — the PV yield is then
  overestimated.

**DATA-6 — Load data (Liander K&O profile)**
- Normalized profile, not a real measurement — therefore also no real
  clock-change irregularity (365×96 quarter-hours, no gaps). Making it
  tz-aware therefore requires a deliberate, pragmatic choice
  (`nonexistent="shift_forward"`, `ambiguous=True`) instead of a
  real DST correction as for prices/PV, which do run on real
  measurements.
  Note what this profile actually is: Liander's own K&O standard profile,
  built from telemetry of large consumers (grootverbruikers) and used by Liander itself
  to estimate new large-consumer customers (see external
  documentation MOOI EIGEN SBI-profielen). The profile shape therefore determines
  nothing about whether the modeled building is a small or large consumer (klein- of grootverbruik) — that is
  purely a function of the scale (area_m2/annual_kwh_per_m2, see DATA-8),
  not of this file.

**DATA-7 — Load profile smoothing (coincidence)**
- Because the Liander K&O profile is a mathematical average of hundreds of
  buildings, the curve is smoothed (coincidence factor). The peaks of
  a real building are higher, so the value of peak reduction is in this
  model probably underestimated. Those real peaks are, however, short and
  erratic, and therefore in practice harder to predict and to
  eliminate than here with a perfect forecast (TIME-2).

**DATA-8 — Reference building, large-consumer scale**
- 4,500 m² instead of 590 m², annual_kwh_per_m2 unchanged (115 kWh/m²/year,
  Dutch average, does not change with scale). Deliberately chosen so that the
  calculated peak ends up well above the large-consumer threshold (55 kVA / 3x80A),
  instead of sitting right at it. Calculation:
  sum(relative_profile) on KO_KANTOOR_ONDERWIJS, verified via
  `get_relative_profile().sum()`: 20,824.42. 4,500 x 115 = 517,500
  kWh/year -> peak_kwh_per_quarter = 517,500 / 20,824.42 = 24.85
  kWh/quarter-hour -> peak = 99.4 kW (verified via notebook run).
  peak_kwh_per_quarter is no longer a separate BuildingConfig field, but is
  derived in main.py via derive_peak_kwh_per_quarter() (fetch_load.py)
  — prevents area_m2 and peak_kwh_per_quarter from silently drifting
  apart.

**DATA-9 — Battery model, BOLT-241**
- Boltainer BOLT-241 (Dutch manufacturer): 241 kWh capacity, power options
  49/60/99/120 kW. 99 kW chosen based on the calculated peak (99.4 kW,
  DATA-8) — same "power ≈ peak" logic as in the original
  SigenStor choice. Capacity checked against the same
  capacity-to-daily-consumption ratio as before (~19%): new
  daily average 517,500/365 ≈ 1,418 kWh/day, 19% of that ≈ 270 kWh — 241
  kWh is slightly below that ratio (cycling slightly more often/deeper than with the old
  ratio).
  NOTE: found via a single search, not thoroughly verified for
  price/availability/delivery time. Usable capacity (after
  min/max SoC) and round-trip efficiency of this specific product have
  not been looked up separately — BatteryConfig still uses the old,
  generic SigenStor assumptions (90%/10%/95%) as a placeholder for these. TODO:
  verify.

**DATA-10 — PV sizing, export-aware**
- 190 kWp instead of 25 kWp, same underlying ratio as the
  original (undocumented) "annual consumption rule of thumb"
  comment in PVConfig: 25 kWp / 67,850 kWh (old annual consumption) ≈ 0.368
  kWp per MWh/year, applied to the new annual consumption (517,500 kWh) ->
  ~190.6 kWp.
  Deliberate choice between two strategies: (a) export-aware, ~33%
  annual coverage (190 kWp, chosen) vs. (b) full annual consumption
  coverage (~673 kWp, common residential rule of thumb: 1.3 kWp per 1,000 kWh
  annual consumption). (b) requires ~2,605 m² of roof area (1,447 panels
  at 465 Wp x 1.8 m²/panel), (a) ~736 m² — the latter fits
  comfortably within a 4,500 m² building, the former is on the tight
  side.
  Reason for (a): for large consumers, export is structurally valued lower
  than self-consumption (see ARCH-5) — an installation that
  mainly targets export uses a large part of its kWp on the least
  valuable part of the yield.
  NOTE: this is a ratio-preserving extrapolation of an
  originally unsubstantiated number (no notebook/calculation
  found for the original 25 kWp), not an independently
  verified rule of thumb. TODO if time permits: own justification (e.g.
  roof area availability) instead of ratio preservation.

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
