import discord
from discord.ext import tasks
import aiosqlite
from .Commands.Command import Command
from .util import display_error, update_user
from .logging import write_log_message, LogMessageLevel


# Updates all users in the database every 30 minutes.
@tasks.loop(minutes=30)
async def update_users_scheduled():
    write_log_message("Updating all users (30m timer)", LogMessageLevel.INFO)
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT discord_id FROM users") as cursor:
            rows = await cursor.fetchall()
            if rows == None:
                raise Exception("No data in users table!!!")
            
            for row in rows:
                try:
                    await update_user(row[0])
                except RuntimeError as e:
                    write_log_message(f"Error when trying to update user. {str(e)}", LogMessageLevel.ERROR)

class CeebboardClient(discord.Client):
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            if kwargs["OFFLINE_MODE"]:
                cls._is_offline = True
            else:
                cls._is_offline = False
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def setup_hook(self):
        # Start the automatic user update loop
        if self._is_offline:
            return
        update_users_scheduled.start()
        
    async def on_ready(self):
        write_log_message("Discord bot ready.", LogMessageLevel.INFO)

    # handle receiving messages and passing off execution to command handler
    async def on_message(self, message: discord.Message):
        
        # check if command
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
            