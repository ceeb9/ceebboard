import discord
from discord.ext import tasks
import aiosqlite
from .Commands.Command import Command
from .util import display_error, update_user

@tasks.loop(minutes=30)
async def update_users_scheduled():
    print("Updating all users...")
    # Updates all users in the database every 30 minutes.
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT discord_id FROM users") as cursor:
            rows = await cursor.fetchall()
            if rows == None:
                raise Exception("No data in users table!!!")
            
            for row in rows:
                try:
                    await update_user(row[0])
                except RuntimeError as e:
                    print(str(e))

class CeebboardClient(discord.Client):
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            if kwargs["DEV_MODE"]:
                cls._is_dev_mode = True
            else:
                cls._is_dev_mode = False
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def setup_hook(self):
        # Start the automatic user update loop
        if self._is_dev_mode:
            return
        update_users_scheduled.start()
        
    async def on_ready(self):
        print("Ready!")

    async def on_message(self, message: discord.Message):
        if not message.content.startswith(Command.command_prefix): return
        args = message.content[len(Command.command_prefix):].split(" ")

        # get the command instance
        current_command = await Command.message_to_command(message)
        if current_command is None: 
            await display_error(f"Unknown command! Try `{Command.command_prefix}help` for a list of commands.", message.channel)
            return

        try:
            # check if syntax of command is valid
            is_command_syntax_valid = await current_command.validity_check_func(message, args)
            if not is_command_syntax_valid:
                await display_error(f"Usage: {current_command.usage_string}", message.channel, title="Invalid Usage.")
                return
            
            # execute command
            await current_command.execution_func(message, args)
                
        except RuntimeError as e:
            await display_error(str(e), message.channel)
            