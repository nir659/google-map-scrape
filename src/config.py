"""
Single-source configuration: paths, browser settings, scroll behaviour,
retry policy, and Google Maps CSS selectors.

Everything that might need tweaking lives here.
"""

from pathlib import Path


# ── Project Paths ─────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"


# ── Browser ───────────────────────────────────────────────────────────────────

HEADLESS: bool = True
VIEWPORT_WIDTH: int = 1920
VIEWPORT_HEIGHT: int = 1080
LOCALE: str = "en-US"
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ── Timeouts (milliseconds for Playwright, seconds for sleep) ─────────────────

PAGE_LOAD_TIMEOUT: int = 30_000          # 30 s
NAVIGATION_TIMEOUT: int = 30_000         # 30 s
SEARCH_WAIT: float = 3.0                 # seconds after search submit

# ── Scroll behaviour ─────────────────────────────────────────────────────────

SCROLL_PAUSE_MIN: float = 1.5            # min random sleep (seconds)
SCROLL_PAUSE_MAX: float = 3.0            # max random sleep (seconds)
SCROLL_DISTANCE_MIN: int = 1000          # min mouse-wheel delta
SCROLL_DISTANCE_MAX: int = 3000          # max mouse-wheel delta
MAX_STALE_ATTEMPTS: int = 3              # unchanged count -> stop

# ── Retry / resilience ───────────────────────────────────────────────────────

MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 2.0          # exponential backoff base
RETRY_BACKOFF_MAX: float = 30.0          # cap wait time (seconds)

# ── Output ────────────────────────────────────────────────────────────────────

OUTPUT_DIR: Path = DATA_DIR
ENABLE_SCREENSHOTS: bool = True
DEFAULT_MAX_RESULTS: int = 50

# ── Google Maps selectors (CSS) ──────────────────────────────────────────────
#
#    When Google changes the UI, update these constants.
#    Every module reads from here – nothing is hard-coded elsewhere.

SEARCH_BOX: str = "input#searchboxinput"
SEARCH_BUTTON: str = "button#searchbox-searchbutton"
SIDEBAR_FEED: str = 'div[role="feed"]'
RESULT_CARD: str = 'a[href^="https://www.google.com/maps/place"]'
END_OF_LIST: str = "p.fontBodyMedium > span > span"
ACCEPT_COOKIES: str = 'button[aria-label="Accept all"]'

# ── Card detail selectors (children of the card container) ────────────────
WEBSITE_LINK: str = 'a[data-value="Website"]'
RATING_SPAN: str = 'span[role="img"]'       # aria-label contains "X.X stars"
