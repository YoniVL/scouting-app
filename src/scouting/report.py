"""Rich terminal rendering for profile and similarity output."""

import math

import pandas as pd
from rich.table import Table

from .percentiles import PCT_COLS, sample_warning
from .stats import P90_STATS
from .values import format_eur

LABELS = {
    "passes_p90": "Passes", "progressive_passes_p90": "Progressive passes",
    "carries_p90": "Carries", "progressive_carries_p90": "Progressive carries",
    "shots_p90": "Shots (non-pen)", "npxg_p90": "npxG",
    "tackles_p90": "Tackles", "interceptions_p90": "Interceptions",
    "pressures_p90": "Pressures",
}


def bar(pct: float, width: int = 20) -> str:
    if math.isnan(pct):
        return "n/a"
    return "█" * round(pct / 100 * width) + "·" * (width - round(pct / 100 * width))


def profile_header(row, min_minutes: float) -> list[str]:
    lines = [
        f"[bold]{row['player_name']}[/bold]  {row['role']}  {row['season_name']}",
        (f"{row['teams']} ({row['competitions']}) · {row['matches']} matches · "
         f"{row['minutes']:.0f} min · pool: {row['pool_size']} {row['role']} "
         f"with ≥ {min_minutes:.0f} min"),
    ]
    if not math.isnan(row.get("market_value_eur", float("nan"))):
        contract = row["contract_until"]
        until = f", contract until {contract:%Y-%m-%d}" if pd.notna(contract) else ""
        lines.append(f"Market value {format_eur(row['market_value_eur'])}{until} "
                     f"(as of {row['value_date']:%Y-%m-%d})")
    warning = sample_warning(row["minutes"], min_minutes)
    if warning:
        lines.append(f"[yellow]⚠ {warning}[/yellow]")
    return lines


def profile_table(row) -> Table:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("per 90", justify="right")
    table.add_column("Pctl", justify="right")
    table.add_column("")
    for stat, pct_col in zip(P90_STATS, PCT_COLS, strict=True):
        table.add_row(LABELS[stat], f"{row[stat]:.2f}", f"{row[pct_col]:.0f}", bar(row[pct_col]))
    return table


def similar_table(results, limited_below: float) -> Table:
    table = Table(show_header=True, header_style="bold")
    right = ("#", "Minutes", "Similarity", "Value")
    for name in ("#", "Player", "Season", "Team", "Minutes", "Value", "Contract", "Similarity"):
        table.add_column(name, justify="right" if name in right else "left")
    for i, (_, r) in enumerate(results.iterrows(), 1):
        mark = "~" if r["minutes"] < limited_below else ""
        table.add_row(str(i), r["player_name"], r["season_name"], r["teams"],
                      f"{r['minutes']:.0f}{mark}", format_eur(r["market_value_eur"]),
                      _date(r["contract_until"]), f"{r['similarity']:.3f}")
    return table


def _date(ts) -> str:
    return "" if pd.isna(ts) else f"{ts:%Y-%m}"


def undervalued_table(df) -> Table:
    table = Table(show_header=True, header_style="bold")
    for name in ("#", "Player", "Role", "Team", "Minutes", "Value", "Perf", "Value rank", "Score"):
        table.add_column(name, justify="left" if name in ("Player", "Role", "Team") else "right")
    for i, (_, r) in enumerate(df.iterrows(), 1):
        table.add_row(str(i), r["player_name"], r["role"], r["teams"], f"{r['minutes']:.0f}",
                      format_eur(r["market_value_eur"]), f"{r['perf_rank']:.0f}",
                      f"{r['value_rank']:.0f}", f"{r['undervalued']:+.0f}")
    return table
