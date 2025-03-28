import discord
import aiosqlite
import time
import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime, timedelta
from collections.abc import Callable
from types import SimpleNamespace
from display import display_info, display_error
from scraper import get_info_from_friend_code, PlayerInfo

# update the details of a user (name and rating). also create user_data_history entry if rating has changed
async def update_user(discord_id: int) -> PlayerInfo:
    # get the friend code of the user issuing the command from the db
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT friend_code FROM users WHERE discord_id={discord_id}") as cursor:
            row = await cursor.fetchone()
            if row == None or type(row) == tuple and len(row) == 0:
                raise RuntimeError("This discord account hasn't been linked to a maimai account yet!")
            
            friend_code = str(row[0])

        # get their actual info
        info = await get_info_from_friend_code(friend_code)

        # update historical data (if rating has changed)
        async with db.execute(f"SELECT maimai_rating FROM users WHERE discord_id={discord_id}") as cursor:
            row = await cursor.fetchone()
            if row == None or type(row) == tuple and len(row) == 0:
                raise RuntimeError("No historical data for this account. Not sure how you managed this")
            
            last_known_rating = row[0]
            if int(last_known_rating) != int(info.rating):
                await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (discord_id, round(time.time()), info.username, info.rating))
                print(f"Updated info for maimai account {info.username}. Rating: {int(last_known_rating)} --> {info.rating}.")
            else:
                print(f"Last known rating for {info.username} matches current rating. Not updating historical data.")

        # update current rating
        await db.execute("UPDATE users SET maimai_name = ?, maimai_rating = ? WHERE discord_id = ?", (info.username, info.rating, discord_id))
        await db.commit()
    
    return info

class Command():
    command_prefix = "cb>"
    Commands = {}
    
    def __init__(self, name: str, validity_check_func: Callable, execution_func: Callable, usage_string: str, description: str):
        self.name = name
        self.validity_check_func = validity_check_func
        self.execution_func = execution_func
        self.usage_string = usage_string
        self.description = description

        self.Commands[name] = self

    # get a command instance given a message.
    # assumes the message starts with the command prefix and is *supposed* to be a command
    @staticmethod
    async def message_to_command(original_message: discord.Message) -> "Command | None":
        args = original_message.content[len(Command.command_prefix):].split(" ")
        command_identifier = args[0]

        if not command_identifier.isalpha(): current_command = None
        else: current_command = Command.Commands.get(command_identifier, None)

        return current_command

async def link_command_validity(original_message: discord.Message, args: list[str]) -> bool:
    if len(args) != 2: return False
    friend_code = args[1]
    if not friend_code.isdigit(): return False
    if not len(friend_code) == 13: return False
    return True

# link a maimai account for the first time
async def link_command_exec(original_message: discord.Message, args: list[str]):
    friend_code = args[1]

    # make sure not already linked
    users_with_this_discord_id = 1
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT COUNT(*) FROM users WHERE discord_id={original_message.author.id}") as cursor:
            row = await cursor.fetchone()
            if row == None: raise RuntimeError("Something went wrong accessing the database!")

            users_with_this_discord_id = row[0]

    if users_with_this_discord_id > 0:
        raise RuntimeError("Someone has already linked this maimai account to a discord account!")

    # make sure its a valid friend code
    info = await get_info_from_friend_code(friend_code)

    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT INTO users VALUES(?, ?, ?, ?)", (original_message.author.id, friend_code, info.username, info.rating))
        await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (original_message.author.id, round(time.time()), info.username, info.rating))
        await db.commit()
    await display_info(f"Linked this discord account to maimai account {info.username}!", original_message.channel)
    return

# show a leaderboard of all registered users
async def leaderboard_command_exec(original_message: discord.Message, args):
    users = None
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT discord_id, maimai_name, maimai_rating FROM users ORDER BY maimai_rating DESC") as cursor:
            users = await cursor.fetchall()

    lb_text = ""
    for index, user_info in enumerate(users):
        userid = user_info[0]
        maimai_name = user_info[1]
        maimai_rating = user_info[2]

        lb_position_text = f"{' '*(2-len(str(index+1)))}{index+1}"
        rating_text = f"{' '*(5-len(str(maimai_rating)))}{maimai_rating}"
        maimai_name_text = f"{maimai_name}{'　'*(8-len(str(maimai_name)))}"
        lb_line_text = f"`{lb_position_text}` | `{rating_text}` | `{maimai_name_text}` | <@{userid}>"
        if userid == original_message.author.id:
            lb_line_text = f"**{lb_line_text}**"

        lb_text += (lb_line_text + "\n")

    leaderboard_embed = discord.Embed(title="Leaderboard", color=discord.Color.green(), description=lb_text)
    await original_message.channel.send(embed=leaderboard_embed)
    return

