import discord

# create and send an embed for an error
async def display_error(error_text: str, channel) -> None:
    error_embed = discord.Embed(color=discord.Color.red(), description=error_text)
    await channel.send(embed=error_embed)

# create and send an embed for info
async def display_info(info_text: str, channel) -> None:
    info_embed = discord.Embed(color=discord.Color.blue(), description=info_text)
    await channel.send(embed=info_embed)