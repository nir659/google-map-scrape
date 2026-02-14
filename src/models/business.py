"""
Pydantic data model for scraped business listings.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Business(BaseModel):
    """All data extractable from a Google Maps sidebar card."""

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
