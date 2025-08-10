import discord
from collections.abc import Callable

class Command():
    command_prefix = "cb>"
    # class var storing ref to each command instance
    IdentifierToCommandInstance = {}
    
    def __init__(self, identifiers: tuple, validity_check_func: Callable, execution_func: Callable, usage_string: str, description: str):
        self.identifiers = identifiers
        self.validity_check_func = validity_check_func
        self.execution_func = execution_func
        self.usage_string = usage_string
        self.description = description

        for identifier in identifiers:
            self.IdentifierToCommandInstance[identifier] = self

    # get a command instance given a message.
    # assumes the message starts with the command prefix and is *supposed* to be a command
    @staticmethod
    async def message_to_command(original_message: discord.Message) -> "Command | None":
        args = original_message.content[len(Command.command_prefix):].split(" ")
        command_identifier = args[0]

        if not command_identifier.isalpha(): current_command = None
        else: current_command = Command.IdentifierToCommandInstance.get(command_identifier, None)

        return current_command

class CommandInfo():
    def __init__(self, identifiers: tuple, usage_string: str, description_string: str, is_dev_command: bool):
        self.identifiers = identifiers
        self.usage_string = usage_string
        self.description_string = description_string
        self.is_dev_command = is_dev_command

async def no_arg_validity(original_message: discord.Message, args):
    return True
