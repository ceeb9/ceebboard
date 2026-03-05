# ceebboard

Discord bot that tracks [maimai](https://maimai.sega.com/) player statistics. Scrapes player data from SEGA's dxnet service via friend codes, stores rating history in SQLite, and generates visual rating progression graphs.

## Setup

```bash
git clone <repo-url> && cd ceebboard
uv sync
uv run playwright install chromium
```

Copy `.env.example` to `.env` and fill in your credentials:

```
PRODUCTION_DISCORD_TOKEN=...
DEV_DISCORD_TOKEN=...
SEGA_USERNAME=...
SEGA_PASSWORD=...
```

Only the production token is required for production mode. The dev token is only needed with `--dev`.

## Running

```bash
uv run python startup.py                  # Production mode
uv run python startup.py --dev            # Dev mode (uses DEV_DISCORD_TOKEN, enables dev-only commands)
uv run python startup.py --offline        # Offline mode (skips scheduled user updates)
uv run python startup.py --dev --offline  # Both
```

## CLI (development)

Run any command from the terminal without Discord:

```bash
uv run python cli.py <command> [args...] [--as <discord_id>]
```

Embeds are printed to stdout. Files (e.g. `graph.png`) are saved to the working directory.

`--as` sets the author's Discord ID for commands that act on "self" (graph, update, link).

Examples:
```bash
uv run python cli.py help
uv run python cli.py leaderboard
uv run python cli.py graph 123456789012345 -1
uv run python cli.py graph --as 123456789012345
```

## Commands

| Command | Description |
|---------|-------------|
| `cb>help` | List all available commands |
| `cb>link <friendcode>` | Link your Discord account to a maimai friend code |
| `cb>update` | Update your username and rating |
| `cb>graph [@user] [days]` | Rating progression graph (default 30 days, `-1` for full history) |
| `cb>leaderboard` | Leaderboard of all registered users |
| `cb>linkotheruser <friendcode> <discord_id>` | Link another user (dev only) |

## Architecture

- **`startup.py`** — Entry point. Initializes SQLite, registers commands, starts the Discord event loop.
- **`cli.py`** — CLI entry point. Mocks Discord objects, runs commands locally.
- **`ceebboard/bot.py`** — Singleton `CeebboardClient`. Handles message routing and a 30-minute scheduled update loop.
- **`ceebboard/Commands/`** — Plugin-based command system. Each module exports `COMMAND_INFO` and `exec_command`. Auto-discovered via `pkgutil`.
- **`ceebboard/scraper.py`** — Authenticates to dxnet via Playwright, queries friend code endpoints with a persistent `requests` session.
- **`ceebboard/util.py`** — Shared helpers: `display_error`, `display_info`, `update_user`.
- **`ceebboard/resources/`** — Fonts and background image for graph rendering.
