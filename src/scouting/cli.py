"""Command line interface: scout ingest | build | profile | similar."""

from typing import Annotated

import pandas as pd
import typer
from rich.console import Console
from rich.progress import Progress

from . import config
from .db import connect
from .ingest import ingest as run_ingest
from .lookup import find_players
from .percentiles import compute_percentiles
from .report import profile_header, profile_table, similar_table, undervalued_table
from .similarity import similar_players
from .sources.statsbomb import StatsBombSource
from .stats import build_player_season_stats
from .tm_dataset import import_transfermarkt
from .values import (
    attach_values,
    filter_by_value,
    import_values,
    parse_amount,
    undervalued_scores,
)

app = typer.Typer(help="Football scouting: profiles and similarity (data: StatsBomb Open Data).",
                  no_args_is_help=True)
console = Console()

DbOpt = Annotated[str, typer.Option("--db", envvar="SCOUT_DB", help="DuckDB file.")]
MinOpt = Annotated[float, typer.Option("--min-minutes", help="Minimum minutes for percentile pools.")]
SeasonOpt = Annotated[str | None, typer.Option("--season", help="Season name, e.g. 2015/2016.")]
MaxValueOpt = Annotated[str | None, typer.Option("--max-value", help="e.g. 10m or 500k.")]
ContractOpt = Annotated[
    str | None, typer.Option("--contract-ends-before", help="Date or year, e.g. 2018.")]
RoleOpt = Annotated[str | None, typer.Option("--role", help="CB, FB, CM, AM, W or ST.")]


def _db(path: str):
    return connect(path)


@app.command()
def ingest(
    competition: Annotated[list[int] | None, typer.Option(help="StatsBomb competition_id")] = None,
    season: Annotated[list[int] | None, typer.Option(help="StatsBomb season_id")] = None,
    db: DbOpt = str(config.DB_PATH),
):
    """Download and load matches (default: 2015/16 PL, Ligue 1, La Liga, Serie A)."""
    if bool(competition) != bool(season) or len(competition or []) != len(season or []):
        raise typer.BadParameter("Give --competition and --season the same number of times.")
    selection = list(zip(competition, season, strict=True)) if competition else config.PRESET_2015_16
    con = _db(db)
    with Progress(console=console) as progress:
        task = progress.add_task("Ingesting matches", total=None)
        loaded = run_ingest(con, StatsBombSource(), selection,
                            progress=lambda done, total: progress.update(
                                task, completed=done, total=total))
    rows = build_player_season_stats(con)
    console.print(f"Loaded {loaded} new matches; {rows} player-season-role rows.")
    console.print("[dim]Data: StatsBomb Open Data (credit StatsBomb when sharing results).[/dim]")


@app.command()
def build(db: DbOpt = str(config.DB_PATH)):
    """Rebuild per-90 stats from the loaded events and minutes."""
    console.print(f"{build_player_season_stats(_db(db))} player-season-role rows.")


def _load_percentiles(con, min_minutes: float) -> pd.DataFrame:
    stats = con.execute("SELECT * FROM player_season_stats").df()
    if stats.empty:
        console.print("[red]No stats yet. Run `scout ingest` first.[/red]")
        raise typer.Exit(1)
    values = con.execute("SELECT * FROM market_values").df()
    return attach_values(compute_percentiles(stats, min_minutes), values)


def _pick_row(con, pct: pd.DataFrame, query: str, season: str | None, role: str | None):
    """Resolve a name to one player-season-role row (most minutes by default)."""
    players = con.execute("SELECT * FROM players").df()
    found = find_players(players, query)
    rows = pct[pct["player_id"].isin(found["player_id"])]
    if season:
        rows = rows[rows["season_name"] == season]
    if role:
        rows = rows[rows["role"] == role.upper()]
    if rows.empty:
        console.print(f"[red]No player found for '{query}'"
                      f"{' with these filters' if season or role else ''}.[/red]")
        raise typer.Exit(1)
    if rows["player_id"].nunique() > 1:
        console.print(f"[yellow]'{query}' is ambiguous, be more specific:[/yellow]")
        for _, r in rows.sort_values("minutes", ascending=False).drop_duplicates("player_id").iterrows():
            console.print(f"  {r['player_name']} ({r['teams']}, {r['season_name']})")
        raise typer.Exit(1)
    return rows.sort_values("minutes", ascending=False), rows.sort_values("minutes").iloc[-1]


