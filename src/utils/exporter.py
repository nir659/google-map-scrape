"""
Export scraped data to CSV and JSON.
"""

import json
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger

from src.models.business import Business


def _ensure_dir(path: Path) -> None:
    """Create parent directories if they don't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def export_to_csv(data: List[Business], output_path: Path) -> Path:
    """
    Write listings to a CSV file using pandas.

    Returns the resolved output path.
    """
    _ensure_dir(output_path)
    records = [item.model_dump() for item in data]
    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("CSV exported ({} rows)  ->  {}", len(df), output_path)
    return output_path


def export_to_json(data: List[Business], output_path: Path) -> Path:
    """
    Write listings to a JSON file using Pydantic serialisation.

    Returns the resolved output path.
    """
    _ensure_dir(output_path)
    records = [item.model_dump(mode="json") for item in data]
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2, default=str)
    logger.info("JSON exported ({} records)  ->  {}", len(records), output_path)
    return output_path


def export_all(
    data: List[Business],
    output_dir: Path,
    query_name: str,
) -> dict:
    """
    Export leads + enriched versions (CSV and JSON).

    Returns a dict with all output file paths.
    """
    safe_name = query_name.replace(" ", "_").lower()

    csv_path = output_dir / f"{safe_name}_leads.csv"
    json_path = output_dir / f"{safe_name}_leads.json"
    enriched_csv = output_dir / f"{safe_name}_enriched.csv"
    enriched_json = output_dir / f"{safe_name}_enriched.json"

    export_to_csv(data, csv_path)
    export_to_json(data, json_path)

    # Also save as enriched filenames for clarity
    export_to_csv(data, enriched_csv)
    export_to_json(data, enriched_json)

    return {
        "csv": csv_path,
        "json": json_path,
        "enriched_csv": enriched_csv,
        "enriched_json": enriched_json,
    }
