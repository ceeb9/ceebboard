import discord, os, io, aiosqlite
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from types import SimpleNamespace
from ..util import display_error
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("graph",),
    usage_string = "graph [@another_user]",
    description_string = "See a graph of a user's rating over time. If you don't ping another user, it'll show you your graph.",
    is_dev_command = False
)

async def check_validity(original_message: discord.Message, args):
    if len(args) == 1:
        return True
    elif len(args) == 2 and len(original_message.mentions) == 1:
        return True
    elif len(args) == 2 and len(original_message.mentions) == 0 and args[1].isdigit():
        return True
    return False

# show a graph of rating changes
async def exec_command(original_message: discord.Message, args):
    MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    BACKGROUND_IMAGE_PATH = os.path.join(MODULE_PATH, "../resources/bg.png")
    DEFAULT_FONT_PATH = os.path.join(MODULE_PATH, "../resources/CreatoDisplay-Regular.otf")
    BEST_FONT_PATH = os.path.join(MODULE_PATH, "../resources/TTRoundsNeueExtraBold.ttf")
    TITLE_FONT_PATH = os.path.join(MODULE_PATH, "../resources/MaruGothicDB.ttf")
    
    id_to_query = original_message.author.id
    if len(original_message.mentions) == 1:
        id_to_query = original_message.mentions[0].id
        
    if len(args) == 2 and len(original_message.mentions) == 0:
        id_to_query = args[1]

    async with aiosqlite.connect("users.db") as db:
        async with db.execute(f"SELECT timestamp, maimai_rating, maimai_name, (SELECT COUNT() from user_data_history WHERE discord_id={id_to_query}) AS count FROM user_data_history WHERE discord_id={id_to_query} ORDER BY timestamp ASC") as cursor:
            rows = await cursor.fetchall()
            if rows == None or (type(rows) == list and len(rows) == 0):
                raise RuntimeError("This discord account hasn't been linked to a maimai account yet!")
            
            maimai_name = ""
            
            # AGGREGATE RATING DATA INTO DAYS
            
            daily_player_info = []
            first_rating = 0
            for i, row in enumerate(rows):
                # Row doesn't define getitem so do stuff we only need to do once here
                if i == 0:
                    first_rating = row[1]
                if row[3] == 1:
                    await display_error("Graphing isn't working for users with only 1 day of tracking history right now. Try again later!", original_message.channel)
                    return
                
                maimai_name = row[2]
                
                todays_player_info = SimpleNamespace(date=datetime.fromtimestamp(row[0]).date(), rating=row[1])
    
                # make a new day in daily player info if timestamp dictates
                if (len(daily_player_info) == 0) or (daily_player_info[-1].date != todays_player_info.date):
                    daily_player_info.append(todays_player_info)
                    
                # update today's rating to a higher value if found
                elif (daily_player_info[-1].date == todays_player_info.date) and daily_player_info[-1].rating < todays_player_info.rating:
                    daily_player_info[-1].rating = todays_player_info.rating
                else:
                    raise RuntimeError("Something went wrong when aggregating rating data")
                
            lowest_rating = 20000
            highest_rating = -1
            # find highest and lowest rating (resolution of value at the end of each day)
            for todays_player_info in daily_player_info:
                if todays_player_info.rating < lowest_rating: lowest_rating = todays_player_info.rating
                if todays_player_info.rating > highest_rating: highest_rating = todays_player_info.rating
                
                
            # add datapoint for today if last day of data isn't today
            if daily_player_info[-1].date != datetime.today().date():
                daily_player_info.append(SimpleNamespace(date=datetime.today().date(), rating=daily_player_info[-1].rating))
                
            # SETUP IMAGE
            # note that the constants for smoothing the data points have been tested 
            # assuming 800x600. if you change this, make sure to adjust the smoothing constants accordingly
            BORDER_PADDING = 90
            GRAPH_PADDING = 100
            GRAPH_WIDTH = 800
            GRAPH_HEIGHT = 600
            DOT_RADIUS = 3
            GRAPH_LINE_WIDTH = 2
            
            img = Image.new("RGB", (GRAPH_WIDTH, GRAPH_HEIGHT), "white")
            draw = ImageDraw.Draw(img)
            
            # add background
            bg_image = Image.open(BACKGROUND_IMAGE_PATH)
            bg_resized = bg_image.resize(img.size)
            img.paste(bg_resized, (0,0))
            
            # get image scaling factors
            days_in_graph = (datetime.today().date() - daily_player_info[0].date).days
            x_per_day: float = float(GRAPH_WIDTH - (GRAPH_PADDING * 2))/float(days_in_graph)
            rating_delta = highest_rating - lowest_rating
            if rating_delta == 0:
                await display_error("Graphing isn't working for users who haven't gained rating since they started tracking yet. Go get some rating!", original_message.channel)
                return
            
            y_per_rating: float = float(GRAPH_HEIGHT - (GRAPH_PADDING * 2))/float(rating_delta)
            
            x_pos = lambda datapoint: ((days_in_graph - (datetime.today().date() - datapoint.date).days) * x_per_day) + GRAPH_PADDING
            y_pos = lambda datapoint: GRAPH_HEIGHT - (((datapoint.rating - lowest_rating) * y_per_rating) + GRAPH_PADDING)
            
            # RENDER GRAPH
            # iterate over all data points to be rendered (draw the actual graph)
            for index in range(len(daily_player_info) - 1):
                cur_x = x_pos(daily_player_info[index])
                cur_y = y_pos(daily_player_info[index])
                next_x = x_pos(daily_player_info[index+1])
                next_y = y_pos(daily_player_info[index+1])
                
                draw.ellipse((cur_x - DOT_RADIUS, cur_y - DOT_RADIUS, cur_x + DOT_RADIUS, cur_y + DOT_RADIUS), fill="black")
                
                # handle the case where you gain rating on your first day of tracking
                if index == 0 and first_rating != daily_player_info[0].rating:
                    original_datapoint = SimpleNamespace(date=daily_player_info[0].date, rating=first_rating)
                    original_x = x_pos(original_datapoint)
                    original_y = y_pos(original_datapoint)
                    draw.ellipse((original_x - DOT_RADIUS, original_y - DOT_RADIUS, original_x + DOT_RADIUS, original_y + DOT_RADIUS), fill="black")
                    draw.line((original_x, original_y, cur_x, cur_y), fill="black", width=GRAPH_LINE_WIDTH)
                
                # draw the lines connecting points of the graph
                if next_x - cur_x < 15:
                    # go directly from one point to another if close
                    draw.line((cur_x, cur_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                else:
                    # catching the case where rating goes down (on a new version)
                    if next_y > cur_y:
                        draw.line((cur_x, cur_y, next_x - 15, cur_y), fill="black", width=GRAPH_LINE_WIDTH)
                        draw.line((next_x - 15, cur_y, next_x - 10, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                        draw.line((next_x - 10, next_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                        print("here")
                    else:
                        # draw gradual slope when increasing
                        offset = int(((cur_y - next_y) / 100) * 10)
                        draw.line((cur_x, cur_y, next_x + offset, cur_y), fill="black", width=GRAPH_LINE_WIDTH)
                        draw.line((next_x + offset, cur_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                
                # make sure to draw the ellipse of the last datapoint too
                if index+1 == len(daily_player_info) - 1:
                    draw.ellipse((next_x - DOT_RADIUS, next_y - DOT_RADIUS, next_x + DOT_RADIUS, next_y + DOT_RADIUS), fill="black")
            
            # setup font (this is really ineffecient but whatever)
            font = ImageFont.truetype(DEFAULT_FONT_PATH, size=16)
            
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
            first_date_text = str(daily_player_info[0].date.strftime("%d/%m/%y"))
            first_date_text_width = font.getbbox(first_date_text)[2]
            second_date_text = str(daily_player_info[-1].date.strftime("%d/%m/%y"))
            second_date_text_width = font.getbbox(second_date_text)[2]
            draw.text((GRAPH_PADDING - first_date_text_width//2, GRAPH_HEIGHT - BORDER_PADDING + 10), first_date_text, fill="black", font=font)
            draw.text((GRAPH_WIDTH - GRAPH_PADDING - second_date_text_width//2, GRAPH_HEIGHT - BORDER_PADDING + 10), second_date_text, fill="black", font=font)
            
            # get numbers of the days to draw gridlines for
            if days_in_graph < 3:
                gridlined_day_count = 0
            elif days_in_graph < 5:
                gridlined_day_count = 1
            elif days_in_graph < 10:
                gridlined_day_count = 2
            else:
                gridlined_day_count = 4
                
            # find index of date of highest gain
            highest_gain_date_index = 0
            highest_gain = 0
            last_rating = daily_player_info[0].rating
            for i in range(len(daily_player_info)):
                if daily_player_info[i].rating - last_rating > highest_gain:
                    highest_gain = daily_player_info[i].rating - last_rating
                    highest_gain_date_index = i
                last_rating = daily_player_info[i].rating
            highest_gain_day_num = (daily_player_info[highest_gain_date_index].date - daily_player_info[0].date).days
                
            # draw gridlines and date labels for some amount of days
            for i in range(gridlined_day_count):
                # find the actual days we should gridline
                day_num = round((days_in_graph / float(gridlined_day_count + 1)) * (i + 1))
                
                
                # draw the date labels
                date_text = (daily_player_info[0].date + timedelta(days=day_num)).strftime("%d/%m/%y")
                date_text_width = font.getbbox(date_text)[2]
                text_x = GRAPH_PADDING + (x_per_day * day_num) - (date_text_width//2)
                text_y = GRAPH_HEIGHT - BORDER_PADDING + 10
                draw.text((text_x, text_y), date_text, fill="black", font=font)
                
                # draw the gridlines
                line_x = GRAPH_PADDING + (x_per_day * day_num)
                draw.line((line_x, GRAPH_HEIGHT-BORDER_PADDING, line_x, BORDER_PADDING), width=1, fill=(0,0,0,16))
                
            # RENDER BEST DAY GRAPHICS
            # draw a date label and special gridline for the best day (most rating increase)            
            # draw the gridline, best! text and +rating text
            highest_gain_date_x = GRAPH_PADDING + (x_per_day * highest_gain_day_num)
            draw.line((highest_gain_date_x, GRAPH_HEIGHT-BORDER_PADDING, highest_gain_date_x, BORDER_PADDING), width=5, fill=(250,214,67,255))
            best_font = ImageFont.truetype(BEST_FONT_PATH, size=16)
            best_text_y = GRAPH_HEIGHT - BORDER_PADDING + 10 + best_font.getbbox("!")[3]
            draw.text((highest_gain_date_x - (best_font.getbbox("BEST!")[2]//2), best_text_y), "BEST!", stroke_width=1, stroke_fill="black", font=best_font, fill=(250,214,67,255))
            draw.text((highest_gain_date_x - (best_font.getbbox("+"+str(highest_gain))[2]//2), best_text_y + best_font.getbbox("!")[3]), "+"+str(highest_gain), stroke_width=1, stroke_fill="black", font=best_font, fill=(250,214,67,255))
            
            # draw the date label for the best day (if not aligned with a date that already has a label)
            if not (highest_gain_day_num == 0 or highest_gain_day_num == days_in_graph or highest_gain_day_num == round((days_in_graph / float(gridlined_day_count + 1)))):
                date_text = daily_player_info[highest_gain_date_index].date.strftime("%d/%m/%y")
                date_text_width = font.getbbox(date_text)[2]
                text_x = GRAPH_PADDING + (x_per_day * highest_gain_day_num) - (date_text_width//2)
                text_y = GRAPH_HEIGHT - BORDER_PADDING + 62
                draw.text((text_x, text_y), date_text, fill="black", font=font)  
              
            # RENDER BORDERS
            draw.line((BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING, BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
            draw.line((BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
            draw.line((GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH-BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING), fill="black", width=3)
            draw.line((GRAPH_WIDTH-BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING, BORDER_PADDING, GRAPH_HEIGHT-BORDER_PADDING), fill="black", width=3)
            
            # RENDER TITLE
            title_font = ImageFont.truetype(TITLE_FONT_PATH, size=32)
            title_text = f"Rating Graph for {maimai_name}:"
            title_text_height = title_font.getbbox(title_text)[3]
            draw.text((BORDER_PADDING + 10, (BORDER_PADDING//2) - (title_text_height//2) - 4), title_text, font=title_font, fill="black")
                
            # save the image and send it
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            await original_message.channel.send(file=discord.File(fp=img_bytes, filename='graph.png'))
