# scouting-app

Personal football scouting tool for finding undervalued players.
Phase 1: data ingest, player profiles (percentiles per role) and similarity search. CLI only.

## Data attribution

All data comes from **StatsBomb Open Data**
(<https://github.com/statsbomb/open-data>). Per the StatsBomb licence,
**StatsBomb must be credited as the source in every publication or shared result**
that uses this data. The data is not included in this repository.

## Setup

```bash
uv sync
uv run scout --help
```

## Usage

```bash
uv run scout ingest          # download + load 2015/16 PL, Ligue 1, La Liga, Serie A
uv run scout build           # aggregate per-90 stats per player/season/role
uv run scout profile "Jamie Vardy"
uv run scout similar "Jamie Vardy" --top 10
```

## Layout

- `src/scouting/sources/` one module per data source, mapping into the common schema
- `src/scouting/schema.py` common DuckDB schema (incl. empty `market_values` for phase 2)
- `data/` local cache + database (git-ignored)
