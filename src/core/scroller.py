"""
Infinite-scroll engine for the Google Maps sidebar.

Mimics human behaviour with randomised scroll distance and pauses,
detects when no new results are loading, and respects a max-listing cap.
"""

import random
import time

from loguru import logger
from playwright.sync_api import Page

import src.config as cfg
from src.core.error_handler import ErrorHandler


def perform_infinite_scroll(
    page: Page,
    max_listings: int,
    error_handler: ErrorHandler,
) -> int:
    """
    Scroll the results sidebar until *max_listings* are loaded or
    no new results appear for several consecutive attempts.

    Parameters
    ----------
    page : Page
        Playwright page with search results already visible.
    max_listings : int
        Stop scrolling after this many result cards are found.
    error_handler : ErrorHandler
        Used for screenshots when the scroller gets stuck.

    Returns
    -------
    int
        Total number of result cards visible after scrolling.
    """
    sidebar = page.locator(cfg.SIDEBAR_FEED)

    if not sidebar.count():
        logger.error("Sidebar feed not found -- cannot scroll")
        error_handler.take_screenshot(page, "sidebar_not_found")
        return 0

    previous_count = 0
    stale_rounds = 0

    logger.info(
        "Starting infinite scroll (target: {} listings) ...", max_listings
    )

    while True:
        # -- Hover + scroll ------------------------------------------------
        try:
            sidebar.hover()
            scroll_delta = random.randint(
                cfg.SCROLL_DISTANCE_MIN,
                cfg.SCROLL_DISTANCE_MAX,
            )
            page.mouse.wheel(0, scroll_delta)
        except Exception as exc:
            logger.warning("Scroll action failed: {}", exc)
            error_handler.take_screenshot(page, "scroll_error")
            break

        # -- Human-like pause ----------------------------------------------
        pause = random.uniform(cfg.SCROLL_PAUSE_MIN, cfg.SCROLL_PAUSE_MAX)
        time.sleep(pause)

        # -- Count current listings ----------------------------------------
        current_count = page.locator(cfg.RESULT_CARD).count()
        logger.debug(
            "Listings loaded: {} (previous: {}, stale rounds: {})",
            current_count,
            previous_count,
            stale_rounds,
        )

        # -- Check for "end of list" text ----------------------------------
        try:
            end_marker = page.locator(cfg.END_OF_LIST)
            if end_marker.count() and end_marker.first.is_visible(timeout=500):
                logger.info(
                    "Reached end of list ({} listings loaded)", current_count
                )
                break
        except Exception:
            pass  # marker not found -- keep scrolling

        # -- Stale-count detection -----------------------------------------
        if current_count == previous_count:
            stale_rounds += 1
            if stale_rounds >= cfg.MAX_STALE_ATTEMPTS:
                logger.info(
                    "No new results for {} rounds -- stopping at {} listings",
                    stale_rounds,
                    current_count,
                )
                break
        else:
            stale_rounds = 0

        previous_count = current_count

        # -- Reached target ------------------------------------------------
        if current_count >= max_listings:
            logger.info(
                "Target reached ({}/{} listings)", current_count, max_listings
            )
            break

    final_count = page.locator(cfg.RESULT_CARD).count()
    logger.info("Scrolling complete -- {} total listings loaded", final_count)
    return final_count
