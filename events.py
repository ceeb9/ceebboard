import discord
import asyncio
from commands import Command
from display import display_error

async def on_ready():
    print("Ready!")

async def on_message(message: discord.Message):
    if not message.content.startswith(Command.command_prefix): return
    
    args = message.content[len(Command.command_prefix):].split(" ")

    # get the command instance
    current_command = await Command.message_to_command(message)
    if current_command == None: 
        await display_error("Unknown command! Try `m>help` for a list of commands.", message.channel)
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