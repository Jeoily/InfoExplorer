from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


class Evidence(BaseModel):
    id: str
    url: str
    title: str
    excerpt: str
    retrievedAt: datetime
    contentHash: str


class Generation(BaseModel):
    model: str
    host: str
    promptVersion: str
    inputHash: str


class QueryTrace(BaseModel):
    query: str
    language: Literal["en", "zh"]
    status: Literal["PENDING", "SUCCEEDED", "FAILED"] = "PENDING"
    resultCount: int = 0
    evidenceIds: list[str] = Field(default_factory=list)
    errorCode: str | None = None


class SearchPlan(BaseModel):
    mode: Literal["direct", "model"]
    intent: str | None
    reason: str | None
    queries: list[QueryTrace]
    generation: Generation | None = None


class ResearchReport(BaseModel):
    answer: str
    sources: list[str]
    provider: str
    query: str
    retrievedAt: datetime
    evidence: list[Evidence]
    generation: Generation | None = None
    plan: SearchPlan | None = None
