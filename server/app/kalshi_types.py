from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PotentialPayoutFrom100Dollars(BaseModel):
    yes: Optional[str] = None
    no: Optional[str] = None


class MarketItem(BaseModel):
    ticker: str
    yes_subtitle: Optional[str] = None
    no_subtitle: Optional[str] = None
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    last_price: Optional[int] = None
    yes_bid_dollars: Optional[str] = None
    yes_ask_dollars: Optional[str] = None
    last_price_dollars: Optional[str] = None
    price_delta: Optional[float] = None
    close_ts: Optional[datetime] = None
    expected_expiration_ts: Optional[datetime] = None
    open_ts: Optional[datetime] = None
    rulebook_variables: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    score: Optional[int] = None
    market_id: Optional[str] = None
    title: Optional[str] = None
    potential_payout_from_100_dollars: Optional[PotentialPayoutFrom100Dollars] = None


class ProductMetadata(BaseModel):
    categories: Optional[List[str]] = None
    promoted_milestone_id: Optional[str] = None
    scope: Optional[Any] = None
    structured_icon: Optional[str] = None
    automatic_featured_text: Optional[str] = None
    subcategories: Optional[Dict[str, Any]] = None


class SeriesSearchItem(BaseModel):
    series_ticker: str
    series_title: str
    event_ticker: str
    event_subtitle: Optional[str] = None
    event_title: str
    category: Optional[str] = None
    product_metadata: Optional[ProductMetadata] = None
    product_metadata_derived: Optional[Dict[str, Any]] = None
    total_series_volume: Optional[int] = None
    total_volume: Optional[int] = None
    total_market_count: Optional[int] = None
    active_market_count: Optional[int] = None
    markets: List[MarketItem] = []
    is_trending: Optional[bool] = None
    is_new: Optional[bool] = None
    is_closing: Optional[bool] = None
    is_price_delta: Optional[bool] = None
    search_score: Optional[int] = None
    fee_type: Optional[str] = None
    fee_multiplier: Optional[float] = None


class KalshiSearchResponse(BaseModel):
    total_results_count: int
    current_page: List[SeriesSearchItem]


