import discord
import aiosqlite
import time
from ..scraper import get_info_from_friend_code
from ..util import display_info
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("link",),
    usage_string = "link <friendcode>",
    description_string = "Link your discord account to the given friend code.",
    is_dev_command = False
)

async def check_validity(original_message: discord.Message, args: list[str]) -> bool:
    if len(args) != 2: return False
    friend_code = args[1]
    if not friend_code.isdigit(): return False
    return True

# link a maimai account for the first time
async def exec_command(original_message: discord.Message, args: list[str]):
    friend_code = args[1]

    # make sure not already linked
    users_with_this_discord_id = 1
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT COUNT(*) FROM users WHERE discord_id={original_message.author.id}") as cursor:
            row = await cursor.fetchone()
            if row == None: raise RuntimeError("Something went wrong accessing the database!")

            users_with_this_discord_id = row[0]

    if users_with_this_discord_id > 0:
        raise RuntimeError("Someone has already linked this maimai account to a discord account!")

    # make sure its a valid friend code
    info = await get_info_from_friend_code(friend_code)

    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT INTO users VALUES(?, ?, ?, ?)", (original_message.author.id, friend_code, info.username, info.rating))
        await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (original_message.author.id, round(time.time()), info.username, info.rating))
        await db.commit()
    await display_info(f"Linked this discord account to maimai account {info.username}!", original_message.channel)
    return