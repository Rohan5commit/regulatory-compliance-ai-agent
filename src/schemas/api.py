from datetime import datetime

from pydantic import BaseModel


class RegulationResponse(BaseModel):
    id: int
    title: str
    regulator: str
    effective_date: datetime | None
    obligation_count: int


class ObligationResponse(BaseModel):
    id: int
    obligation_text: str
    obligation_type: str
    risk_level: str
    mapped_policy_count: int


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class MappingRequest(BaseModel):
    obligation_ids: list[int]
    policy_ids: list[str] | None = None
