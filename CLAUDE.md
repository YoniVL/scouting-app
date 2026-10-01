# CLAUDE.md

Personal football scouting tool (phase 1: data, profiles, similarity; CLI only; no AI layer,
no scraping of other sites).

## Data attribution (mandatory)

Data source is **StatsBomb Open Data** (github.com/statsbomb/open-data). StatsBomb must be
credited as the source in any publication or shared result. Keep this notice in README.md.

## Stack and commands

Python 3.11+, uv, DuckDB, pandas, scikit-learn, typer.

- `uv sync` install; `uv run pytest` tests; `uv run ruff check .` lint
- `uv run scout ingest|build|profile|similar`

## Conventions

- One module per data source in `src/scouting/sources/`, implementing `sources/base.py`;
  everything downstream only uses the common schema in `schema.py`.
- Keep functions small; tunables live in `config.py`.
- Players may count in several role groups (CB, FB, CM, AM, W, ST; GK excluded);
  percentiles are per (season, role) pool of players above the minimum minutes.
- Warn on small samples (below `MIN_MINUTES`).
- Code and docs in English. No model identifiers in commits or code.
