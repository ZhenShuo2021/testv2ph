# user preference
MIN_SCROLL_LENGTH = 1500
MAX_SCROLL_LENGTH = 4000
MIN_SCROLL_STEP = 50
MAX_SCROLL_STEP = 250
RATE_LIMIT = 400
DOWNLOAD_DIR = "download"
PROFILE_PATH = "chrome_profile"
ALBUM_LOG_FILE = "downloaded_albums.txt"
LOG_PATH = "./v2ph"

# url
BASE_URL = "https://www.v2ph.com"
ACTOR_URL = "https://www.v2ph.com/actor/Umi-Shinonome?page=2"
DEMO_URL_ALBUM = "https://www.v2ph.com/album/Weekly-Young-Jump-2015-No15"
DEMO_URL_ACTOR = "https://www.v2ph.com/actor/Mao-Imaizumi"
WORKFLOW_URL_ACTOR = (
    "https://www.v2ph.com/album/Weekly-Big-Comic-Spirits-2016-No22-23"  # only 1 page
)

# system
DRY_RUN_MSG = "[DRY RUN]"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.59 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
