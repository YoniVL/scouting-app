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
from .report import profile_header, profile_table, similar_table
from .similarity import similar_players
from .sources.statsbomb import StatsBombSource
from .stats import build_player_season_stats

app = typer.Typer(help="Football scouting: profiles and similarity (data: StatsBomb Open Data).",
                  no_args_is_help=True)
console = Console()

DbOpt = Annotated[str, typer.Option("--db", envvar="SCOUT_DB", help="DuckDB file.")]
MinOpt = Annotated[float, typer.Option("--min-minutes", help="Minimum minutes for percentile pools.")]
SeasonOpt = Annotated[str | None, typer.Option("--season", help="Season name, e.g. 2015/2016.")]
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
    return compute_percentiles(stats, min_minutes)


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
    min_minutes: MinOpt = config.MIN_MINUTES, db: DbOpt = str(config.DB_PATH),
):
    """Most similar players in the same role (standardised percentiles + cosine)."""
    con = _db(db)
    pct = _load_percentiles(con, min_minutes)
    _, row = _pick_row(con, pct, player, season, role)
    for line in profile_header(row, min_minutes):
        console.print(line)
    results = similar_players(pct, row, top)
    console.print(similar_table(results, config.LIMITED_SAMPLE_MINUTES))
    console.print(f"[dim]Candidates: {row['role']} with ≥ {min_minutes:.0f} min; "
                  f"~ = under {config.LIMITED_SAMPLE_MINUTES} min. Data: StatsBomb Open Data.[/dim]")
