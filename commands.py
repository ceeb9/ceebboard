import discord
import aiosqlite
import time
from collections.abc import Callable
from display import display_info
from scraper import get_info_from_friend_code
from scraper import PlayerInfo

class Command():
    command_prefix = "cb>"
    Commands = {}
    def __init__(self, name: str, validity_check_func: Callable, execution_func: Callable, usage_string: str, description: str):
        self.name = name
        self.validity_check_func = validity_check_func
        self.execution_func = execution_func
        self.usage_string = usage_string
        self.description = description

        self.Commands[name] = self

def link_command_validity(original_message: discord.Message, args: list[str]) -> bool:
    if len(args) != 2: return False
    friend_code = args[1]
    if not friend_code.isdigit(): return False
    if not len(friend_code) == 13: return False
    return True

# link a maimai account for the first time
async def link_command_exec(original_message: discord.Message, args: list[str]):
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
        await db.commit()
    await display_info(f"Linked this discord account to maimai account {info.username}!", original_message.channel)
    return

# show a leaderboard of all registered users
async def leaderboard_command_exec(original_message: discord.Message, args):
    users = None
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT discord_id, maimai_name, maimai_rating FROM users ORDER BY maimai_rating DESC") as cursor:
            users = await cursor.fetchall()

    lb_text = ""
    for index, user_info in enumerate(users):
        userid = user_info[0]
        maimai_name = user_info[1]
        maimai_rating = user_info[2]

        lb_position_text = f"{' '*(2-len(str(index+1)))}{index+1}"
        rating_text = f"{' '*(5-len(str(maimai_rating)))}{maimai_rating}"
        maimai_name_text = f"{maimai_name}{'　'*(8-len(str(maimai_name)))}"
        lb_line_text = f"`{lb_position_text}` | `{rating_text}` | `{maimai_name_text}` | <@{userid}>"
        if userid == original_message.author.id:
            lb_line_text = f"**{lb_line_text}**"

        lb_text += (lb_line_text + "\n")

    leaderboard_embed = discord.Embed(title="Leaderboard", color=discord.Color.green(), description=lb_text)
    await original_message.channel.send(embed=leaderboard_embed)
    return

async def update_user(discord_id: int) -> PlayerInfo:
    # get the friend code of the user issuing the command from the db
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT friend_code FROM users WHERE discord_id={discord_id}") as cursor:
            row = await cursor.fetchone()
            if row == None or type(row) == tuple and len(row) == 0:
                raise RuntimeError("This discord account hasn't been linked to a maimai account yet!")
            
            friend_code = str(row[0])

        # get their actual info
        info = await get_info_from_friend_code(friend_code)

        # update historical data (if rating has changed)
        async with db.execute(f"SELECT maimai_rating FROM users WHERE discord_id={discord_id}") as cursor:
            row = await cursor.fetchone()
            if row == None or type(row) == tuple and len(row) == 0:
                raise RuntimeError("No historical data for this account. Not sure how you managed this")
            
            last_known_rating = row[0]
            if int(last_known_rating) != int(info.rating):
                await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (discord_id, round(time.time()), info.username, info.rating))

        # update current rating
        await db.execute("UPDATE users SET maimai_name = ?, maimai_rating = ? WHERE discord_id = ?", (info.username, info.rating, discord_id))
        await db.commit()
    
    print(f"Updated info for maimai account {info.username}. Rating: {info.rating}.")
    return info


# update the issuing user's rating and username
async def update_command_exec(original_message: discord.Message, args):
    info = await update_user(original_message.author.id)
    
    await display_info(f"Updated info for maimai account {info.username}. Rating: {info.rating}.", original_message.channel)
    return

# display help
async def help_command_exec(original_message: discord.Message, args):
    help_embed = discord.Embed(title="Commands", color=discord.Color.blue())
    for command in Command.Commands.values():
        help_embed.add_field(name=f"`{Command.command_prefix}{command.usage_string}`", value=command.description, inline=False)
    await original_message.channel.send(embed=help_embed)


Command("link", link_command_validity, link_command_exec, "link <friendcode>", "Link your discord account to the given friend code.")
Command("leaderboard", lambda a, b: True, leaderboard_command_exec, "leaderboard", "See a leaderboard of all registered users.")
Command("update", lambda a, b: True, update_command_exec, "update", "Update your username and rating.")
Command("help", lambda a, b: True, help_command_exec, "help", "See all available commands.")