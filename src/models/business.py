"""
Pydantic data model for scraped business listings.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Business(BaseModel):
    """All data extractable from a Google Maps sidebar card + enrichment."""

    # -- Stage 1: Maps scraper fields --------------------------------------
    name: str = Field(..., description="Business name")
    link: str = Field(..., description="Google Maps place URL")
    phone: Optional[str] = Field(None, description="Phone number")
    website: Optional[str] = Field(None, description="Business website URL")
    address: Optional[str] = Field(None, description="Street address")
    rating: Optional[float] = Field(None, description="Star rating (1.0-5.0)")
    reviews: Optional[int] = Field(None, description="Number of reviews")
    category: Optional[str] = Field(None, description="Business category")
    query_source: str = Field(..., description="The query that produced this result")
    scraped_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of when the record was scraped",
    )

    # -- Stage 2: Email enrichment fields ----------------------------------
    email: Optional[str] = Field(None, description="Extracted email address")
    enrichment_status: Optional[str] = Field(
        None,
        description="tier1_success | tier2_success | tier3_success | no_website | failed",
    )
    enrichment_method: Optional[str] = Field(
        None, description="Which tier found the email"
    )
    enriched_at: Optional[datetime] = Field(
        None, description="Timestamp of enrichment"
    )
