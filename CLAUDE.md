# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ceebboard is a Discord bot that tracks maimai (rhythm game) player statistics. It scrapes player data from SEGA's dxnet service via friend codes, stores rating history in SQLite, and generates visual rating progression graphs.

## Running the Bot

```bash
uv sync                            # Install dependencies
uv run playwright install chromium # Install Playwright browsers
uv run python startup.py                  # Production mode
uv run python startup.py --dev            # Dev mode (enables dev-only commands, uses DEV_DISCORD_TOKEN)
uv run python startup.py --offline        # Offline mode (skips scheduled user updates)
uv run python startup.py --dev --offline  # Both
```

## Configuration

Copy `example_config.json` to `config.json` and fill in credentials. Contains Discord bot tokens and SEGA account credentials for dxnet authentication.

## Architecture

**Entry point:** `startup.py` — initializes SQLite database, auto-discovers and registers commands, starts the Discord event loop.

**Bot client:** `ceebboard/bot.py` — singleton `CeebboardClient` extending `discord.Client`. Handles message routing to commands and runs a 30-minute scheduled loop to update all tracked users.

**Command system:** Plugin-based. Each command is a module in `ceebboard/Commands/` that exports:
- `COMMAND_INFO` — a `CommandInfo` instance with identifiers, usage string, description, and dev-only flag
- `exec_command(message, args)` — async execution function
- `check_validity(message, args)` — optional async validation function (defaults to `no_arg_validity`)

Commands are auto-discovered via `pkgutil.iter_modules`. The command prefix is `cb>`. To add a new command, create a new module in `Commands/` following this pattern.

**Scraper:** `ceebboard/scraper.py` — authenticates to dxnet via Playwright (browser automation through SEGA's login flow), then uses a persistent `requests` session to query friend code endpoints. Auto-reauthenticates on error codes 200004/200002.

**Database:** SQLite (`users.db`) with two tables:
- `users` — maps discord_id to friend_code, maimai_name, maimai_rating
- `user_data_history` — timestamped rating snapshots (only written when rating changes)

**Graph rendering:** `ceebboard/Commands/graph.py` — generates 800x600 rating-over-time images using PIL. Aggregates data into daily values, draws gridlines/labels, highlights the "best day" (largest single-day rating gain). Font files and background image are in `ceebboard/resources/`.

## Key Patterns

- All database access is async via `aiosqlite`
- Errors are surfaced to Discord users via `display_error()` embeds in `util.py`
- `update_user()` in `util.py` is the core function that scrapes and persists a user's current data
- The session store (`session_store.py`) holds a global `requests.Session` for authenticated dxnet requests
- No test framework is configured
