"""
Email enrichment orchestrator.

Runs the tiered extraction pipeline across all businesses using
ThreadPoolExecutor for concurrent processing.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List

from loguru import logger

import src.config as cfg
from src.models.business import Business
from src.enricher.http_client import StealthHTTPClient
from src.enricher.tier1_regex import extract_email_tier1
from src.enricher.tier2_dom import extract_email_tier2
from src.enricher.tier3_browser import extract_email_tier3


def _process_single(
    business: Business,
    client: StealthHTTPClient,
) -> Business:
    """
    Run the tiered email pipeline for a single business.

    Mutates and returns the business with enrichment fields populated.
    """
    if not business.website:
        business.enrichment_status = "no_website"
        return business

    url = business.website

    # -- Tier 1: Fast regex ------------------------------------------------
    email, raw_html = extract_email_tier1(url, client)
    if email:
        business.email = email
        business.enrichment_status = "tier1_success"
        business.enrichment_method = "tier1_regex"
        business.enriched_at = datetime.utcnow()
        return business

    # -- Tier 2: DOM + contact page ----------------------------------------
    email = extract_email_tier2(url, client, html=raw_html)
    if email:
        business.email = email
        business.enrichment_status = "tier2_success"
        business.enrichment_method = "tier2_dom"
        business.enriched_at = datetime.utcnow()
        return business

    # -- Tier 3: Playwright JS render --------------------------------------
    email = extract_email_tier3(url, client, raw_html=raw_html)
    if email:
        business.email = email
        business.enrichment_status = "tier3_success"
        business.enrichment_method = "tier3_browser"
        business.enriched_at = datetime.utcnow()
        return business

    # -- All tiers failed --------------------------------------------------
    business.enrichment_status = "failed"
    business.enriched_at = datetime.utcnow()
    return business


def enrich_businesses(
    businesses: List[Business],
    max_workers: int | None = None,
) -> List[Business]:
    """
    Process all businesses through the tiered email pipeline.

    Parameters
    ----------
    businesses : list[Business]
        Scraped businesses (some may have ``website=None``).
    max_workers : int or None
        Thread count. Defaults to ``cfg.ENRICHER_MAX_WORKERS``.

    Returns
    -------
    list[Business]
        Same list, with email/enrichment fields populated.
    """
    if max_workers is None:
        max_workers = cfg.ENRICHER_MAX_WORKERS

    with_website = [b for b in businesses if b.website]
    without_website = [b for b in businesses if not b.website]

    # Mark no-website entries immediately
    for b in without_website:
        b.enrichment_status = "no_website"

    if not with_website:
        logger.info("No businesses have website URLs -- skipping enrichment")
        return businesses

    logger.info(
        "Enriching {} businesses ({} have websites, {} workers) ...",
        len(businesses),
        len(with_website),
        max_workers,
    )

    client = StealthHTTPClient()
    completed = 0
    lock = threading.Lock()

    # Counters for the summary
    stats = {
        "tier1_success": 0,
        "tier2_success": 0,
        "tier3_success": 0,
        "no_website": len(without_website),
        "failed": 0,
    }

    def _worker(biz: Business) -> Business:
        nonlocal completed
        result = _process_single(biz, client)
        with lock:
            completed += 1
            if result.enrichment_status:
                stats[result.enrichment_status] = (
                    stats.get(result.enrichment_status, 0) + 1
                )
            if completed % 10 == 0 or completed == len(with_website):
                logger.info(
                    "  Enrichment progress: {}/{}", completed, len(with_website)
                )
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, b): b for b in with_website}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                biz = futures[future]
                logger.warning("Enrichment crashed for {}: {}", biz.name, exc)
                biz.enrichment_status = "failed"

    # Log summary
    total = len(businesses)
    found = stats["tier1_success"] + stats["tier2_success"] + stats["tier3_success"]
    logger.info("")
    logger.info("Email Enrichment Results:")
    logger.info(
        "  Tier 1 (Regex):      {}/{} ({:.0f}%)",
        stats["tier1_success"], total, stats["tier1_success"] / max(total, 1) * 100,
    )
    logger.info(
        "  Tier 2 (DOM):        {}/{} ({:.0f}%)",
        stats["tier2_success"], total, stats["tier2_success"] / max(total, 1) * 100,
    )
    logger.info(
        "  Tier 3 (Playwright): {}/{} ({:.0f}%)",
        stats["tier3_success"], total, stats["tier3_success"] / max(total, 1) * 100,
    )
    logger.info(
        "  No website:          {}/{} ({:.0f}%)",
        stats["no_website"], total, stats["no_website"] / max(total, 1) * 100,
    )
    logger.info(
        "  Failed:              {}/{} ({:.0f}%)",
        stats["failed"], total, stats["failed"] / max(total, 1) * 100,
    )
    logger.info(
        "  Total emails found:  {}/{} ({:.0f}%)",
        found, total, found / max(total, 1) * 100,
    )

    return businesses
