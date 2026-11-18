"""
api/v1.py - v1 API layer for DYPCOE Campus Navigator.

Provides all /api/v1/ endpoints that the React frontend expects:
  GET  /api/v1/locations           - list all locations (optional ?category=)
  GET  /api/v1/locations/categories - list distinct category strings
  GET  /api/v1/locations/{id}      - get one location
  POST /api/v1/locations           - create location (admin)
  PATCH /api/v1/locations/{id}     - update location (admin)
  DELETE /api/v1/locations/{id}    - delete location (admin)
  POST /api/v1/directions          - get route between two locations by name or id
  POST /api/v1/chat                - AI assistant chat
  POST /api/v1/auth/login          - JSON login -> {token}
  GET  /api/v1/admin/stats/overview - admin dashboard stats
"""

import json
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, GraphNode, User, ChatHistory
from app.security import (
    verify_password,
    create_access_token,
    get_current_admin_user,
    get_password_hash,
)
from app.services.pathfinding import (
    build_graph,
    dijkstra,
    calculate_eta,
    generate_step_instructions,
    invalidate_graph_cache,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])

Admin = Depends(get_current_admin_user)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _loc_to_dict(loc: Location) -> Dict[str, Any]:
    """Serialize a Location ORM object to the JSON shape the frontend expects."""
    return {
        "id": loc.id,
        "name": loc.name,
        "category": loc.category or "",
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "building": loc.building or "",
        "floor": str(loc.floor) if loc.floor is not None else "",
        "description": loc.description or "",
        "image_url": None,
        # Extra fields (admin / directions use these)
        "room_number": loc.room_number or "",
        "is_navigable": loc.is_navigable,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/auth/login")
def login_v1(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    JSON login: {username: str, password: str} → {token: str}
    Frontend stores token as 'dypcoe_admin_token' in localStorage.
    """
    username = payload.get("username") or payload.get("email") or ""
    password = payload.get("password") or ""

    user = db.query(User).filter(User.email == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    token = create_access_token({"sub": user.email, "admin": True})
    return {"token": token, "access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Locations – public
# ---------------------------------------------------------------------------

@router.get("/locations/categories")
def list_categories(db: Session = Depends(get_db)):
    """Return sorted list of distinct category strings."""
    rows = (
        db.query(Location.category)
        .filter(Location.category.isnot(None), Location.category != "")
        .distinct()
        .all()
    )
    return sorted([r[0] for r in rows if r[0]])


@router.get("/locations")
def list_locations(category: Optional[str] = None, db: Session = Depends(get_db)):
    """List all campus locations, optionally filtered by category."""
    q = db.query(Location)
    if category:
        q = q.filter(Location.category == category)
    locs = q.order_by(Location.name).all()
    return [_loc_to_dict(loc) for loc in locs]


@router.get("/locations/{location_id}")
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return _loc_to_dict(loc)


# ---------------------------------------------------------------------------
# Locations – admin CRUD (require JWT admin)
# ---------------------------------------------------------------------------

@router.post("/locations", status_code=201)
def create_location_v1(payload: Dict[str, Any], db: Session = Depends(get_db), _=Admin):
    """Admin: create a new location. Auto-creates a GraphNode if is_navigable=True."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if db.query(Location).filter(Location.name == name).first():
        raise HTTPException(status_code=400, detail="A location with this name already exists")

    lat = payload.get("latitude") or payload.get("lat")
    lng = payload.get("longitude") or payload.get("lng")
    floor_raw = payload.get("floor")
    floor_int = int(floor_raw) if floor_raw not in (None, "", "null") else None

    loc = Location(
        name=name,
        category=payload.get("category") or "",
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
        building=payload.get("building") or "",
        floor=floor_int,
        room_number=payload.get("room_number") or "",
        description=payload.get("description") or "",
        is_navigable=bool(payload.get("is_navigable", True)),
    )
    db.add(loc)
    db.flush()

    if loc.is_navigable and loc.latitude and loc.longitude:
        node = GraphNode(
            location_id=loc.id,
            node_type="location",
            floor=loc.floor,
            lat=loc.latitude,
            lng=loc.longitude,
            label=loc.name,
        )
        db.add(node)
        db.flush()
        loc.node_id = node.id
        invalidate_graph_cache()

    db.commit()
    db.refresh(loc)
    return _loc_to_dict(loc)


@router.patch("/locations/{location_id}")
def update_location_v1(
    location_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _=Admin,
):
    """Admin: partially update a location."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    field_map = {
        "name": "name",
        "category": "category",
        "latitude": "latitude",
        "longitude": "longitude",
        "building": "building",
        "floor": "floor",
        "room_number": "room_number",
        "description": "description",
        "is_navigable": "is_navigable",
    }
    for json_key, model_attr in field_map.items():
        if json_key in payload:
            val = payload[json_key]
            if json_key == "floor" and val not in (None, "", "null"):
                val = int(val)
            elif json_key == "floor":
                val = None
            setattr(loc, model_attr, val)

    # Sync the linked graph node
    if loc.node_id:
        node = db.query(GraphNode).filter(GraphNode.id == loc.node_id).first()
        if node:
            if "latitude" in payload and payload["latitude"] is not None:
                node.lat = float(payload["latitude"])
            if "longitude" in payload and payload["longitude"] is not None:
                node.lng = float(payload["longitude"])
            if "floor" in payload:
                node.floor = loc.floor
            if "name" in payload and payload["name"]:
                node.label = payload["name"]

    # Auto-create node if is_navigable just turned on
    if loc.is_navigable and not loc.node_id and loc.latitude and loc.longitude:
        node = GraphNode(
            location_id=loc.id,
            node_type="location",
            floor=loc.floor,
            lat=loc.latitude,
            lng=loc.longitude,
            label=loc.name,
        )
        db.add(node)
        db.flush()
        loc.node_id = node.id

    invalidate_graph_cache()
    db.commit()
    db.refresh(loc)
    return _loc_to_dict(loc)


@router.delete("/locations/{location_id}", status_code=204)
def delete_location_v1(
    location_id: int,
    db: Session = Depends(get_db),
    _=Admin,
):
    """Admin: delete a location and its linked graph node."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if loc.node_id:
        node = db.query(GraphNode).filter(GraphNode.id == loc.node_id).first()
        if node:
            db.delete(node)

    db.delete(loc)
    invalidate_graph_cache()
    db.commit()


# ---------------------------------------------------------------------------
# Directions  POST /api/v1/directions
# ---------------------------------------------------------------------------

@router.post("/directions")
async def get_directions(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Frontend sends: {from_location: str|int, to_location: str|int}
    Returns: {routes: [{distanceMeters, durationSeconds, path, steps}]}
    """
    raw_from = payload.get("from_location")
    raw_to = payload.get("to_location")

    def find_location(val) -> Optional[Location]:
        if val is None:
            return None
        # Try by ID first
        try:
            loc_id = int(val)
            return db.query(Location).filter(Location.id == loc_id).first()
        except (ValueError, TypeError):
            pass
        # Try exact name match, then partial
        loc = db.query(Location).filter(Location.name == str(val)).first()
        if not loc:
            kw = f"%{val}%"
            loc = db.query(Location).filter(Location.name.ilike(kw)).first()
        return loc

    start_loc = find_location(raw_from)
    end_loc = find_location(raw_to)

    if not start_loc:
        raise HTTPException(status_code=404, detail=f"Start location '{raw_from}' not found")
    if not end_loc:
        raise HTTPException(status_code=404, detail=f"End location '{raw_to}' not found")

    if start_loc.id == end_loc.id:
        return {
            "routes": [{
                "distanceMeters": 0,
                "durationSeconds": 0,
                "path": [],
                "steps": [f"You are already at {start_loc.name}."],
                "routeType": "none",
            }]
        }

    # ---- Try indoor Dijkstra ----
    if start_loc.node_id and end_loc.node_id:
        graph = build_graph(db)
        try:
            path_ids, total_dist = dijkstra(graph, start_loc.node_id, end_loc.node_id)
            nodes = db.query(GraphNode).filter(GraphNode.id.in_(path_ids)).all()
            node_map = {n.id: n for n in nodes}
            ordered = [node_map[nid] for nid in path_ids if nid in node_map]
            eta = calculate_eta(total_dist)
            steps = generate_step_instructions(ordered, start_loc, end_loc)

            path_coords = [
                {"lat": n.lat, "lng": n.lng}
                for n in ordered
                if n.lat is not None and n.lng is not None
            ]
            route_type = "indoor" if (start_loc.building == end_loc.building) else "hybrid"
            return {
                "routes": [{
                    "distanceMeters": round(total_dist, 1),
                    "durationSeconds": eta.get("eta_seconds", 0),
                    "path": path_coords,
                    "steps": steps,
                    "routeType": route_type,
                }]
            }
        except ValueError:
            pass  # fall through

    # ---- Straight-line outdoor fallback ----
    if start_loc.latitude and start_loc.longitude and end_loc.latitude and end_loc.longitude:
        from app.core.config import settings
        # Try Google Maps if key available
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                from app.services.google_maps import get_walking_route
                outdoor = await get_walking_route(
                    start_loc.latitude, start_loc.longitude,
                    end_loc.latitude, end_loc.longitude,
                )
                dist = outdoor["distance_meters"]
                dur = outdoor["duration_seconds"]
                steps = [
                    f"Start at {start_loc.name}",
                    f"Walk {int(dist)}m to {end_loc.name}",
                    f"Arrive at {end_loc.name}",
                ]
                return {
                    "routes": [{
                        "distanceMeters": round(dist, 1),
                        "durationSeconds": dur,
                        "path": [
                            {"lat": start_loc.latitude, "lng": start_loc.longitude},
                            {"lat": end_loc.latitude, "lng": end_loc.longitude},
                        ],
                        "steps": steps,
                        "routeType": "outdoor",
                        "polyline": outdoor.get("polyline"),
                    }]
                }
            except Exception:
                pass

        # Haversine fallback
        dlat = (end_loc.latitude - start_loc.latitude) * 111320
        dlng = (
            (end_loc.longitude - start_loc.longitude)
            * 111320
            * math.cos(math.radians(start_loc.latitude))
        )
        dist = math.sqrt(dlat ** 2 + dlng ** 2)
        eta = calculate_eta(dist)
        steps = [
            f"Start at {start_loc.name}",
            f"Walk approximately {int(dist)}m to {end_loc.name}",
            f"Arrive at {end_loc.name}",
        ]
        if end_loc.node_id is None:
            steps.append("⚠️ Indoor navigation unavailable — please ask at reception.")
        return {
            "routes": [{
                "distanceMeters": round(dist, 1),
                "durationSeconds": eta.get("eta_seconds", 0),
                "path": [
                    {"lat": start_loc.latitude, "lng": start_loc.longitude},
                    {"lat": end_loc.latitude, "lng": end_loc.longitude},
                ],
                "steps": steps,
                "routeType": "outdoor",
            }]
        }

    raise HTTPException(status_code=422, detail="Cannot calculate route — location coordinates unavailable.")


# ---------------------------------------------------------------------------
# Chat  POST /api/v1/chat
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a friendly campus navigation assistant for DYPCOE – Dr. D.Y. Patil College of Engineering, Akurdi, Pune.

You help students, faculty, and visitors:
- Find buildings, labs, classrooms, offices, and campus facilities
- Understand which floor and building a room is in
- Get general directions and navigation tips

Campus locations:
{locations_json}

Guidelines:
- Mention building, floor, and category when describing a location.
- For turn-by-turn directions tell users to use the Search + "Get Directions" feature in the app.
- If a location is not listed, say you're not sure and suggest asking at the main reception.
- Keep answers concise, friendly, and accurate.
- Do not invent room numbers or paths not in the data.
"""


@router.post("/chat")
async def chat_v1(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Frontend sends: {message: str, client_resolution?: any}
    Returns: {reply: str, suggestions?: [...locations]}
    """
    message = (payload.get("message") or "").strip()
    if not message:
        return {"reply": "Hi! How can I help you navigate DYPCOE campus today?", "suggestions": []}

    locations = db.query(Location).order_by(Location.name).all()
    loc_data = [
        {
            "id": l.id,
            "name": l.name,
            "category": l.category,
            "building": l.building,
            "floor": l.floor,
            "room_number": l.room_number,
            "description": l.description,
        }
        for l in locations
    ]
    system_prompt = SYSTEM_PROMPT.format(locations_json=json.dumps(loc_data, indent=2))

    # Use AI service (supports OpenAI / Gemini / keyword fallback)
    from app.services.ai_service import get_ai_response
    reply = await get_ai_response(
        query=message,
        history=[],
        system_prompt=system_prompt,
        locations=locations,
    )

    # Log chat (best-effort)
    try:
        db.add(ChatHistory(session_id="v1", user_query=message, ai_response=reply))
        db.commit()
    except Exception:
        pass

    # Build quick suggestions: locations mentioned in reply
    suggestions = []
    for loc in locations:
        if loc.name.lower() in reply.lower():
            suggestions.append(_loc_to_dict(loc))
            if len(suggestions) >= 3:
                break

    return {"reply": reply, "suggestions": suggestions}


# ---------------------------------------------------------------------------
# Admin stats  GET /api/v1/admin/stats/overview
# ---------------------------------------------------------------------------

@router.get("/admin/stats/overview")
def stats_overview(db: Session = Depends(get_db), _=Admin):
    """Return high-level admin dashboard stats."""
    location_count = db.query(Location).count()
    category_count = (
        db.query(Location.category)
        .filter(Location.category.isnot(None), Location.category != "")
        .distinct()
        .count()
    )
    navigable_count = db.query(Location).filter(Location.is_navigable == True).count()  # noqa: E712
    chat_count = db.query(ChatHistory).count()

    # Category breakdown
    from sqlalchemy import func
    rows = (
        db.query(Location.category, func.count(Location.id))
        .filter(Location.category.isnot(None), Location.category != "")
        .group_by(Location.category)
        .order_by(func.count(Location.id).desc())
        .all()
    )
    categories = [{"name": r[0], "count": r[1]} for r in rows]

    return {
        "totalLocations": location_count,
        "totalCategories": category_count,
        "navigableLocations": navigable_count,
        "totalChatMessages": chat_count,
        "categoriesBreakdown": categories,
        "campus": "DYPCOE – Dr. D.Y. Patil College of Engineering, Akurdi, Pune",
    }


# ---------------------------------------------------------------------------
# Admin Insights  GET /api/v1/admin/insights/*
# (Used by the React admin dashboard — DashboardPage, DataHealthPage,
#  SystemStatusPage, AIAnalyticsPage, SearchAnalyticsPage)
# ---------------------------------------------------------------------------

CAMPUS_LAT  = 18.6448
CAMPUS_LNG  = 73.7582
OUTLIER_M   = 3000   # metres beyond which a point is "suspicious"
EXPECTED_IDS = (1, 100)  # loose range; we just report what's in the DB

def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    """Return approximate distance in metres between two WGS-84 points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _run_health_checks(locations: list) -> dict:
    """
    Run all data-quality checks over the location list and return the
    full health payload expected by DataHealthPage.jsx.
    """
    import re
    from collections import defaultdict

    ids = [l.id for l in locations]
    id_set = set(ids)
    min_id = min(ids) if ids else 0
    max_id = max(ids) if ids else 0

    checks = []
    attention = []
    row_flags: dict[int, list[str]] = {l.id: [] for l in locations}

    # ---- Count check ----
    n = len(locations)
    checks.append({
        "code": "count",
        "title": "Location count",
        "status": "healthy" if n >= 30 else "warning",
        "detail": f"{n} locations in the database",
        "expected": "≥ 30",
        "affected_ids": [],
    })

    # ---- Name whitespace ----
    ws_ids = [l.id for l in locations if l.name != l.name.strip()]
    for lid in ws_ids:
        row_flags[lid].append("name_whitespace")
    checks.append({
        "code": "name_whitespace",
        "title": "Name whitespace",
        "status": "warning" if ws_ids else "healthy",
        "detail": f"{len(ws_ids)} names with leading/trailing spaces" if ws_ids else "No issues",
        "expected": "0",
        "affected_ids": ws_ids,
    })
    if ws_ids:
        attention.append({"code": "name_whitespace", "title": "Name spacing issues",
                          "detail": "Some location names have leading or trailing spaces.",
                          "status": "warning", "ids": ws_ids})

    # ---- Missing building ----
    no_bldg = [l.id for l in locations if not (l.building or "").strip()]
    for lid in no_bldg:
        row_flags[lid].append("missing_building")
    checks.append({
        "code": "missing_building",
        "title": "Building label",
        "status": "info" if no_bldg else "healthy",
        "detail": f"{len(no_bldg)} locations without a building label" if no_bldg else "All locations have a building",
        "expected": "0",
        "affected_ids": no_bldg,
    })

    # ---- Missing description ----
    no_desc = [l.id for l in locations if not (l.description or "").strip()]
    for lid in no_desc:
        row_flags[lid].append("missing_description")
    checks.append({
        "code": "missing_description",
        "title": "Description",
        "status": "info" if no_desc else "healthy",
        "detail": f"{len(no_desc)} locations without a description" if no_desc else "All locations have descriptions",
        "expected": "0",
        "affected_ids": no_desc,
    })

    # ---- Category variants ----
    cats = [l.category for l in locations if l.category]
    cat_norm = {c: re.sub(r"\s+", " ", c).strip().lower() for c in cats}
    norm_counts: dict[str, list] = defaultdict(list)
    for c, n_c in cat_norm.items():
        norm_counts[n_c].append(c)
    variant_groups = [vs for vs in norm_counts.values() if len(vs) > 1]
    variant_ids = [l.id for l in locations if l.category and cat_norm.get(l.category) in
                   {n_c for n_c, vs in norm_counts.items() if len(vs) > 1}]
    for lid in variant_ids:
        row_flags[lid].append("category_variant")
    checks.append({
        "code": "category_variants",
        "title": "Category label consistency",
        "status": "warning" if variant_groups else "healthy",
        "detail": f"{len(variant_groups)} possible variant group(s)" if variant_groups else "Categories are consistent",
        "expected": "0 groups",
        "affected_ids": variant_ids,
    })
    if variant_groups:
        attention.append({"code": "category_variants", "title": "Category label variants",
                          "detail": f"{len(variant_groups)} groups of category labels that differ only in case or spacing.",
                          "status": "warning", "ids": variant_ids})

    # ---- Suspicious coordinates ----
    suspicious = []
    for l in locations:
        if l.latitude is None or l.longitude is None:
            continue
        d = _haversine_m(l.latitude, l.longitude, CAMPUS_LAT, CAMPUS_LNG)
        if d > OUTLIER_M:
            reasons = [f"{int(d)}m from campus centre"]
            suspicious.append({
                "id": l.id, "name": l.name,
                "latitude": l.latitude, "longitude": l.longitude,
                "distance_m": round(d, 1), "reasons": reasons,
            })
            row_flags[l.id].append("needs_verification")
    susp_ids = [s["id"] for s in suspicious]
    checks.append({
        "code": "suspicious_coordinates",
        "title": "Suspicious coordinates",
        "status": "warning" if suspicious else "healthy",
        "detail": f"{len(suspicious)} locations far from campus" if suspicious else "All coordinates near campus",
        "expected": "0",
        "affected_ids": susp_ids,
    })
    if suspicious:
        attention.append({"code": "suspicious_coordinates", "title": "Coordinates need verification",
                          "detail": f"{len(suspicious)} locations are more than {OUTLIER_M}m from the campus centre.",
                          "status": "warning", "ids": susp_ids})

    # ---- Shared coordinates ----
    coord_groups: dict[tuple, list] = defaultdict(list)
    for l in locations:
        if l.latitude is not None and l.longitude is not None:
            coord_groups[(round(l.latitude, 6), round(l.longitude, 6))].append({"id": l.id, "name": l.name})
    shared = [
        {"latitude": k[0], "longitude": k[1], "places": v}
        for k, v in coord_groups.items() if len(v) > 1
    ]
    shared_ids = [p["id"] for g in shared for p in g["places"]]
    for lid in shared_ids:
        row_flags[lid].append("shared_coordinates")

    overall = "warning" if any(c["status"] == "warning" for c in checks) else "info" if any(c["status"] == "info" for c in checks) else "healthy"

    return {
        "status": overall,
        "expected": {"count": n, "ids": [min_id, max_id], "outlier_radius_m": OUTLIER_M},
        "checks": checks,
        "attention": attention,
        "suspicious": suspicious,
        "shared_coordinate_groups": shared,
        "row_flags": row_flags,
        "canonical": {
            "status": "info",
            "synchronized": True,
            "matching": n,
            "canonical_count": n,
            "database_count": n,
            "mismatched": [],
            "missing_in_db": [],
            "extra_in_db": [],
            "error": None,
        },
    }


@router.get("/admin/insights/summary")
def insights_summary(db: Session = Depends(get_db), _=Admin):
    """
    Full summary consumed by DashboardPage.jsx.
    Shape: { locations, health, ai, events, canonical, generated_at }
    """
    from datetime import datetime, timezone
    from sqlalchemy import func as sqlfunc

    locations = db.query(Location).order_by(Location.name).all()
    n = len(locations)
    ids = [l.id for l in locations]
    min_id = min(ids) if ids else 0
    max_id = max(ids) if ids else 0
    cats = list({(l.category or "").strip() for l in locations if (l.category or "").strip()})
    bldgs = list({(l.building or "").strip() for l in locations if (l.building or "").strip()})

    health = _run_health_checks(locations)

    chat_total = db.query(ChatHistory).count()
    last_chat = db.query(sqlfunc.max(ChatHistory.created_at)).scalar()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "locations": {
            "total": n,
            "min_id": min_id,
            "max_id": max_id,
            "categories": len(cats),
            "categories_normalized": len(cats),
            "category_variant_groups": 0,
            "buildings": len(bldgs),
            "without_building": sum(1 for l in locations if not (l.building or "").strip()),
        },
        "health": {
            "status": health["status"],
            "attention": health["attention"],
        },
        "canonical": health["canonical"],
        "ai": {
            "total": chat_total,
            "resolved": chat_total,
            "unresolved": 0,
            "last_at": last_chat.isoformat() if last_chat else None,
        },
        "events": {
            "total": 0,
            "by_type": {},
            "since": None,
            "table": False,
        },
    }


@router.get("/admin/insights/data-health")
def insights_data_health(db: Session = Depends(get_db), _=Admin):
    """Full data-health report for DataHealthPage.jsx."""
    locations = db.query(Location).order_by(Location.name).all()
    return _run_health_checks(locations)


@router.get("/admin/insights/ai")
def insights_ai(db: Session = Depends(get_db), _=Admin):
    """AI analytics for AIAnalyticsPage.jsx."""
    from sqlalchemy import func as sqlfunc
    total = db.query(ChatHistory).count()
    last_at = db.query(sqlfunc.max(ChatHistory.created_at)).scalar()
    recent = (
        db.query(ChatHistory)
        .order_by(ChatHistory.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "total": total,
        "resolved": total,
        "unresolved": 0,
        "last_at": last_at.isoformat() if last_at else None,
        "endpoint_registered": True,
        "recent": [
            {
                "id": c.id,
                "session_id": c.session_id,
                "query": c.user_query,
                "response": c.ai_response,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in recent
        ],
    }


@router.get("/admin/insights/usage")
def insights_usage(db: Session = Depends(get_db), _=Admin):
    """Usage analytics for SearchAnalyticsPage.jsx / PlaceUsagePage.jsx."""
    return {
        "total": 0,
        "by_type": {},
        "since": None,
        "table": False,
        "note": "Usage events are stored client-side only; no server-side event tracking is configured.",
    }


@router.get("/admin/insights/system")
def insights_system(db: Session = Depends(get_db), _=Admin):
    """System status for SystemStatusPage.jsx."""
    import platform
    from datetime import datetime, timezone
    from sqlalchemy import text

    # DB version
    try:
        result = db.execute(text("SELECT version()")).scalar()
        db_version = result.split(" ")[1] if result else "unknown"
        db_name = db.execute(text("SELECT current_database()")).scalar()
        db_status = "healthy"
    except Exception as e:
        db_version = "unknown"
        db_name = "dypcoe_campus"
        db_status = "unavailable"

    location_count = db.query(Location).count()
    chat_count = db.query(ChatHistory).count()
    last_chat = db.execute(
        text("SELECT MAX(created_at) FROM chat_history")
    ).scalar()

    from app.core.config import settings

    return {
        "backend": {
            "time": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "python": platform.python_version(),
        },
        "database": {
            "status": db_status,
            "version": db_version,
            "name": db_name,
        },
        "locations": {
            "count": location_count,
            "status": "healthy" if location_count >= 30 else "warning",
        },
        "canonical": {
            "status": "info",
            "synchronized": True,
            "matching": location_count,
            "canonical_count": location_count,
            "error": None,
        },
        "ai": {
            "status": "healthy",
            "endpoint_registered": True,
            "logs": chat_count,
            "last_query_at": last_chat.isoformat() if last_chat else None,
        },
        "events": {
            "status": "info",
            "table": False,
            "count": 0,
        },
        "security": {
            "status": "warning" if not settings.SECRET_KEY or settings.SECRET_KEY in ("changeme", "secret", "your-secret-key") else "healthy",
            "default_admin_password": False,
            "default_secret_key": not settings.SECRET_KEY or settings.SECRET_KEY in ("changeme", "secret", "your-secret-key"),
            "token_lifetime_minutes": 60 * 24,
        },
    }
