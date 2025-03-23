import discord
import events
import aiosqlite
import sqlite3
import time
import commands
from discord.ext import tasks

@tasks.loop(minutes=30)
async def update_users_scheduled():
    print("Updating all users...")
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT discord_id FROM users") as cursor:
            rows = await cursor.fetchall()
            if rows == None:
                raise Exception("No data in users table!!!")
            
            for row in rows:
                await commands.update_user(row[0])

class CeebboardClient(discord.Client):
    async def setup_hook(self):
        update_users_scheduled.start()
    
def startup():
    # create client
    print("Creating client...")
    intents = discord.Intents.default()
    intents.message_content = True
    client = CeebboardClient(intents=intents)

    # register events
    client.event(events.on_ready)
    client.event(events.on_message)

    # register commands
    commands.register_commands()

    # read auth from disk
    print("Getting authentication values from disk...")
    prod_bot_token = ""
    dev_bot_token = ""
    with open("auth.txt", "r") as file:
        lines = file.readlines()
        prod_bot_token = lines[0].split("::::")[1]
        dev_bot_token = lines[1].split("::::")[1]

    # initialize database
    print("Initializing database...")
    db = sqlite3.connect("users.db")
    db.execute("CREATE TABLE IF NOT EXISTS users(discord_id TEXT, friend_code TEXT, maimai_name TEXT, maimai_rating INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS user_data_history(discord_id TEXT, timestamp INTEGER, maimai_name TEXT, maimai_rating INTEGER)")
    db.commit()
    db.close()

    # run
    print("Starting event loop...")
    #client.run(prod_bot_token)
    client.run(dev_bot_token)

if __name__ == "__main__":
    startup()
