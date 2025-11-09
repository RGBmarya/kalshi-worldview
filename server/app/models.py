from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, conlist, confloat


class GraphNode(BaseModel):
    id: str
    label: str
    url: Optional[HttpUrl] = None
    type: Literal["series", "market"]
    similarity: confloat(ge=0.0, le=1.0)
    hop: int


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: confloat(ge=0.0, le=1.0)


class Suggestion(BaseModel):
    nodeId: str = Field(..., alias="nodeId")
    action: Literal["YES", "NO", "SKIP"]
    confidence: confloat(ge=0.0, le=1.0)
    rationale: str
    url: HttpUrl

    class Config:
        populate_by_name = True


class Graph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    coreId: str


class GraphRequest(BaseModel):
    worldview: str = Field(..., min_length=4, max_length=2000)
    k: int = Field(200, ge=1, le=1000)
    maxHops: int = Field(3, ge=0, le=6)
    threshold: float = Field(0.78, ge=0.0, le=1.0)
    topN: int = Field(15, ge=1, le=100)


class GraphResponse(BaseModel):
    graph: Graph
    suggestions: List[Suggestion]
    debug: Optional[dict] = None


class Candidate(BaseModel):
    id: str
    type: Literal["series", "market"]
    title: str
    description: Optional[str] = None
    url: Optional[HttpUrl] = None


