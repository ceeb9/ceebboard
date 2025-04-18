import discord
from .Command import Command
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("help", "?"),
    usage_string = "help",
    description_string = "See all available commands.",
    is_dev_command = False
)

# display help
async def exec_command(original_message: discord.Message, args):
    help_embed = discord.Embed(
        title="Commands", 
        description="Arguments surrounded by <> are required, and arguments surrounded by [] are optional.", 
        color=discord.Color.blue()
        )
    
    for command in Command.IdentifierToCommandInstance.values():
        help_embed.add_field(name=f"`{Command.command_prefix}{command.usage_string}`", value=command.description, inline=False)
    await original_message.channel.send(embed=help_embed)