"""Central configuration for the screener pipeline.

All data sources here are free and require no API key. Where a provider
asks for a descriptive contact (SEC's fair-access policy), set it via
environment variable rather than hardcoding a real identity in source.
"""
import os

# SEC requires a descriptive User-Agent identifying the requester for its
# free, no-key EDGAR APIs. Override with your own contact via env var.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "stocks-predictor-research-tool contact:set-SEC_USER_AGENT-env-var"
)

HTTP_USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; stocks-predictor-research-bot/1.0)",
)

REQUEST_TIMEOUT_SECONDS = 15

# Yahoo Finance predefined screener IDs used to discover candidate tickers
# beyond a fixed static list (so small/micro caps outside the S&P 500 can
# surface too).
YAHOO_SCREENER_IDS = [
    "day_gainers",
    "most_actives",
    "small_cap_gainers",
    "undervalued_growth_stocks",
    "growth_technology_stocks",
]
YAHOO_SCREENER_COUNT = 50  # tickers requested per screener

# Read-only, no-auth public JSON endpoints (old.reddit.com works without
# OAuth for public subreddit listings). This is best-effort: Reddit may
# rate-limit or block anonymous requests; add PRAW + API credentials later
# for reliability.
REDDIT_SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
REDDIT_POSTS_PER_SUBREDDIT = 100
REDDIT_REQUEST_DELAY_SECONDS = 2

# Google News RSS query template, no auth required.
NEWS_ARTICLES_PER_TICKER = 15

# Threaded fetching (see scraper/parallel.py): worker cap and per-host request
# rates. Politeness is governed by the rate limits, not the thread count.
PARALLEL_WORKERS = int(os.environ.get("PARALLEL_WORKERS", "8"))
NEWS_RATE_PER_SEC = 3.0
STOCKTWITS_RATE_PER_SEC = 2.0
WIKI_RATE_PER_SEC = 5.0

# Extra tickers to always include regardless of what screeners surface,
# one per line, '#' comments allowed.
WATCHLIST_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "watchlist.txt"
)

MAX_TICKERS_TO_SCORE = 120  # cap total universe size per run to keep runtime/API usage bounded

# Cap on how many tickers to archive daily closes for (today's universe plus
# previously-tracked names). Bounds API load while keeping forward-return
# labels available for names that have dropped off the hot list.
# Overridable via env for scaling runs.
MAX_PRICE_ARCHIVE_TICKERS = int(os.environ.get("MAX_PRICE_ARCHIVE_TICKERS", "500"))

# When "1", the daily price archive covers the FULL US market (~10k tickers
# from SEC company_tickers.json) rather than just screener + tracked names.
# This is the whole-market net needed to catch movers before they trend.
FULL_MARKET_ARCHIVE = os.environ.get("FULL_MARKET_ARCHIVE", "0") == "1"

# When "1", curated world-market tickers (data/markets/international.txt)
# join the tier-1 price archive: UK/DE/FR/NL/CH/JP/HK/AU/CA/IN/KR large caps.
# Prices+labels only -- the deep attention sources are US-only by nature.
INTERNATIONAL_ARCHIVE = os.environ.get("INTERNATIONAL_ARCHIVE", "1") == "1"

# Composite scoring weights. These are heuristic and not derived from any
# validated backtest -- tune based on your own evaluation.
SCORE_WEIGHTS = {
    "price_momentum": 0.25,
    "volume_spike": 0.15,
    "news_buzz": 0.12,
    "news_sentiment": 0.08,
    "reddit_buzz": 0.12,
    "reddit_sentiment": 0.05,
    "sec_activity": 0.05,
    "st_attention": 0.08,     # Stocktwits trending + message volume
    "wiki_attention": 0.05,   # Wikipedia pageview spike
    "short_pressure": 0.05,   # FINRA short-volume ratio
}

TOP_N_RESULTS = 25
