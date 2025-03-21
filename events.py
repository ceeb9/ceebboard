import discord
import asyncio
import cProfile, pstats
from commands import Command
from display import display_error

async def on_ready():
    print("Ready!")

async def on_message(message: discord.Message):
    if not message.content.startswith(Command.command_prefix):
        return
    
    args = message.content[len(Command.command_prefix):].split(" ")
    command_identifier = args[0]

    # check if the command exists
    # check if alphanumeric first for security
    if not command_identifier.isalpha(): 
        current_command = "FAILED TO GET COMMAND"
    else:
        current_command = Command.Commands.get(command_identifier, "FAILED TO GET COMMAND")

    if current_command == "FAILED TO GET COMMAND":
        await display_error(f"Unknown command! `Try m>help` for a list of commands.", message.channel)
        return

    # do the actual command syntax checking and execution
    try:
        if asyncio.iscoroutinefunction(current_command.validity_check_func(message, args)):
            is_command_syntax_valid = await current_command.validity_check_func(message, args)
        else:
            is_command_syntax_valid = current_command.validity_check_func(message, args)
        
        if is_command_syntax_valid:
            await current_command.execution_func(message, args)

        else:
            await display_error(current_command.usage_string, message.channel)
    except RuntimeError as e:
        await display_error(str(e), message.channel)