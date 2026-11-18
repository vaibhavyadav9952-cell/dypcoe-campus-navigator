"""
api/locations.py - Public location endpoints for DYPCOE Campus Navigator.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location
from app.schemas import LocationResponse

router = APIRouter(prefix="/api", tags=["locations"])


@router.get("/locations", response_model=List[LocationResponse])
def list_locations(
    search: Optional[str] = Query(None, description="Search by name, building, category"),
    category: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    floor: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Location)
    if search:
        kw = f"%{search}%"
        q = q.filter(
            or_(
                Location.name.ilike(kw),
                Location.building.ilike(kw),
                Location.category.ilike(kw),
                Location.description.ilike(kw),
                Location.room_number.ilike(kw),
            )
        )
    if category:
        q = q.filter(Location.category == category)
    if building:
        kw = f"%{building}%"
        q = q.filter(Location.building.ilike(kw))
    if floor is not None:
        q = q.filter(Location.floor == floor)
    return q.order_by(Location.name).all()


@router.get("/locations/{location_id}", response_model=LocationResponse)
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc
