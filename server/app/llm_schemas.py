"""
Pydantic schemas for LLM structured outputs.
"""
from typing import List
from pydantic import BaseModel, Field


class DerivativeBeliefs(BaseModel):
    """Response schema for derivative belief generation."""
    derivatives: List[str] = Field(
        description="List of 3-5 high-quality derivative beliefs",
        min_length=3,
        max_length=5
    )


class VerificationResponse(BaseModel):
    """Response schema for claim verification."""
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    rationale: str = Field(
        description="Brief rationale explaining the confidence score (2-3 sentences)"
    )