@app.command()
def profile(
    player: Annotated[str, typer.Argument(help="Player name (partial, accent-insensitive).")],
    season: SeasonOpt = None, role: RoleOpt = None,
    min_minutes: MinOpt = config.MIN_MINUTES, db: DbOpt = str(config.DB_PATH),
):
    """Percentile profile within the player's role group."""
    con = _db(db)
    rows, row = _pick_row(con, _load_percentiles(con, min_minutes), player, season, role)
    for line in profile_header(row, min_minutes):
        console.print(line)
    console.print(profile_table(row))
    others = rows[(rows["role"] != row["role"]) | (rows["season_name"] != row["season_name"])]
    if not others.empty:
        opts = ", ".join(f"{r['role']} {r['season_name']} ({r['minutes']:.0f} min)"
                         for _, r in others.iterrows())
        console.print(f"[dim]Also played: {opts}. Use --role / --season.[/dim]")
    console.print("[dim]Data: StatsBomb Open Data.[/dim]")


@app.command()
def similar(
    player: Annotated[str, typer.Argument(help="Player name (partial, accent-insensitive).")],
    top: Annotated[int, typer.Option(help="Number of results.")] = 10,
    season: SeasonOpt = None, role: RoleOpt = None,
    max_value: MaxValueOpt = None, contract_ends_before: ContractOpt = None,
    min_minutes: MinOpt = config.MIN_MINUTES, db: DbOpt = str(config.DB_PATH),
):
    """Most similar players in the same role (standardised percentiles + cosine).

    Value filters need imported market values; players without data are left out.
    """
    con = _db(db)
    pct = _load_percentiles(con, min_minutes)
    _, row = _pick_row(con, pct, player, season, role)
    for line in profile_header(row, min_minutes):
        console.print(line)
    results = similar_players(pct, row, None)
    results = filter_by_value(results, _amount(max_value), _date_limit(contract_ends_before))
    results = results.head(top)
    console.print(similar_table(results, config.LIMITED_SAMPLE_MINUTES))
    console.print(f"[dim]Candidates: {row['role']} with ≥ {min_minutes:.0f} min; "
                  f"~ = under {config.LIMITED_SAMPLE_MINUTES} min. Data: StatsBomb Open Data.[/dim]")


def _amount(text: str | None) -> float | None:
    return parse_amount(text) if text else None


def _date_limit(text: str | None) -> pd.Timestamp | None:
    return pd.Timestamp(f"{text}-01-01" if len(text) == 4 else text) if text else None


@app.command("import-values")
def import_values_cmd(
    csv: Annotated[str, typer.Argument(help="CSV: player_name, as_of_date, market_value_eur, "
                                            "[club, contract_until, provider, notes]")],
    db: DbOpt = str(config.DB_PATH),
):
    """Import market values / contracts from a CSV file (phase 2)."""
    res = import_values(_db(db), csv)
    console.print(f"Imported {res['imported']} values.")
    if res["unmatched"]:
        console.print(f"[yellow]Unmatched or ambiguous ({len(res['unmatched'])}):[/yellow] "
                      + ", ".join(res["unmatched"]))
        console.print("[dim]Add a `club` column to disambiguate namesakes.[/dim]")


@app.command()
def undervalued(
    top: Annotated[int, typer.Option(help="Number of results.")] = 20,
    season: SeasonOpt = None, role: RoleOpt = None, max_value: MaxValueOpt = None,
    contract_ends_before: ContractOpt = None,
    min_minutes: MinOpt = config.MIN_MINUTES, db: DbOpt = str(config.DB_PATH),
):
    """Players whose performance rank is well above their market-value rank.

    Performance = mean percentile over all stats, ranked within (season, role) among
    eligible players with a value. Score = performance rank - value rank (-100..100).
    """
    pct = undervalued_scores(_load_percentiles(_db(db), min_minutes))
    df = pct[pct["eligible"] & pct["undervalued"].notna()]
    if df.empty:
        console.print("[red]No values available. Run `scout import-values` first.[/red]")
        raise typer.Exit(1)
    if season:
        df = df[df["season_name"] == season]
    if role:
        df = df[df["role"] == role.upper()]
    df = filter_by_value(df, _amount(max_value), _date_limit(contract_ends_before))
    console.print(undervalued_table(df.sort_values("undervalued", ascending=False).head(top)))
    console.print("[dim]Score is a rough screening aid, not a verdict. "
                  "Data: StatsBomb Open Data.[/dim]")


@app.command("import-transfermarkt")
def import_transfermarkt_cmd(
    directory: Annotated[str, typer.Argument(help="Folder with players.csv, "
                                                  "player_valuations.csv, clubs.csv")],
    db: DbOpt = str(config.DB_PATH),
):
    """Import values from the public Transfermarkt dataset (needs `scout build` first)."""
    res = import_transfermarkt(_db(db), directory)
    console.print(f"Matched {res['matched']} of {res['players']} players; "
                  f"{res['valuations']} valuations stored.")
    console.print("[dim]Unmatched players simply have no value (names or clubs differ).[/dim]")
