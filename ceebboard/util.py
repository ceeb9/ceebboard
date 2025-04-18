import discord
import aiosqlite
import time
from .scraper import get_info_from_friend_code, PlayerInfo


# create and send an embed for an error
async def display_error(error_text: str, channel, title: str="") -> None:
    error_embed = discord.Embed(color=discord.Color.red(), title=title, description=error_text)
    await channel.send(embed=error_embed)

# create and send an embed for info
async def display_info(info_text: str, channel, title: str="") -> None:
    info_embed = discord.Embed(color=discord.Color.blue(), title=title, description=info_text)
    await channel.send(embed=info_embed)
    
# update the details of a user (name and rating). also create user_data_history entry if rating has changed
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
                print(f"Updated info for maimai account {info.username}. Rating: {int(last_known_rating)} --> {info.rating}.")
            else:
                print(f"Last known rating for {info.username} matches current rating. Not updating historical data.")

        # update current rating
        await db.execute("UPDATE users SET maimai_name = ?, maimai_rating = ? WHERE discord_id = ?", (info.username, info.rating, discord_id))
        await db.commit()
    
    return info