# TinyBI Agent Notes

## Scope

- This directory is a standalone FastAPI app, despite the parent repository's Markdown-only course guidance. Run project commands from `tinybi-demo/`.
- Keep the app local-first: no database, authentication, CORS, external backend service, or frontend build step.

## Commands

- Install or reconcile dependencies: `make install` or `uv sync`.
- Run locally: `make serve` (`uv run uvicorn main:app --reload`).
- Add packages only through `uv add <package>` or `uv add --dev <package>`; do not hand-edit dependency lists when `uv` can update `pyproject.toml` and `uv.lock` together.
- There is no configured test, lint, formatter, or typecheck suite. Use `uv run python -m py_compile main.py` for a backend syntax/import check and `node --check static/app.js` for frontend JavaScript syntax.

## Architecture

- `main.py` owns CSV decoding, pandas analysis, HTML/static mounting, and all routes: `GET /`, `GET /sample-data`, `POST /analyze`, and `POST /config`.
- `templates/index.html` and `static/app.js` are coupled to the JSON shape returned by `analyze_frame`; update both sides when changing metrics, charts, preview records, or dashboard config.
- Chart.js and fonts load from CDNs. There is no npm project or asset compilation.
- Dashboard config is process-global memory and intentionally resets when Uvicorn restarts.

## Data Constraints

- Preserve fallback decoding for `utf-8`, `utf-8-sig`, `cp1252`, and `latin1`; the bundled Superstore data is not guaranteed to be UTF-8.
- Uploads are capped at 15 MB, previews at 10 rows, and chart output at 100 groups. Keep API and UI behavior aligned if changing these limits.
- `.gitignore` ignores every `*.csv`, including `sample_data.csv`, but `GET /sample-data` requires that file at runtime. Verify it exists locally when testing the sample-data flow.

## Style

- Match the existing Python style: two-space indentation, single-quoted strings, and `dict(...)` where practical.
