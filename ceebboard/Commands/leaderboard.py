import discord
import aiosqlite
import time
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("leaderboard", "lb"),
    usage_string = "leaderboard" ,
    description_string = "See a leaderboard of all registered users.",
    is_dev_command = False
)

EMOJI_UP = "<:up_green:1479333946218254468>"
EMOJI_DOWN = "<:down_red:1479333926559420487>"
EMOJI_NEW = "<:plus_white:1479336807882817650>"
EMOJI_NEUTRAL = "<:minus_white:1479336825213419672>"

def _format_delta(current_pos: int, old_positions: dict[str, int], discord_id: str) -> str:
    if discord_id not in old_positions:
        return f"{EMOJI_NEW}`NEW`"
    delta = old_positions[discord_id] - current_pos
    if delta == 0:
        return f"{EMOJI_NEUTRAL}`---`"
    emoji = EMOJI_UP if delta > 0 else EMOJI_DOWN
    return f"{emoji}`{abs(delta):>2} `"


# show a leaderboard of all registered users
async def exec_command(original_message: discord.Message, args):
    users = None
    historical_ratings: dict[str, int] = {}
    cutoff = int(time.time()) - (30 * 86400)

    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT discord_id, maimai_name, maimai_rating FROM users ORDER BY maimai_rating DESC") as cursor:
            users = await cursor.fetchall()

        async with db.execute(
            """
            SELECT h.discord_id, h.maimai_rating
            FROM user_data_history h
            INNER JOIN (
                SELECT discord_id, MAX(timestamp) as max_ts
                FROM user_data_history
                WHERE timestamp <= ?
                GROUP BY discord_id
            ) latest ON h.discord_id = latest.discord_id AND h.timestamp = latest.max_ts
            """,
            (cutoff,)
        ) as cursor:
            async for row in cursor:
                historical_ratings[str(row[0])] = row[1]

    # build old positions by sorting historical ratings desc
    old_sorted = sorted(historical_ratings.items(), key=lambda x: x[1], reverse=True)
    old_positions: dict[str, int] = {uid: pos + 1 for pos, (uid, _) in enumerate(old_sorted)}

    lb_text = ""
    for index, user_info in enumerate(users):
        userid = user_info[0]
        maimai_name = user_info[1]
        maimai_rating = user_info[2]
        current_pos = index + 1

        lb_position_text = f"{' '*(2-len(str(current_pos)))}{current_pos}"
        delta_text = _format_delta(current_pos, old_positions, str(userid))
        rating_text = f"{' '*(5-len(str(maimai_rating)))}{maimai_rating}"
        maimai_name_text = f"{maimai_name}{'　'*(8-len(str(maimai_name)))}"
        lb_line_text = f"`{lb_position_text}` {delta_text} | `{rating_text}` | `{maimai_name_text}` | <@{userid}>"
        if userid == original_message.author.id:
            lb_line_text = f"**{lb_line_text}**"

        lb_text += (lb_line_text + "\n")

    leaderboard_embed = discord.Embed(title="Leaderboard", color=discord.Color.green(), description=lb_text)
    await original_message.channel.send(embed=leaderboard_embed)
    return
