import discord, aiosqlite, time
from ..util import display_info
from ..scraper import get_info_from_friend_code
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("linkotheruser", "lou"),
    usage_string = "linkotheruser <friend code> <discord id>",
    description_string = "Link a friend code to the discord id of a given user.",
    is_dev_command = True
)

# link other user (for testing)
async def exec_command(original_message: discord.Message, args):
    
    link_id = args[2]
    friend_code = args[1]

    # make sure not already linked
    users_with_this_discord_id = 1
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT COUNT(*) FROM users WHERE discord_id={link_id}") as cursor:
            row = await cursor.fetchone()
            if row == None: raise RuntimeError("Something went wrong accessing the database!")

            users_with_this_discord_id = row[0]

    if users_with_this_discord_id > 0:
        raise RuntimeError("Someone has already linked this maimai account to a discord account!")

    # make sure its a valid friend code
    info = await get_info_from_friend_code(friend_code)

    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT INTO users VALUES(?, ?, ?, ?)", (link_id, friend_code, info.username, info.rating))
        await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (link_id, round(time.time()), info.username, info.rating))
        await db.commit()
    await display_info(f"Linked <@{link_id}> to maimai account {info.username}!", original_message.channel)
    return