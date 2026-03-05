from __future__ import annotations
import discord, os, io, aiosqlite
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from types import SimpleNamespace
from ..util import display_error
from .Command import CommandInfo

COMMAND_INFO = CommandInfo(
    identifiers = ("graph",),
    usage_string = "graph [@user] [days]",
    description_string = "See a graph of a user's rating over time. Default shows last 30 days. Use -1 for full history.",
    is_dev_command = False
)

# layout constants
BORDER_PADDING = 90
GRAPH_PADDING = 100
GRAPH_WIDTH = 800
GRAPH_HEIGHT = 600
DOT_RADIUS = 3
GRAPH_LINE_WIDTH = 2
DEFAULT_CUTOFF_DAYS = 30

# resource paths and fonts (loaded once at import)
_MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
_BACKGROUND_IMAGE_PATH = os.path.join(_MODULE_PATH, "../resources/bg.png")
_DEFAULT_FONT = ImageFont.truetype(os.path.join(_MODULE_PATH, "../resources/CreatoDisplay-Regular.otf"), size=16)
_BEST_FONT = ImageFont.truetype(os.path.join(_MODULE_PATH, "../resources/TTRoundsNeueExtraBold.ttf"), size=16)
_TITLE_FONT = ImageFont.truetype(os.path.join(_MODULE_PATH, "../resources/MaruGothicDB.ttf"), size=32)


def _is_discord_id(s: str) -> bool:
    return s.isdigit() and len(s) >= 15


def _parse_args(message: discord.Message, args: list[str]) -> tuple[int | str, int]:
    """Returns (discord_id, cutoff_days)."""
    target_id: int | str = message.author.id
    cutoff_days: int = DEFAULT_CUTOFF_DAYS

    if len(message.mentions) == 1:
        target_id = message.mentions[0].id

    remaining = [a for a in args[1:] if not a.startswith("<@")]

    for token in remaining:
        if _is_discord_id(token):
            target_id = token
        else:
            cutoff_days = int(token)

    return target_id, cutoff_days


async def _fetch_rating_history(discord_id: int | str) -> tuple[list[SimpleNamespace], int, str]:
    """Query DB and aggregate into daily values. Returns (daily_player_info, first_rating, maimai_name)."""
    async with aiosqlite.connect("users.db") as db:
        async with db.execute(
            "SELECT timestamp, maimai_rating, maimai_name, "
            "(SELECT COUNT() from user_data_history WHERE discord_id=?) AS count "
            "FROM user_data_history WHERE discord_id=? ORDER BY timestamp ASC",
            (discord_id, discord_id)
        ) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                raise RuntimeError("This discord account hasn't been linked to a maimai account yet!")
            rows = list(rows)

    if rows[0][3] <= 1:
        return [], rows[0][1], rows[-1][2]

    first_rating: int = rows[0][1]
    maimai_name: str = rows[-1][2]

    daily_player_info: list[SimpleNamespace] = []
    for row in rows:
        info = SimpleNamespace(date=datetime.fromtimestamp(row[0]).date(), rating=row[1])
        if not daily_player_info or daily_player_info[-1].date != info.date:
            daily_player_info.append(info)
        elif daily_player_info[-1].rating != info.rating:
            daily_player_info[-1].rating = info.rating

    return daily_player_info, first_rating, maimai_name


def _apply_cutoff(daily_player_info: list[SimpleNamespace], first_rating: int, cutoff_days: int) -> tuple[list[SimpleNamespace], int]:
    """Filter to cutoff window, prepend synthetic point if needed. Returns (filtered_info, adjusted_first_rating)."""
    if cutoff_days < 0:
        return daily_player_info, first_rating

    cutoff_date = datetime.today().date() - timedelta(days=cutoff_days)

    # find the last known rating before the cutoff window
    pre_window_rating: int = first_rating
    for info in daily_player_info:
        if info.date < cutoff_date:
            pre_window_rating = info.rating
        else:
            break

    filtered = [info for info in daily_player_info if info.date >= cutoff_date]

    # prepend synthetic start point if no data exactly on cutoff_date
    if not filtered or filtered[0].date != cutoff_date:
        filtered.insert(0, SimpleNamespace(date=cutoff_date, rating=pre_window_rating))

    return filtered, filtered[0].rating


