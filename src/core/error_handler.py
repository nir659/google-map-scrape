"""
Robust error handling: retry logic, screenshot capture, checkpoint save/load.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List

from loguru import logger
from playwright.sync_api import Page

import src.config as cfg


class ErrorHandler:
    """Centralised error handling and recovery utilities."""

    def __init__(self) -> None:
        self._setup_logging()

    # -- Logging -----------------------------------------------------------

    @staticmethod
    def _setup_logging() -> None:
        """Configure loguru sinks (console + rotating file)."""
        cfg.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = cfg.LOGS_DIR / "scraper_{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_path),
            rotation="10 MB",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
        )
        logger.info("Logging initialised  ->  {}", cfg.LOGS_DIR)

    # -- Screenshots -------------------------------------------------------

    @staticmethod
    def take_screenshot(page: Page, error_name: str) -> Path | None:
        """Save a screenshot when something goes wrong."""
        if not cfg.ENABLE_SCREENSHOTS:
            return None

        cfg.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = cfg.LOGS_DIR / f"{ts}_{error_name}.png"
        try:
            page.screenshot(path=str(filename), full_page=True)
            logger.warning("Screenshot saved  ->  {}", filename)
            return filename
        except Exception as exc:
            logger.error("Failed to save screenshot: {}", exc)
            return None

    # -- Retry with exponential backoff ------------------------------------

    @staticmethod
    def retry_with_backoff(
        func: Callable,
        max_retries: int = cfg.MAX_RETRIES,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Call *func* up to *max_retries* times with exponential backoff.

        Returns the result of the first successful call.
        Raises the last exception if all retries fail.
        """
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                wait = min(
                    cfg.RETRY_BACKOFF_BASE ** attempt,
                    cfg.RETRY_BACKOFF_MAX,
                )
                logger.warning(
                    "Attempt {}/{} failed ({}). Retrying in {:.1f}s ...",
                    attempt,
                    max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # -- Checkpoint (save / load) ------------------------------------------

    @staticmethod
    def _checkpoint_path(query_name: str) -> Path:
        return cfg.LOGS_DIR / f"resume_{query_name}.json"

    @staticmethod
    def save_checkpoint(data: List[dict], query_name: str) -> None:
        """Persist intermediate results so a crashed run can resume."""
        path = ErrorHandler._checkpoint_path(query_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, default=str)
        logger.debug("Checkpoint saved ({} records)  ->  {}", len(data), path)

    @staticmethod
    def load_checkpoint(query_name: str) -> List[dict] | None:
        """Load a previous checkpoint if one exists."""
        path = ErrorHandler._checkpoint_path(query_name)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.info("Checkpoint loaded ({} records)  <-  {}", len(data), path)
        return data

    @staticmethod
    def clear_checkpoint(query_name: str) -> None:
        """Remove checkpoint after a successful export."""
        path = ErrorHandler._checkpoint_path(query_name)
        if path.exists():
            path.unlink()
            logger.debug("Checkpoint cleared  ->  {}", path)
