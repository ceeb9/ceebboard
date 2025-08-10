import json
import os
from playwright.async_api import async_playwright
from .session_store import REQUESTS_SESSION
from .logging import write_log_message, LogMessageLevel

class PlayerInfo():
    def __init__(self, username: str, rating: str):
        self.username = username
        self.rating = rating

friend_code_endpoint = "https://maimaidx-eng.com/maimai-mobile/friend/search/searchUser/?friendCode="
dxnet_home_url = "https://maimaidx-eng.com/maimai-mobile/"
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")

# reauthenticates the global session
async def reauthenticate_session():
    global REQUESTS_SESSION
    write_log_message("Getting persistent login cookie...", LogMessageLevel.INFO)

    # Load credentials
    with open(CONFIG_PATH, "r") as auth_file:
        config = json.load(auth_file)
        sega_username = config["SEGA_USERNAME"]
        sega_password = config["SEGA_PASSWORD"]

    async with async_playwright() as p:
        write_log_message("Logging into all-net...", LogMessageLevel.INFO)
        browser = await p.chromium.launch()
        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()

        await page.goto("https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=aimessen&redirect_url=https%3A%2F%2Fmy-aime.net%2Fen%2Flogin%2Fauth%2Fcauth&back_url=https%3A%2F%2Fmy-aime.net%2Fen", wait_until="load")

        await page.locator("#agree").first.set_checked(True)
        await page.locator(".c-button--openid--segaId").click()
        await page.wait_for_load_state("load")

        await page.locator("#sid").fill(sega_username)
        await page.locator("#password").fill(sega_password)
        await page.locator("#btnSubmit").click()
        await page.wait_for_url("https://my-aime.net/en")

        cookies = await context.cookies("https://lng-tgk-aime-gw.am-all.net/common_auth")

        for cur_cookie in cookies:
            REQUESTS_SESSION.cookies.set(
                cur_cookie["name"],
                cur_cookie["value"],
                domain=cur_cookie.get("domain"),
                path=cur_cookie.get("path", "/")
            )

        # Redirect from auth site (contains ssid cookie, sets cookie through header)
        response = REQUESTS_SESSION.head("https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=maimaidxex&redirect_url=https://maimaidx-eng.com/maimai-mobile/")
        if response.is_redirect:
            REQUESTS_SESSION.head(response.headers["Location"])
            write_log_message("Logged into all-net.", LogMessageLevel.INFO)
        else:
            raise Exception("Failed to get authenticated session.")

# get a playerinfo instance from a friend code 
async def get_info_from_friend_code(friend_code) -> PlayerInfo:
    global REQUESTS_SESSION
    response = REQUESTS_SESSION.get(friend_code_endpoint + friend_code)
    
    # login failure detection and reauth
    login_failure_codes = ["ERROR CODE：200004", "ERROR CODE：200002"]
    for login_failure_code in login_failure_codes:
        if login_failure_code in response.text:
            write_log_message(f"Couldn't get data from dxnet, reauthenticating... [{login_failure_code}]", LogMessageLevel.WARNING)
            await reauthenticate_session()
            response = REQUESTS_SESSION.get(friend_code_endpoint + friend_code)

    # check if we got the data we need, if so get it and return
    if (response.status_code == 200) and ("name_block" in response.text) and ("rating_block" in response.text):
        html = response.text
        result = PlayerInfo(get_div_contents(html, "name_block"), get_div_contents(html, "rating_block"))
        return result
    
    # otherwise determine what error to report back
    if response.status_code != 200: 
        write_log_message(f"Got non 200 status code. Can't access the maimai servers.", LogMessageLevel.ERROR)
        raise RuntimeError("Error accessing the maimai servers.")

    elif "ERROR CODE：" in response.text: 
        write_log_message(f"Got unknown error code in response text from dxnet. Servers probably offline", LogMessageLevel.ERROR)
        raise RuntimeError("Error querying the maimai server for data. DXNET likely offline.")
    elif "WRONG CODE" in response.text: 
        raise RuntimeError("Invalid friend code.")
    else: 
        write_log_message(f"Unknown error in response from dxnet. Status code 200, and no error code text.", LogMessageLevel.ERROR)
        raise RuntimeError("An unknown error occurred. I didn't plan for this one :(")

# get the contents of a div
def get_div_contents(html, search_term: str):
    start_index = html.index(search_term)
    end_index = start_index
    while html[start_index] != ">": start_index += 1
    while html[end_index] != "<": end_index += 1
    return html[start_index+1:end_index]