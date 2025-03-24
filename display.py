import discord

# create and send an embed for an error
async def display_error(error_text: str, channel, title: str="") -> None:
    error_embed = discord.Embed(color=discord.Color.red(), title=title, description=error_text)
    await channel.send(embed=error_embed)

# create and send an embed for info
async def display_info(info_text: str, channel, title: str="") -> None:
    info_embed = discord.Embed(color=discord.Color.blue(), title=title, description=info_text)
    await channel.send(embed=info_embed)