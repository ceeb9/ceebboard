import discord
import aiosqlite
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("leaderboard", "lb"),
    usage_string = "leaderboard" ,
    description_string = "See a leaderboard of all registered users.",
    is_dev_command = False
)

# show a leaderboard of all registered users
async def exec_command(original_message: discord.Message, args):
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