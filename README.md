# Google Maps Scraper

A Google Maps scraper built with **Playwright** and **Stealth** injection. Extracts business listings (name + link) from Google Maps search results with robust error handling, checkpointing, and retry logic.

## Features

- **Stealth browsing** -- Playwright + `playwright-stealth` v2 to bypass bot detection
- **Single-command CLI** -- Pass a query with `-q` and go
- **Infinite scroll engine** -- Randomised scroll behaviour that mimics a human
- **Checkpoint & resume** -- Interrupted scrapes can be resumed automatically
- **Retry with backoff** -- Exponential backoff on transient failures
- **Dual export** -- Saves results as both CSV and JSON
- **Extensible** -- Pydantic models ready for future detailed scraping (phone, email, etc.)

## Prerequisites

- Python 3.10+
- pip

## Installation

```bash
# 1. Clone the repository
git clone <repo-url> && cd google-map-scrape

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install the Chromium browser for Playwright
playwright install chromium
```

## Usage

```bash
# Basic usage
python -m src.main -q "plumbers in New York City"

# Set a custom result limit
python -m src.main -q "dentists in Los Angeles" --max-results 100

# Run in visible (headed) mode for debugging
python -m src.main -q "cafes in Chicago" --no-headless

# Custom output directory
python -m src.main -q "electricians in Miami" --output-dir ./results
```

### CLI Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-q` / `--query` | Yes | -- | Google Maps search query |
| `--max-results` | No | 50 | Maximum listings to scrape |
| `--no-headless` | No | false | Show the browser window |
| `--output-dir` | No | `data/` | Output directory for CSV/JSON |

### Output

Results are saved in the `data/` directory (or your custom `--output-dir`):

```
data/
  plumbers_in_new_york_city_leads.csv
  plumbers_in_new_york_city_leads.json
```

Each record contains:

| Column | Description |
|---|---|
| `name` | Business name |
| `link` | Google Maps URL for the listing |
| `query_source` | The query that produced this result |
| `scraped_at` | UTC timestamp of scraping |

## Configuration

All settings live in a single file: `src/config.py`. This includes:

- **Browser settings** -- headless mode, viewport, user agent, locale
- **Scroll behaviour** -- pause ranges, scroll distances, stale detection
- **Retry policy** -- max retries, backoff base/cap
- **CSS selectors** -- every Google Maps selector in one place

When Google changes the Maps UI, update the selectors at the bottom of `src/config.py` -- no other files need to change.

## Project Structure

```
/
├── src/
│   ├── config.py             # All settings + selectors (single source of truth)
│   ├── core/
│   │   ├── browser.py        # Playwright + Stealth browser factory
│   │   ├── scroller.py       # Infinite scroll engine
│   │   ├── parser.py         # Data extraction from page elements
│   │   └── error_handler.py  # Retry logic, screenshots, checkpoints
│   ├── models/
│   │   └── business.py       # Pydantic data models
│   ├── utils/
│   │   └── exporter.py       # CSV + JSON export
│   └── main.py               # Entry point / orchestrator
├── data/                     # Scraped output (CSV + JSON)
├── logs/                     # Error logs + screenshots
└── requirements.txt
```

## Troubleshooting

### "Sidebar feed not found"

Google may have changed the page structure. Open `src/config.py` and update the `SIDEBAR_FEED` and `RESULT_CARD` selectors. Run with `--no-headless` to inspect the page visually.

### "Browser context creation failed"

Make sure Chromium is installed: `playwright install chromium`.

### Cookie consent blocking results

The scraper tries to dismiss cookie banners automatically. If your region shows a different banner, update `ACCEPT_COOKIES` in `src/config.py`.

### Resuming an interrupted scrape

Checkpoints are saved in `logs/resume_<query>.json`. On the next run with the same query the scraper loads existing data and avoids re-scraping. Delete the checkpoint files to force a fresh run.

## Future Roadmap

1. **Detailed scraping** -- Click into each listing to extract phone, website, address, rating, email
2. **Async support** -- Parallel detail extraction with `asyncio`
3. **Rate limiting** -- Configurable delays between deep-scrape page visits
4. **Proxy support** -- Rotate proxies for large-scale scraping
