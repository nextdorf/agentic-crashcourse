# Tic-Tac-Toe MCP

A minimal Tic-Tac-Toe game exposed through FastAPI and FastMCP. It accompanies the [TicTacToe over MCP](../crashcourse/03%20MCP%20servers.md#tictactoe-over-mcp) workshop section.

Requires Python 3.13 or newer and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the game, `/docs` for the HTTP API, or connect an MCP client to `http://127.0.0.1:8000/mcp/`.

The browser, HTTP API, and MCP clients share one in-memory game. Reloading or restarting Uvicorn resets it.
