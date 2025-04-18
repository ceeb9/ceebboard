import discord
import sqlite3
import json
from ceebboard.commands import register_commands
from ceebboard.bot import CeebboardClient

def startup():
    intents = discord.Intents.default()
    intents.message_content = True
    client = CeebboardClient(intents=intents)
    register_commands()

    # initialize database
    print("Initializing database...")
    db = sqlite3.connect("users.db")
    db.execute("CREATE TABLE IF NOT EXISTS users(discord_id TEXT, friend_code TEXT, maimai_name TEXT, maimai_rating INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS user_data_history(discord_id TEXT, timestamp INTEGER, maimai_name TEXT, maimai_rating INTEGER)")
    db.commit()
    db.close()

    # get credentials
    with open("config.json") as config_file:
        config = json.load(config_file)
        
    print("Starting event loop...")
    client.run(config["DEV_DISCORD_TOKEN"])
    #client.run(config["PRODUCTION_DISCORD_TOKEN"])

if __name__ == "__main__":
    startup()
