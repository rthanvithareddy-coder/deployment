from pydantic import BaseModel, Field
from typing import Optional


class Tower(BaseModel):
    id: str
    name: str
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    capacity: int = Field(default=20, ge=1)
    enabled: bool = True


class MobileUser(BaseModel):
    id: str
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    dx: float = 0.35
    dy: float = 0.20
    speed: float = Field(default=1.0, ge=0)
    connected_tower_conventional: Optional[str] = None
    connected_tower_mobility: Optional[str] = None


class Settings(BaseModel):
    user_count: int = Field(default=12, ge=1, le=200)
    speed: float = Field(default=1.0, ge=0, le=10)
    handover_threshold: float = Field(default=-90, ge=-120, le=-40)
    stability_margin: float = Field(default=4, ge=0, le=20)
    weights: dict = Field(default_factory=lambda: {"signal": 0.5, "capacity": 0.3, "mobility": 0.2})
    scenario: str = "Normal Mobility"

