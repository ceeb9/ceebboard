import requests
from playwright.sync_api import sync_playwright

class PlayerInfo():
    def __init__(self, username: str, rating: str):
        self.username = username
        self.rating = rating

friend_code_endpoint = "https://maimaidx-eng.com/maimai-mobile/friend/search/searchUser/?friendCode="
dxnet_home_url = "https://maimaidx-eng.com/maimai-mobile/"

def get_authenticated_session() -> requests.Session:
    print("Getting persistent login cookie...")
    with open("auth.txt", "r") as file:
        lines = file.readlines()
        sega_username = lines[2].split("::::")[1]
        sega_password = lines[3].split("::::")[1]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        print("Logging into all-net...")
        # login and get cookies
        page.goto("https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=aimessen&redirect_url=https%3A%2F%2Fmy-aime.net%2Fen%2Flogin%2Fauth%2Fcauth&back_url=https%3A%2F%2Fmy-aime.net%2Fen")
        page.locator(".c-button--openid--segaId").click()
        page.locator("#sid").fill(sega_username)
        page.locator("#password").fill(sega_password)
        page.locator("#btnSubmit").click()
        page.wait_for_url("https://my-aime.net/en")
        ck = context.cookies("https://lng-tgk-aime-gw.am-all.net/common_auth")

        # find the cookies we need and save them
        for cur_cookie in ck:
            if not "name" in cur_cookie or not "value" in cur_cookie:
                continue
            if cur_cookie["name"] == "clal": 
                browser.close()
                session = requests.Session()

                # set persistent login cookie
                session.cookies.set("clal", cur_cookie["value"], domain="lng-tgk-aime-gw.am-all.net", path="/common_auth")

                # get redirect from auth site (which contains ssid to authenticate session)
                response = session.head(f"https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=maimaidxex&redirect_url=https://maimaidx-eng.com/maimai-mobile/")

                # make a request to main site with ssid as param (authenticates session)
                if response.is_redirect: 
                    session.head(response.headers["Location"])
                    browser.close()
                    return session
                else:
                    raise Exception("Failed to get authenticated session (couldn't get ssid)")

            else: continue
        
        browser.close()
        raise Exception("Failed to get authenticated session (couldn't get clal cookie)")
    
# i hate putting this here and not in startup but i cant figure out module caching so here it goes
REQUESTS_SESSION = get_authenticated_session()

# get the contents of a div
def get_div_contents(html, search_term: str):
    start_index = html.index(search_term)
    end_index = start_index
    while html[start_index] != ">": start_index += 1
    while html[end_index] != "<": end_index += 1
    return html[start_index+1:end_index]

# get a playerinfo instance from a friend code 
async def get_info_from_friend_code(friend_code) -> PlayerInfo:
    global REQUESTS_SESSION
    response = REQUESTS_SESSION.get(friend_code_endpoint + friend_code)

    if "ERROR CODE：" in response.text:
        print("Couldn't get data, logging in again")
        #auth_response = REQUESTS_SESSION.head(dxnet_home_url, allow_redirects=True)
        with open("error.html", "w", encoding="utf-8") as file:
            file.write(response.text)
        REQUESTS_SESSION = get_authenticated_session()

    # check if we got the data we need, if so get it and return
    if (response.status_code == 200) and ("name_block" in response.text) and ("rating_block" in response.text):
        html = response.text
        result = PlayerInfo(get_div_contents(html, "name_block"), get_div_contents(html, "rating_block"))
        return result
    
    # otherwise determine what error to report back
    if response.status_code != 200: raise RuntimeError("Error accessing the maimai servers.")
    elif "ERROR CODE：" in response.text: 
        raise RuntimeError("Error querying the maimai server for data.")
    elif "WRONG CODE" in response.text: raise RuntimeError("Invalid friend code.")
    else: raise RuntimeError("An unknown error occurred. I didn't plan for this one :(")