def _find_best_day(daily_player_info: list[SimpleNamespace]) -> tuple[int, int]:
    """Returns (best_day_index, highest_gain)."""
    best_index: int = 0
    highest_gain: int = 0
    last_rating: int = daily_player_info[0].rating
    for i in range(len(daily_player_info)):
        gain = daily_player_info[i].rating - last_rating
        if gain > highest_gain:
            highest_gain = gain
            best_index = i
        last_rating = daily_player_info[i].rating
    return best_index, highest_gain


def _render_graph_line(draw: ImageDraw.ImageDraw, daily_player_info: list[SimpleNamespace], first_rating: int,
                       x_pos, y_pos) -> None:
    for index in range(len(daily_player_info) - 1):
        cur_x = x_pos(daily_player_info[index])
        cur_y = y_pos(daily_player_info[index])
        next_x = x_pos(daily_player_info[index + 1])
        next_y = y_pos(daily_player_info[index + 1])

        draw.ellipse((cur_x - DOT_RADIUS, cur_y - DOT_RADIUS, cur_x + DOT_RADIUS, cur_y + DOT_RADIUS), fill="black")

        # handle the case where you gain rating on your first day of tracking
        if index == 0 and first_rating != daily_player_info[0].rating:
            original_datapoint = SimpleNamespace(date=daily_player_info[0].date, rating=first_rating)
            original_x = x_pos(original_datapoint)
            original_y = y_pos(original_datapoint)
            draw.ellipse((original_x - DOT_RADIUS, original_y - DOT_RADIUS, original_x + DOT_RADIUS, original_y + DOT_RADIUS), fill="black")
            draw.line((original_x, original_y, cur_x, cur_y), fill="black", width=GRAPH_LINE_WIDTH)

        if next_x - cur_x < 15:
            draw.line((cur_x, cur_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
        else:
            if next_y > cur_y:
                draw.line((cur_x, cur_y, next_x - 15, cur_y), fill="black", width=GRAPH_LINE_WIDTH)
                draw.line((next_x - 15, cur_y, next_x - 10, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                draw.line((next_x - 10, next_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
            else:
                offset = int(((cur_y - next_y) / 100) * 10)
                if next_x - offset > cur_x:
                    draw.line((cur_x, cur_y, next_x - offset, cur_y), fill="black", width=GRAPH_LINE_WIDTH)
                    draw.line((next_x - offset, cur_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)
                else:
                    draw.line((cur_x, cur_y, next_x, next_y), fill="black", width=GRAPH_LINE_WIDTH)

        if index + 1 == len(daily_player_info) - 1:
            draw.ellipse((next_x - DOT_RADIUS, next_y - DOT_RADIUS, next_x + DOT_RADIUS, next_y + DOT_RADIUS), fill="black")


def _render_rating_axis(draw: ImageDraw.ImageDraw, lowest_rating: int, rating_delta: int, y_per_rating: float) -> None:
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

    rating_step = float(rating_delta) / float(rating_gridline_count - 1) if rating_gridline_count > 1 else 0

    for i in range(rating_gridline_count):
        current_gridline_rating = rating_step * i
        current_gridline_y = GRAPH_HEIGHT - (GRAPH_PADDING + current_gridline_rating * y_per_rating)

        text = str(int(lowest_rating + current_gridline_rating))
        text_width = _DEFAULT_FONT.getbbox(text)[2]
        text_height = _DEFAULT_FONT.getbbox(text)[3]
        draw.text((BORDER_PADDING - text_width - 9, current_gridline_y - text_height // 2), text, fill="black", font=_DEFAULT_FONT)

        if i != 0 and i != rating_gridline_count - 1:
            draw.line((BORDER_PADDING, current_gridline_y, GRAPH_WIDTH - BORDER_PADDING, current_gridline_y), width=1, fill="black")


def _render_date_axis(draw: ImageDraw.ImageDraw, daily_player_info: list[SimpleNamespace],
                      days_in_graph: int, x_per_day: float) -> int:
    """Returns gridlined_day_count for use by best day rendering."""
    first_date_text = daily_player_info[0].date.strftime("%d/%m/%y")
    first_date_text_width = _DEFAULT_FONT.getbbox(first_date_text)[2]
    second_date_text = daily_player_info[-1].date.strftime("%d/%m/%y")
    second_date_text_width = _DEFAULT_FONT.getbbox(second_date_text)[2]
    draw.text((GRAPH_PADDING - first_date_text_width // 2, GRAPH_HEIGHT - BORDER_PADDING + 10), first_date_text, fill="black", font=_DEFAULT_FONT)
    draw.text((GRAPH_WIDTH - GRAPH_PADDING - second_date_text_width // 2, GRAPH_HEIGHT - BORDER_PADDING + 10), second_date_text, fill="black", font=_DEFAULT_FONT)

    if days_in_graph < 3:
        gridlined_day_count = 0
    elif days_in_graph < 5:
        gridlined_day_count = 1
    elif days_in_graph < 10:
        gridlined_day_count = 2
    else:
        gridlined_day_count = 4

    for i in range(gridlined_day_count):
        day_num = round((days_in_graph / float(gridlined_day_count + 1)) * (i + 1))
        date_text = (daily_player_info[0].date + timedelta(days=day_num)).strftime("%d/%m/%y")
        date_text_width = _DEFAULT_FONT.getbbox(date_text)[2]
        text_x = GRAPH_PADDING + (x_per_day * day_num) - (date_text_width // 2)
        text_y = GRAPH_HEIGHT - BORDER_PADDING + 10
        draw.text((text_x, text_y), date_text, fill="black", font=_DEFAULT_FONT)

        line_x = GRAPH_PADDING + (x_per_day * day_num)
        draw.line((line_x, GRAPH_HEIGHT - BORDER_PADDING, line_x, BORDER_PADDING), width=1, fill=(0, 0, 0, 16))

    return gridlined_day_count


def _render_best_day(draw: ImageDraw.ImageDraw, best_day_index: int, highest_gain: int,
                     daily_player_info: list[SimpleNamespace], days_in_graph: int,
                     x_per_day: float, gridlined_day_count: int) -> None:
    best_day_num = (daily_player_info[best_day_index].date - daily_player_info[0].date).days
    best_x = GRAPH_PADDING + (x_per_day * best_day_num)

    draw.line((best_x, GRAPH_HEIGHT - BORDER_PADDING, best_x, BORDER_PADDING), width=5, fill=(250, 214, 67, 255))
    best_text_y = GRAPH_HEIGHT - BORDER_PADDING + 10 + _BEST_FONT.getbbox("!")[3]
    draw.text((best_x - (_BEST_FONT.getbbox("BEST!")[2] // 2), best_text_y), "BEST!",
              stroke_width=1, stroke_fill="black", font=_BEST_FONT, fill=(250, 214, 67, 255))
    gain_text = "+" + str(highest_gain)
    draw.text((best_x - (_BEST_FONT.getbbox(gain_text)[2] // 2), best_text_y + _BEST_FONT.getbbox("!")[3]),
              gain_text, stroke_width=1, stroke_fill="black", font=_BEST_FONT, fill=(250, 214, 67, 255))

    # draw date label if not aligned with an existing label
    if not (best_day_num == 0 or best_day_num == days_in_graph or best_day_num == round((days_in_graph / float(gridlined_day_count + 1)))):
        date_text = daily_player_info[best_day_index].date.strftime("%d/%m/%y")
        date_text_width = _DEFAULT_FONT.getbbox(date_text)[2]
        text_x = GRAPH_PADDING + (x_per_day * best_day_num) - (date_text_width // 2)
        text_y = GRAPH_HEIGHT - BORDER_PADDING + 62
        draw.text((text_x, text_y), date_text, fill="black", font=_DEFAULT_FONT)


def _render_borders(draw: ImageDraw.ImageDraw) -> None:
    draw.line((BORDER_PADDING, GRAPH_HEIGHT - BORDER_PADDING, BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
    draw.line((BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING), fill="black", width=3)
    draw.line((GRAPH_WIDTH - BORDER_PADDING, BORDER_PADDING, GRAPH_WIDTH - BORDER_PADDING, GRAPH_HEIGHT - BORDER_PADDING), fill="black", width=3)
    draw.line((GRAPH_WIDTH - BORDER_PADDING, GRAPH_HEIGHT - BORDER_PADDING, BORDER_PADDING, GRAPH_HEIGHT - BORDER_PADDING), fill="black", width=3)


def _render_title(draw: ImageDraw.ImageDraw, maimai_name: str) -> None:
    title_text = f"Rating Graph for {maimai_name}:"
    title_text_height = _TITLE_FONT.getbbox(title_text)[3]
    draw.text((BORDER_PADDING + 10, (BORDER_PADDING // 2) - (title_text_height // 2) - 4), title_text, font=_TITLE_FONT, fill="black")


async def check_validity(original_message: discord.Message, args: list[str]) -> bool:
    if len(args) == 1:
        return True
    if len(args) == 2:
        # mention, discord ID, or cutoff
        if len(original_message.mentions) == 1:
            return True
        token = args[1]
        if _is_discord_id(token):
            return True
        try:
            int(token)
            return True
        except ValueError:
            return False
    if len(args) == 3:
        # (mention or discord ID) + cutoff
        has_target = len(original_message.mentions) == 1 or _is_discord_id(args[1])
        if not has_target:
            return False
        try:
            int(args[2])
            return True
        except ValueError:
            return False
    return False


# show a graph of rating changes
async def exec_command(original_message: discord.Message, args: list[str]) -> None:
    target_id, cutoff_days = _parse_args(original_message, args)

    daily_player_info, first_rating, maimai_name = await _fetch_rating_history(target_id)
    if not daily_player_info:
        await display_error("You'll need some more data for graphing to work. Try again later!", original_message.channel)
        return

    daily_player_info, first_rating = _apply_cutoff(daily_player_info, first_rating, cutoff_days)

    # add datapoint for today if last day of data isn't today
    if daily_player_info[-1].date != datetime.today().date():
        daily_player_info.append(SimpleNamespace(date=datetime.today().date(), rating=daily_player_info[-1].rating))

    # compute min/max/scaling
    lowest_rating = min(info.rating for info in daily_player_info)
    highest_rating = max(info.rating for info in daily_player_info)

    # include first_rating in bounds if it differs (for the synthetic start line)
    if first_rating < lowest_rating:
        lowest_rating = first_rating
    if first_rating > highest_rating:
        highest_rating = first_rating

    days_in_graph = (datetime.today().date() - daily_player_info[0].date).days
    if days_in_graph == 0:
        await display_error("Not enough data to graph yet. Try again tomorrow!", original_message.channel)
        return

    rating_delta = highest_rating - lowest_rating
    if rating_delta == 0:
        await display_error("Graphing isn't working for users who haven't gained rating since they started tracking yet. Go get some rating!", original_message.channel)
        return

    x_per_day: float = float(GRAPH_WIDTH - (GRAPH_PADDING * 2)) / float(days_in_graph)
    y_per_rating: float = float(GRAPH_HEIGHT - (GRAPH_PADDING * 2)) / float(rating_delta)

    x_pos = lambda dp: ((days_in_graph - (datetime.today().date() - dp.date).days) * x_per_day) + GRAPH_PADDING
    y_pos = lambda dp: GRAPH_HEIGHT - (((dp.rating - lowest_rating) * y_per_rating) + GRAPH_PADDING)

    # create image
    img = Image.new("RGB", (GRAPH_WIDTH, GRAPH_HEIGHT), "white")
    bg_image = Image.open(_BACKGROUND_IMAGE_PATH)
    img.paste(bg_image.resize(img.size), (0, 0))
    draw = ImageDraw.Draw(img)

    _render_graph_line(draw, daily_player_info, first_rating, x_pos, y_pos)
    _render_rating_axis(draw, lowest_rating, rating_delta, y_per_rating)
    gridlined_day_count = _render_date_axis(draw, daily_player_info, days_in_graph, x_per_day)

    best_day_index, highest_gain = _find_best_day(daily_player_info)
    if highest_gain > 0:
        _render_best_day(draw, best_day_index, highest_gain, daily_player_info, days_in_graph, x_per_day, gridlined_day_count)

    _render_borders(draw)
    _render_title(draw, maimai_name)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    await original_message.channel.send(file=discord.File(fp=img_bytes, filename='graph.png'))
