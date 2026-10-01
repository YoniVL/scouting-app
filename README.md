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

### Market values (phase 2)

Values come from your own CSV (columns `player_name, as_of_date, market_value_eur`;
optional `club, contract_until, provider, notes`; amounts like `10m` or `500k` work).
Names are matched accent-insensitively; add `club` to separate namesakes.

```bash
uv run scout import-values values.csv
uv run scout similar "Jamie Vardy" --max-value 10m --contract-ends-before 2018
uv run scout undervalued --role ST --max-value 10m --top 20
```

Alternatively, import the public CC0 dataset
[dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets)
(download the CSV zip from its README into a folder, then):

```bash
uv run scout import-transfermarkt path/to/transfermarkt-datasets/
```

Players are matched on name plus club; ambiguous or unmatched players get no value. The
dataset only holds each player's *current* contract expiry, so contracts are not imported
from it (use the CSV import with `contract_until` if you need them).

The `undervalued` score is performance rank (mean percentile) minus value rank within
season and role, among eligible players that have a value. It is only meaningful with
good value coverage, and is a screening aid rather than a verdict.

## Layout

- `src/scouting/sources/` one module per data source, mapping into the common schema
- `src/scouting/schema.py` common DuckDB schema (incl. empty `market_values` for phase 2)
- `data/` local cache + database (git-ignored)
