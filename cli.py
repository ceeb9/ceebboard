from __future__ import annotations
import sys, asyncio, sqlite3
from types import SimpleNamespace

import ceebboard
import ceebboard.Commands.Command
from ceebboard.Commands.Command import Command


# --- Mock Discord objects ---

class CLIChannel:
    async def send(self, *, content: str | None = None, embed: object | None = None, file: object | None = None) -> None:
        if embed is not None:
            color = getattr(embed, 'color', None) or getattr(embed, 'colour', None)
            tag = "EMBED"
            if color is not None:
                color_val = color.value if hasattr(color, 'value') else int(color)
                if color_val == 0xe74c3c:  # discord red
                    tag = "ERROR"
                elif color_val == 0x3498db:  # discord blue
                    tag = "INFO"
                elif color_val == 0x2ecc71:  # discord green
                    tag = "OK"

            title = getattr(embed, 'title', None) or ""
            desc = getattr(embed, 'description', None) or ""
            print(f"[{tag}] {title}")
            if desc:
                print(desc)

            fields = getattr(embed, 'fields', [])
            for f in fields:
                print(f"{f.name}: {f.value}")
            print()

        if content is not None:
            print(content)

        if file is not None:
            filename = getattr(file, 'filename', 'output.bin')
            fp = getattr(file, 'fp', None)
            if fp is not None:
                data = fp.read()
                with open(filename, 'wb') as out:
                    out.write(data)
                print(f"Saved: {filename}")


class CLIUser:
    def __init__(self, discord_id: int):
        self.id: int = discord_id
        self.name: str = "cli_user"
        self.display_name: str = "CLI User"
        self.mention: str = f"<@{discord_id}>"


class CLIMessage:
    def __init__(self, content: str, author: CLIUser, channel: CLIChannel):
        self.content: str = content
        self.author: CLIUser = author
        self.channel: CLIChannel = channel
        self.mentions: list[CLIUser] = []


# --- Setup ---

def init_db() -> None:
    db = sqlite3.connect("users.db")
    db.execute("CREATE TABLE IF NOT EXISTS users(discord_id TEXT, friend_code TEXT, maimai_name TEXT, maimai_rating INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS user_data_history(discord_id TEXT, timestamp INTEGER, maimai_name TEXT, maimai_rating INTEGER)")
    db.commit()
    db.close()


def register_commands() -> None:
    import pkgutil, importlib
    for _, name, _ in pkgutil.iter_modules(ceebboard.Commands.__path__):
        module = importlib.import_module(f"ceebboard.Commands.{name}")
        if not hasattr(module, "COMMAND_INFO"):
            continue
        validity = getattr(module, "check_validity", ceebboard.Commands.Command.no_arg_validity)
        ceebboard.Commands.Command.Command(
            module.COMMAND_INFO.identifiers,
            validity,
            module.exec_command,
            module.COMMAND_INFO.usage_string,
            module.COMMAND_INFO.description_string,
        )


def parse_cli_args(argv: list[str]) -> tuple[list[str], int]:
    """Returns (command_args, discord_id). Extracts --as from argv."""
    discord_id = 0
    args = argv[1:]  # skip script name
    if "--as" in args:
        idx = args.index("--as")
        if idx + 1 < len(args):
            discord_id = int(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        else:
            print("--as requires a discord ID argument")
            sys.exit(1)
    return args, discord_id


async def run(command_args: list[str], discord_id: int) -> None:
    if not command_args:
        print("Usage: uv run python cli.py <command> [args...] [--as <discord_id>]")
        return

    init_db()
    register_commands()

    content = Command.command_prefix + " ".join(command_args)
    author = CLIUser(discord_id)
    channel = CLIChannel()
    message = CLIMessage(content, author, channel)

    current_command = await Command.message_to_command(message)
    if current_command is None:
        print(f"Unknown command: {command_args[0]}")
        print(f"Try: uv run python cli.py help")
        return

    args = content[len(Command.command_prefix):].split(" ")

    try:
        is_valid = await current_command.validity_check_func(message, args)
        if not is_valid:
            print(f"Invalid usage. Usage: {current_command.usage_string}")
            return
        await current_command.execution_func(message, args)
    except RuntimeError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    command_args, discord_id = parse_cli_args(sys.argv)
    asyncio.run(run(command_args, discord_id))
