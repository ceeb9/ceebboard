import discord
from ..util import display_info, update_user
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("update",),
    usage_string = "update" ,
    description_string = "Update your username and rating.",
    is_dev_command = False
)

# update the issuing user's rating and username
async def exec_command(original_message: discord.Message, args):
    info = await update_user(original_message.author.id)
    
    await display_info(f"Updated info for maimai account {info.username}. Rating: {info.rating}.", original_message.channel)
    return