# update the issuing user's rating and username
async def update_command_exec(original_message: discord.Message, args):
    info = await update_user(original_message.author.id)
    
    await display_info(f"Updated info for maimai account {info.username}. Rating: {info.rating}.", original_message.channel)
    return

async def graph_command_validity(original_message: discord.Message, args):
    if len(args) == 1:
        return True
    elif len(args) == 2 and len(original_message.mentions) == 1:
        return True
    return False

# show a graph of rating changes
async def graph_command_exec(original_message: discord.Message, args):
    id_to_query = original_message.author.id
    if len(original_message.mentions) == 1:
        id_to_query = original_message.mentions[0].id

    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT timestamp, maimai_rating, maimai_name FROM user_data_history WHERE discord_id={id_to_query} ORDER BY timestamp ASC") as cursor:
            rows = await cursor.fetchall()
            if rows == None or (type(rows) == list and len(rows) == 0):
                raise RuntimeError("This discord account hasn't been linked to a maimai account yet!")
            
            maimai_name = ""
            
            # AGGREGATE RATING DATA INTO DAYS
            lowest_rating = 20000
            highest_rating = -1
            dates_with_rating_gain = []
            for row in rows:
                maimai_name = row[2]
                date_and_rating_gain = SimpleNamespace(date=datetime.fromtimestamp(row[0]).date(), rating=row[1])
                
                # find highest rating
                if date_and_rating_gain.rating < lowest_rating: lowest_rating = date_and_rating_gain.rating
                if date_and_rating_gain.rating > highest_rating: highest_rating = date_and_rating_gain.rating
    
                # set new current day rating or make new day
                if (len(dates_with_rating_gain) == 0) or (dates_with_rating_gain[-1].date != date_and_rating_gain.date):
                    dates_with_rating_gain.append(date_and_rating_gain)
                elif (dates_with_rating_gain[-1].date == date_and_rating_gain.date) and dates_with_rating_gain[-1].rating < date_and_rating_gain.rating:
                    dates_with_rating_gain[-1].rating = date_and_rating_gain.rating
                else:
                    raise RuntimeError("Something went wrong when aggregating rating data")
                
            # add datapoint for today if last day of data isn't today
            if dates_with_rating_gain[-1].date != datetime.today().date():
                dates_with_rating_gain.append(SimpleNamespace(date=datetime.today().date(), rating=dates_with_rating_gain[-1].rating))
                
            # SETUP IMAGE
            # note that the constants for smoothing the data points have been tested 
            # assuming 800x600. if you change this, make sure to adjust the smoothing constants accordingly
            BORDER_PADDING = 90
            GRAPH_PADDING = 100
            GRAPH_WIDTH = 800
            GRAPH_HEIGHT = 600
            DOT_RADIUS = 3
            
            img = Image.new("RGB", (GRAPH_WIDTH, GRAPH_HEIGHT), "white")
            draw = ImageDraw.Draw(img)
            
            # add background
            bg_image = Image.open("resources/bg.png")
            bg_resized = bg_image.resize(img.size)
            img.paste(bg_resized, (0,0))
            
            # get image scaling factors
            days_in_graph = (datetime.today().date() - dates_with_rating_gain[0].date).days
            x_per_day: float = float(GRAPH_WIDTH - (GRAPH_PADDING * 2))/float(days_in_graph)
            rating_delta = highest_rating - lowest_rating
            y_per_rating: float = float(GRAPH_HEIGHT - (GRAPH_PADDING * 2))/float(rating_delta)
            
            x_pos = lambda datapoint: ((days_in_graph - (datetime.today().date() - datapoint.date).days) * x_per_day) + GRAPH_PADDING
            y_pos = lambda datapoint: GRAPH_HEIGHT - (((datapoint.rating - lowest_rating) * y_per_rating) + GRAPH_PADDING)
            
            # RENDER GRAPH
            # iterate over all data points to be rendered (draw the actual graph)
            for index in range(len(dates_with_rating_gain) - 1):
                cur_x = x_pos(dates_with_rating_gain[index])
                cur_y = y_pos(dates_with_rating_gain[index])
                next_x = x_pos(dates_with_rating_gain[index+1])
                next_y = y_pos(dates_with_rating_gain[index+1])
                
                draw.ellipse((cur_x - DOT_RADIUS, cur_y - DOT_RADIUS, cur_x + DOT_RADIUS, cur_y + DOT_RADIUS), fill="black")
                
                # smooth by going across then up if distance is more than 20
                if next_x - cur_x < 15:
                    draw.line((cur_x, cur_y, next_x, next_y), fill="black", width=3)
                else:
                    offset = int(((next_y - cur_y) / 100) * 10)
                    draw.line((cur_x, cur_y, next_x + offset, cur_y), fill="black", width=3)
                    draw.line((next_x + offset, cur_y, next_x, next_y), fill="black", width=3)
                
                # make sure to draw the ellipse of the last datapoint too
                if index+1 == len(dates_with_rating_gain) - 1:
                    draw.ellipse((next_x - DOT_RADIUS, next_y - DOT_RADIUS, next_x + DOT_RADIUS, next_y + DOT_RADIUS), fill="black")
            
            # setup font (this is really ineffecient but whatever)
            font_path = "resources/CreatoDisplay-Regular.otf"
            font = ImageFont.truetype(font_path, size=16)
            
            # RENDER RATING AXIS LABELS AND GRIDLINES
            # define the step and steps for each gridline
            # if increment is too low, dont draw any gridlines, just make the steps the min and max rating
            if rating_delta < 5:
                rating_gridline_count = 3
            elif rating_delta < 10:
                rating_gridline_count = 4
            elif rating_delta < 15:
                rating_gridline_count = 5
            elif rating_delta < 40:
                rating_gridline_count = 6
            else:
                rating_gridline_count = 8
                
            # now that we know how many gridlines we are going to draw, find where we will draw them
            if rating_gridline_count != 0:
                rating_step = float(rating_delta) / float(rating_gridline_count-1)
            else:
                rating_step = 0
                
            # count up to the amount of total gridlines
            for i in range(rating_gridline_count):
                # get the rating of the current gridline, and thus the y value
                current_gridline_rating = rating_step * i
                current_gridline_y_value = GRAPH_HEIGHT - (GRAPH_PADDING + current_gridline_rating * y_per_rating)
                
                # render the axis label and gridline at the correct y value
                text = str(int(lowest_rating + current_gridline_rating))
                text_width = font.getbbox(text)[2]
                text_height = font.getbbox(text)[3]
                draw.text((BORDER_PADDING - text_width - 9, current_gridline_y_value - text_height//2), text, fill="black", font=font)
                
                # only draw the gridline if not the first or last label
                if i != 0 and i != rating_gridline_count-1:
                    draw.line((BORDER_PADDING, current_gridline_y_value, GRAPH_WIDTH - BORDER_PADDING, current_gridline_y_value), width=1, fill="black")
                                    
            # RENDER DATE LABELS AND GRIDLINES
            first_date_text = str(dates_with_rating_gain[0].date.strftime("%d/%m/%y"))
            first_date_text_width = font.getbbox(first_date_text)[2]
            second_date_text = str(dates_with_rating_gain[-1].date.strftime("%d/%m/%y"))
            second_date_text_width = font.getbbox(second_date_text)[2]
            draw.text((GRAPH_PADDING - first_date_text_width//2, GRAPH_HEIGHT - BORDER_PADDING + 10), first_date_text, fill="black", font=font)
            draw.text((GRAPH_WIDTH - GRAPH_PADDING - second_date_text_width//2, GRAPH_HEIGHT - BORDER_PADDING + 10), second_date_text, fill="black", font=font)
            
            # get numbers of the days to draw gridlines for
            if days_in_graph < 3:
                gridlined_day_count = 0
            elif days_in_graph < 5:
                gridlined_day_count = 1
            elif days_in_graph < 10:
                gridlined_day_count = 3
            else:
                gridlined_day_count = 4
                
            # find index of date of highest gain
            highest_gain_date_index = 0
            highest_gain = 0
            last_rating = dates_with_rating_gain[0].rating
            for i in range(len(dates_with_rating_gain)):
                if dates_with_rating_gain[i].rating - last_rating > highest_gain:
                    highest_gain = dates_with_rating_gain[i].rating - last_rating
                    highest_gain_date_index = i
                last_rating = dates_with_rating_gain[i].rating
            highest_gain_day_num = (dates_with_rating_gain[highest_gain_date_index].date - dates_with_rating_gain[0].date).days
                
            # draw gridlines and date labels for some amount of days
            for i in range(gridlined_day_count):
                # find the actual days we should gridline
                day_num = round(float(float(days_in_graph)/float(gridlined_day_count)) * (i+1))
                if day_num == days_in_graph: day_num -= 1
                
                # skip the highest gain day, we will draw something special for it later
                if day_num == highest_gain_date_index: continue
                
                # draw the date labels
                date_text = (dates_with_rating_gain[0].date + timedelta(days=day_num)).strftime("%d/%m/%y")
                date_text_width = font.getbbox(date_text)[2]
                text_x = GRAPH_PADDING + (x_per_day * day_num) - (date_text_width//2)
                text_y = GRAPH_HEIGHT - BORDER_PADDING + 10
                draw.text((text_x, text_y), date_text, fill="black", font=font)
                
                # draw the gridlines
                line_x = GRAPH_PADDING + (x_per_day * day_num)
                draw.line((line_x, GRAPH_HEIGHT-BORDER_PADDING, line_x, BORDER_PADDING), width=1, fill=(0,0,0,16))
                
            # RENDER BEST DAY GRAPHICS
            # draw a date label and special gridline for the best day (most rating increase)
            date_text = dates_with_rating_gain[highest_gain_date_index].date.strftime("%d/%m/%y")
            date_text_width = font.getbbox(date_text)[2]
            text_x = GRAPH_PADDING + (x_per_day * highest_gain_day_num) - (date_text_width//2)
            text_y = GRAPH_HEIGHT - BORDER_PADDING + 10
            draw.text((text_x, text_y), date_text, fill="black", font=font)
            
            # draw the gridline, best! text and +rating text
            highest_gain_date_x = GRAPH_PADDING + (x_per_day * highest_gain_day_num)
            draw.line((highest_gain_date_x, GRAPH_HEIGHT-BORDER_PADDING, highest_gain_date_x, BORDER_PADDING), width=5, fill=(250,214,67,255))
            best_font = ImageFont.truetype("resources/TTRoundsNeueExtraBold.ttf", size=16)
            best_text_y = GRAPH_HEIGHT - BORDER_PADDING + 10 + best_font.getbbox("!")[3]
            draw.text((highest_gain_date_x - (best_font.getbbox("BEST!")[2]//2), best_text_y), "BEST!", stroke_width=1, stroke_fill="black", font=best_font, fill=(250,214,67,255))
            draw.text((highest_gain_date_x - (best_font.getbbox("+"+str(highest_gain))[2]//2), best_text_y + best_font.getbbox("!")[3]), "+"+str(highest_gain), stroke_width=1, stroke_fill="black", font=best_font, fill=(250,214,67,255))
                
            # RENDER BORDERS
            draw.line((BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING, BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
            draw.line((BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
            draw.line((GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH-BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING), fill="black", width=3)
            draw.line((GRAPH_WIDTH-BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING, BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING), fill="black", width=3)
            
            # RENDER TITLE
            title_font = ImageFont.truetype("resources/MaruGothicDB.ttf", size=32)
            title_text = f"Rating Graph for {maimai_name}:"
            title_text_height = title_font.getbbox(title_text)[3]
            draw.text((BORDER_PADDING + 10, (BORDER_PADDING//2) - (title_text_height//2) - 4), title_text, font=title_font, fill="black")
                
            # save the image and send it
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            await original_message.channel.send(file=discord.File(fp=img_bytes, filename='graph.png'))

# link other user (for testnig)
async def lou(original_message: discord.Message, args):
    link_id = args[2]
    friend_code = args[1]

    # make sure not already linked
    users_with_this_discord_id = 1
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT COUNT(*) FROM users WHERE discord_id={link_id}") as cursor:
            row = await cursor.fetchone()
            if row == None: raise RuntimeError("Something went wrong accessing the database!")

            users_with_this_discord_id = row[0]

    if users_with_this_discord_id > 0:
        raise RuntimeError("Someone has already linked this maimai account to a discord account!")

    # make sure its a valid friend code
    info = await get_info_from_friend_code(friend_code)

    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT INTO users VALUES(?, ?, ?, ?)", (link_id, friend_code, info.username, info.rating))
        await db.execute("INSERT INTO user_data_history VALUES(?, ?, ?, ?)", (link_id, round(time.time()), info.username, info.rating))
        await db.commit()
    await display_info(f"Linked <@{link_id}> to maimai account {info.username}!", original_message.channel)
    return

# display help
async def help_command_exec(original_message: discord.Message, args):
    help_embed = discord.Embed(title="Commands", color=discord.Color.blue())
    for command in Command.Commands.values():
        help_embed.add_field(name=f"`{Command.command_prefix}{command.usage_string}`", value=command.description, inline=False)
    await original_message.channel.send(embed=help_embed)
    
async def no_arg_validity(original_message: discord.Message, args):
    return True

def register_commands():
    Command("link", link_command_validity, link_command_exec, "link <friendcode>", "Link your discord account to the given friend code.")
    Command("leaderboard", no_arg_validity, leaderboard_command_exec, "leaderboard", "See a leaderboard of all registered users.")
    Command("update", no_arg_validity, update_command_exec, "update", "Update your username and rating.")
    #Command("lou", lambda a, b: True, lou, "lou", "DEV COMMAND - link another user")
    Command("graph", graph_command_validity, graph_command_exec, "graph", "See a graph of your rating over time.")
    Command("help", no_arg_validity, help_command_exec, "help", "See all available commands.")