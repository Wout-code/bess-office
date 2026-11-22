"""Plots for the bess-office results."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Categorical colours in fixed order (dataviz reference palette, light mode).
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# (key in compute_financial_metrics, label, colour). Order = stacking order.
COST_COMPONENTS = [
    ("import_cost_eur", "Electricity bought (day-ahead)", "#2a78d6"),
    ("energy_tax_cost_eur", "Energy tax", "#eb6834"),
    ("transport_cost_eur", "Transport tariff", "#1baf7a"),
    ("peak_cost_eur", "Monthly peak tariff", "#eda100"),
    ("degradation_cost_eur", "Battery wear", "#008300"),  # BAT-10; slot 6 (slot 5 is export)
]
EXPORT_COMPONENT = ("export_revenue_eur", "Export revenue (subtracted)", "#e87ba4")

# (key, label) per component for the savings chart, in display order. Export is
# a revenue, so its saving has the opposite sign of the cost components.
SAVINGS_COMPONENTS = [
    ("import_cost_eur", "Electricity\nbought"),
    ("energy_tax_cost_eur", "Energy tax"),
    ("transport_cost_eur", "Transport\ntariff"),
    ("peak_cost_eur", "Monthly\npeak tariff"),
    ("degradation_cost_eur", "Battery\nwear"),  # no battery = 0, so always a negative saving
    ("export_revenue_eur", "Export\nrevenue"),
]
SCENARIO_COLOURS = ["#8e8c86", "#2a78d6"]  # first scenario grey, second blue


def _eur(value: float, _pos=None) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}€{abs(value) / 1000:.0f}k"


def _bar_label(value: float) -> str:
    """Value label for a bar: in thousands, or in whole euros below €100."""
    sign = "−" if value < 0 else ""
    if abs(value) < 100:
        return f"{sign}€{abs(value):.0f}"
    return f"{sign}€{abs(value) / 1000:.1f}k"


def _style_axes(ax) -> None:
    """Shared axis styling: light grid, no frame, euro formatting on y."""
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.tick_params(axis="y", colors=TEXT_SECONDARY)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)


def _save(fig, path: Path, show: bool, layout: bool = True) -> Path:
    """Save the figure; keep it open only if main.py will show it."""
    if layout:
        fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    if not show:
        plt.close(fig)
    return path


def plot_cost_breakdown(
    financials: dict[str, dict], path: Path, wear_cost_eur_per_kwh: float, show: bool = True
) -> Path:
    """
    Stacked bar chart of annual cost per component, one bar per scenario.

    Parameters
    ----------
    financials : dict[str, dict]
        Scenario label -> output of main.compute_financial_metrics.
        Insertion order is the bar order.
    path : Path
        Output PNG path; parent directories are created if needed.
    wear_cost_eur_per_kwh : float
        Battery wear cost used for these results, shown in the title (BAT-10).
    show : bool
        If True, keep the figure open so main.py can show it with plt.show();
        otherwise close it after saving.

    Returns
    -------
    Path
        The path written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = list(financials)
    x = range(len(labels))
    width = 0.55

    fig, ax = plt.subplots(figsize=(8, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # Costs stacked above zero; a 2 px surface-coloured edge separates the segments.
    bottoms = [0.0] * len(labels)
    for key, label, color in COST_COMPONENTS:
        values = [financials[s][key] for s in labels]
        ax.bar(x, values, width, bottom=bottoms, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        bottoms = [b + v for b, v in zip(bottoms, values)]

    # Export as a deduction: negative segment below the zero line.
    key, label, color = EXPORT_COMPONENT
    exports = [-financials[s][key] for s in labels]
    ax.bar(x, exports, width, color=color, label=label, edgecolor=SURFACE, linewidth=2)

    # Net cost as a number above the bar.
    for i, s in enumerate(labels):
        net = financials[s]["net_cost_eur"]
        ax.annotate(
            f"net €{net:,.0f}",
            xy=(i, bottoms[i]),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=TEXT_PRIMARY,
        )

    _style_axes(ax)
    ax.set_xticks(list(x), labels, color=TEXT_PRIMARY)
    ax.set_ylim(min(exports) * 1.6, max(bottoms) * 1.12)

    ax.set_ylabel("EUR per year", color=TEXT_SECONDARY)
    ax.set_title(
        f"Annual cost per component\n(battery wear €{wear_cost_eur_per_kwh:.2f}/kWh discharged; "
        "2023 prices and PV, 2026 tariffs)",
        color=TEXT_PRIMARY,
        loc="left",
        fontsize=12,
    )
    # Legend in the same order as the stack from top to bottom:
    # cost components reversed, export (below zero) last.
    handles, legend_labels = ax.get_legend_handles_labels()
    order = list(range(len(COST_COMPONENTS)))[::-1] + [len(COST_COMPONENTS)]
    ax.legend(
        [handles[i] for i in order],
        [legend_labels[i] for i in order],
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(1.0, 1.0),
        labelcolor=TEXT_PRIMARY,
    )

    return _save(fig, path, show)


def plot_savings_breakdown(
    reference: dict,
    scenarios: dict[str, dict],
    path: Path,
    wear_cost_eur_per_kwh: float,
    show: bool = True,
) -> Path:
    """
    Grouped bar chart of the annual saving per cost component versus a
    reference (no battery), one bar per scenario.

    Parameters
    ----------
    reference : dict
        Output of main.compute_financial_metrics for the no-battery case.
    scenarios : dict[str, dict]
        Scenario label -> output of main.compute_financial_metrics.
        Insertion order is the bar order within each group.
    path : Path
        Output PNG path; parent directories are created if needed.
    wear_cost_eur_per_kwh : float
        Battery wear cost used for these results, shown in the title (BAT-10).
    show : bool
        If True, keep the figure open so main.py can show it with plt.show();
        otherwise close it after saving.

    Returns
    -------
    Path
        The path written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = list(scenarios)
    n = len(labels)
    width = 0.8 / n
    x = range(len(SAVINGS_COMPONENTS))

    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor=SURFACE)  # wide enough that labels of adjacent bars don't overlap
    ax.set_facecolor(SURFACE)

    for j, (label, colour) in enumerate(zip(labels, SCENARIO_COLOURS)):
        fin = scenarios[label]
        savings = []
        for key, _ in SAVINGS_COMPONENTS:
            if key == "export_revenue_eur":
                savings.append(fin[key] - reference[key])  # more export revenue = saving
            else:
                savings.append(reference[key] - fin[key])  # lower cost = saving
        total = reference["net_cost_eur"] - fin["net_cost_eur"]
        offsets = [i + (j - (n - 1) / 2) * width for i in x]
        bars = ax.bar(
            offsets, savings, width, color=colour, edgecolor=SURFACE, linewidth=2,
            label=f"{label}: total €{total:,.0f}/year",
        )
        for bar, value in zip(bars, savings):
            if round(value) == 0:
                continue  # a "€0" label on an invisible bar only adds noise
            ax.annotate(
                _bar_label(value),
                xy=(bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 4 if value >= 0 else -4),
                textcoords="offset points",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8.5,
                color=TEXT_PRIMARY,
            )

    _style_axes(ax)
    ax.set_xticks(list(x), [lbl for _, lbl in SAVINGS_COMPONENTS], color=TEXT_PRIMARY)

    ax.set_ylabel("Change vs. no battery, EUR per year\n(+ saving, − extra cost or lost revenue)",
                  color=TEXT_SECONDARY)
    ax.set_title(
        f"Where the savings come from\n(battery wear €{wear_cost_eur_per_kwh:.2f}/kWh discharged; "
        "2023 prices and PV, 2026 tariffs)",
        color=TEXT_PRIMARY,
        loc="left",
        fontsize=12,
    )
    ax.legend(frameon=False, loc="upper right", labelcolor=TEXT_PRIMARY)

    # Short explanation of the two components that are easy to misread.
    fig.text(
        0.01,
        0.01,
        "Electricity bought: lower cost of electricity bought from the grid (cheaper hours, own PV stored).\n"
        "Export revenue: less income from feed-in, because PV is stored and used instead of sold.",
        fontsize=8,
        color=TEXT_SECONDARY,
        ha="left",
        va="bottom",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))  # leave room for the explanation
    return _save(fig, path, show, layout=False)