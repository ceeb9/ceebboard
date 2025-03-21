import discord
import events
import sqlite3
import time

def startup():
    # create client
    print("Creating client...")
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    # register events
    client.event(events.on_ready)
    client.event(events.on_message)
    client.setup_hook = events.update_users_scheduled

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
