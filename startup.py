import discord
import sqlite3
import json
import pkgutil
import importlib
import ceebboard
import ceebboard.Commands.Command
from ceebboard.bot import CeebboardClient

DEV_MODE = False
# disables updating user info

def startup():    
    intents = discord.Intents.default()
    intents.message_content = True
    client = CeebboardClient(intents=intents, DEV_MODE=DEV_MODE)
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
    if DEV_MODE:
        client.run(config["DEV_DISCORD_TOKEN"])
    else:
        client.run(config["PRODUCTION_DISCORD_TOKEN"])
    
def register_commands():
    # register all commands
    
    # iterate through modules in the commands folder
    for _, name, _ in pkgutil.iter_modules(ceebboard.Commands.__path__):
        module = importlib.import_module(f"ceebboard.Commands.{name}")
        
        # create an instance of the command if the corresponding
        # module has a COMMAND_INFO attribute
        if hasattr(module, "COMMAND_INFO"):
            if not DEV_MODE and module.COMMAND_INFO.is_dev_command:
                continue
            
            if hasattr(module, "check_validity"):
                ceebboard.Commands.Command.Command(
                    module.COMMAND_INFO.identifiers,
                    module.check_validity,
                    module.exec_command,
                    module.COMMAND_INFO.usage_string,
                    module.COMMAND_INFO.description_string
                )
            else:
                ceebboard.Commands.Command.Command(
                    module.COMMAND_INFO.identifiers,
                    ceebboard.Commands.Command.no_arg_validity,
                    module.exec_command,
                    module.COMMAND_INFO.usage_string,
                    module.COMMAND_INFO.description_string
                )

if __name__ == "__main__":
    startup()
