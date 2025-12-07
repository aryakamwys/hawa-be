"""
Pydantic schemas untuk weather service
"""
from typing import Optional
from pydantic import BaseModel, Field


class HeatmapTipsParams(BaseModel):
    """Parameters untuk generate heatmap tips"""
    pm25: Optional[float] = Field(default=None, description="PM2.5 value")
    pm10: Optional[float] = Field(default=None, description="PM10 value")
    air_quality: Optional[str] = Field(default=None, description="Air quality status")
    risk_level: Optional[str] = Field(default=None, description="Risk level (high, moderate, low)")
    location: Optional[str] = Field(default=None, description="Location name")
    language: str = Field(default="id", description="Language code (id, en, su)")
