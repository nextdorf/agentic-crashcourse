# Project Instructions

- Use `uv` for dependency management.
- Add runtime dependencies with `uv add <package>`.
- Add development dependencies with `uv add --dev <package>`.
- Avoid direct manual edits to `pyproject.toml` when possible; let `uv` update dependency metadata and the lockfile.
- `uv` is preferred because it keeps setup simple, reproducible, and fast.

Common commands:

- `uv sync` installs dependencies.
- `uv run uvicorn main:app --reload` runs the app.
- `make serve` runs the local development server.
