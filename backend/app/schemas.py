"""
schemas.py - Pydantic v2 schemas for DYPCOE Campus Navigator API.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Location schemas
# ---------------------------------------------------------------------------
class LocationBase(BaseModel):
    name: str
    category: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    indoor_x: Optional[float] = None
    indoor_y: Optional[float] = None
    description: Optional[str] = None
    is_navigable: bool = True


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    indoor_x: Optional[float] = None
    indoor_y: Optional[float] = None
    description: Optional[str] = None
    is_navigable: Optional[bool] = None
    node_id: Optional[int] = None


class LocationResponse(LocationBase):
    id: int
    node_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GraphNode schemas
# ---------------------------------------------------------------------------
class GraphNodeBase(BaseModel):
    node_type: str = "junction"
    floor: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    indoor_x: Optional[float] = None
    indoor_y: Optional[float] = None
    label: Optional[str] = None
    location_id: Optional[int] = None


class GraphNodeCreate(GraphNodeBase):
    pass


class GraphNodeResponse(GraphNodeBase):
    id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GraphEdge schemas
# ---------------------------------------------------------------------------
class GraphEdgeBase(BaseModel):
    from_node_id: int
    to_node_id: int
    weight: float = 1.0
    is_indoor: bool = True
    is_accessible: bool = True
    edge_type: str = "corridor"


class GraphEdgeCreate(GraphEdgeBase):
    pass


class GraphEdgeResponse(GraphEdgeBase):
    id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    email: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None


# ---------------------------------------------------------------------------
# Navigation schemas
# ---------------------------------------------------------------------------
class NavigateRequest(BaseModel):
    start_location_id: int
    end_location_id: int


class RouteNode(BaseModel):
    id: int
    label: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    indoor_x: Optional[float] = None
    indoor_y: Optional[float] = None
    floor: Optional[int] = None
    node_type: str = "junction"


class NavigateResponse(BaseModel):
    found: bool
    route_type: str  # "indoor" | "outdoor" | "hybrid" | "none"
    path: List[RouteNode] = []
    total_distance_meters: float = 0.0
    eta_seconds: int = 0
    eta_text: str = ""
    step_by_step: List[str] = []
    polyline: Optional[str] = None  # encoded polyline for outdoor segment
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str
    conversation_history: List[ChatMessage] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    suggested_locations: List[LocationResponse] = []


# ---------------------------------------------------------------------------
# Graph dump schema
# ---------------------------------------------------------------------------
class GraphDump(BaseModel):
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
