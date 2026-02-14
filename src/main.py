"""
Google Maps Scraper -- main orchestrator.

Usage
-----
    python -m src.main -q "plumbers in New York City"
    python -m src.main -q "dentists in LA" --max-results 100
    python -m src.main -q "cafes in Chicago" --no-headless
"""

import sys
import time
import argparse

from loguru import logger

import src.config as cfg
from src.core.browser import (
    create_browser_context,
    search_maps,
    close_browser,
)
from src.core.scroller import perform_infinite_scroll
from src.core.parser import extract_listings
from src.core.error_handler import ErrorHandler
from src.enricher.orchestrator import enrich_businesses
from src.utils.exporter import export_all


# -- Helpers ---------------------------------------------------------------

def _query_label(query: str) -> str:
    """Derive a short filesystem-safe label from the raw query string."""
    return query.strip().replace(" ", "_").lower()[:60]


# -- Single-query runner ---------------------------------------------------

def run_query(
    query: str,
    max_results: int,
    error_handler: ErrorHandler,
) -> dict:
    """
    Execute one full scrape cycle for a single query.

    Returns a summary dict with counts and file paths.
    """
    name = _query_label(query)

    logger.info("=" * 60)
    logger.info("QUERY: '{}' (target: {} results)", query, max_results)
    logger.info("=" * 60)

    # Check for a previous checkpoint
    checkpoint = error_handler.load_checkpoint(name)
    if checkpoint:
        logger.info(
            "Resuming from checkpoint with {} existing records",
            len(checkpoint),
        )

    pw = browser = context = page = None
    try:
        # -- Browser -------------------------------------------------------
        pw, browser, context, page = create_browser_context()
        search_maps(page, query)

        # -- Scroll --------------------------------------------------------
        def _scroll():
            return perform_infinite_scroll(page, max_results, error_handler)

        total_loaded = error_handler.retry_with_backoff(_scroll)

        # -- Parse ---------------------------------------------------------
        listings = extract_listings(page, query)

        # -- Close browser before enrichment (frees memory) ----------------
        close_browser(pw, browser)
        pw = browser = None

        # -- Enrich --------------------------------------------------------
        if cfg.ENRICHER_ENABLED and listings:
            logger.info(
                "Starting email enrichment for {} businesses ...",
                len(listings),
            )
            listings = enrich_businesses(listings)
            emails_found = sum(1 for b in listings if b.email)
            logger.info(
                "Enrichment complete: {}/{} emails found",
                emails_found,
                len(listings),
            )

        # -- Checkpoint ----------------------------------------------------
        records = [item.model_dump(mode="json") for item in listings]
        error_handler.save_checkpoint(records, name)

        # -- Export --------------------------------------------------------
        output_dir = cfg.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = export_all(listings, output_dir, name)

        # Clean checkpoint after successful export
        error_handler.clear_checkpoint(name)

        return {
            "query": query,
            "total_loaded": total_loaded,
            "unique_exported": len(listings),
            "files": paths,
            "status": "success",
        }

    except Exception as exc:
        logger.error("Query '{}' failed: {}", query, exc)
        if page:
            error_handler.take_screenshot(page, f"query_failure_{name}")
        return {
            "query": query,
            "total_loaded": 0,
            "unique_exported": 0,
            "files": {},
            "status": f"failed: {exc}",
        }
    finally:
        if pw and browser:
            close_browser(pw, browser)


# -- CLI -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Maps Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.main -q 'plumbers in New York City'\n"
            "  python -m src.main -q 'dentists in LA' --max-results 100\n"
            "  python -m src.main -q 'cafes in Chicago' --no-headless\n"
        ),
    )
    parser.add_argument(
        "-q", "--query",
        type=str,
        required=True,
        help="Google Maps search query (e.g. 'plumbers in New York City')",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=cfg.DEFAULT_MAX_RESULTS,
        help=f"Maximum listings to scrape (default: {cfg.DEFAULT_MAX_RESULTS})",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        default=False,
        help="Run the browser in visible (headed) mode",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory for CSV/JSON (default: {cfg.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        default=False,
        help="Skip email enrichment (scrape only)",
    )
    args = parser.parse_args()

    # -- Apply CLI overrides -----------------------------------------------
    if args.no_headless:
        cfg.HEADLESS = False
    if args.output_dir:
        from pathlib import Path
        cfg.OUTPUT_DIR = Path(args.output_dir)
    if args.no_enrich:
        cfg.ENRICHER_ENABLED = False

    # -- Run ---------------------------------------------------------------
    error_handler = ErrorHandler()
    start = time.time()

    summary = run_query(args.query, args.max_results, error_handler)

    elapsed = time.time() - start

    # -- Report ------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("SCRAPING COMPLETE  ({:.1f}s elapsed)", elapsed)
    logger.info("=" * 60)
    status_icon = "OK" if summary["status"] == "success" else "FAIL"
    logger.info(
        "  [{}]  '{}'  ->  {} unique listings",
        status_icon,
        summary["query"],
        summary["unique_exported"],
    )
    if summary["files"]:
        for fmt, path in summary["files"].items():
            logger.info("  {} -> {}", fmt.upper(), path)
    logger.info("=" * 60)

    if summary["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
