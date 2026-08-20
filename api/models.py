from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = "ok"
    vercel_kv: bool = False

class GenericDataResponse(BaseModel):
    data: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "cache"
    updated_at: Optional[str] = None

class SectorDetailsResponse(BaseModel):
    sector: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    industries: List[Dict[str, Any]] = Field(default_factory=list)
    confluences: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: Optional[str] = None

class StockDetailsResponse(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    source: str = "cache"

class ConfluenceResponse(BaseModel):
    status: str = "ok"
    message: Optional[str] = None
    data: List[Dict[str, Any]] = Field(default_factory=list)
    strategy: Optional[str] = "all"
    profile: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

class WSBCalendarData(BaseModel):
    zh: List[Dict[str, Any]] = Field(default_factory=list)
    en: List[Dict[str, Any]] = Field(default_factory=list)

class WSBCalendarResponse(BaseModel):
    data: WSBCalendarData = Field(default_factory=WSBCalendarData)
    source: str = "cache"
    updated_at: Optional[str] = None
    error: Optional[str] = None

class TurbulenceResponse(BaseModel):
    cache_status: Optional[str] = None
    message: Optional[str] = None
    updated_at: Optional[str] = None
    status: Dict[str, Any] = Field(default_factory=dict)
    danger_zone_history: List[Dict[str, Any]] = Field(default_factory=list)
    chart_series: List[Dict[str, Any]] = Field(default_factory=list)
    source: Optional[str] = None
