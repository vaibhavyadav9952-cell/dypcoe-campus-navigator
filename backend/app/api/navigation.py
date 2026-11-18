"""
api/navigation.py - Route calculation endpoint for DYPCOE Campus Navigator.

Routing strategy:
  - Same building  → pure indoor Dijkstra on campus graph
  - Different building → Google Maps Routes API (outdoor walk) OR straight-line fallback
  - If indoor path not mapped → directions to building entrance + advisory message
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, GraphNode
from app.schemas import NavigateRequest, NavigateResponse, RouteNode
from app.services.pathfinding import build_graph, dijkstra, calculate_eta, generate_step_instructions
from app.services.google_maps import get_walking_route

router = APIRouter(prefix="/api", tags=["navigation"])


def _node_to_route_node(n: GraphNode) -> RouteNode:
    return RouteNode(
        id=n.id,
        label=n.label,
        lat=n.lat,
        lng=n.lng,
        indoor_x=n.indoor_x,
        indoor_y=n.indoor_y,
        floor=n.floor,
        node_type=n.node_type,
    )


@router.post("/navigate", response_model=NavigateResponse)
async def navigate(req: NavigateRequest, db: Session = Depends(get_db)):
    start_loc = db.query(Location).filter(Location.id == req.start_location_id).first()
    end_loc   = db.query(Location).filter(Location.id == req.end_location_id).first()

    if not start_loc:
        raise HTTPException(status_code=404, detail=f"Start location {req.start_location_id} not found")
    if not end_loc:
        raise HTTPException(status_code=404, detail=f"End location {req.end_location_id} not found")

    if start_loc.id == end_loc.id:
        return NavigateResponse(
            found=True, route_type="none",
            path=[], total_distance_meters=0, eta_seconds=0, eta_text="~0 mins",
            step_by_step=[f"You are already at {start_loc.name}."],
            message="Same location selected.",
        )

    # -----------------------------------------------------------------------
    # CASE 1: Both locations have graph nodes → try Dijkstra first
    # -----------------------------------------------------------------------
    if start_loc.node_id and end_loc.node_id:
        graph = build_graph(db)
        try:
            path_ids, total_dist = dijkstra(graph, start_loc.node_id, end_loc.node_id)
            nodes = db.query(GraphNode).filter(GraphNode.id.in_(path_ids)).all()
            node_map = {n.id: n for n in nodes}
            ordered = [node_map[nid] for nid in path_ids if nid in node_map]
            eta = calculate_eta(total_dist)
            steps = generate_step_instructions(ordered, start_loc, end_loc)
            route_type = "indoor" if (start_loc.building == end_loc.building) else "hybrid"

            return NavigateResponse(
                found=True,
                route_type=route_type,
                path=[_node_to_route_node(n) for n in ordered],
                total_distance_meters=round(total_dist, 1),
                **eta,
                step_by_step=steps,
                message=None,
            )
        except ValueError:
            pass  # fall through to outdoor routing

    # -----------------------------------------------------------------------
    # CASE 2: Different buildings (or no indoor path) → Google Maps outdoor
    # -----------------------------------------------------------------------
    if start_loc.latitude and start_loc.longitude and end_loc.latitude and end_loc.longitude:
        from app.core.config import settings
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                outdoor = await get_walking_route(
                    start_loc.latitude, start_loc.longitude,
                    end_loc.latitude, end_loc.longitude,
                )
                dist   = outdoor["distance_meters"]
                dur    = outdoor["duration_seconds"]
                eta    = calculate_eta(dist)
                steps  = [
                    f"Start at {start_loc.name}",
                    f"Walk {int(dist)}m to {end_loc.name}",
                    f"Arrive at {end_loc.name}",
                ]
                if end_loc.building and end_loc.floor is not None:
                    steps.append(
                        f"Enter {end_loc.building}, go to floor {end_loc.floor}"
                    )
                if end_loc.node_id is None:
                    steps.append(
                        "⚠️ Indoor navigation unavailable for this location — please ask at reception."
                    )
                return NavigateResponse(
                    found=True,
                    route_type="outdoor",
                    path=[
                        RouteNode(id=0, label=start_loc.name, lat=start_loc.latitude,
                                  lng=start_loc.longitude, node_type="location"),
                        RouteNode(id=1, label=end_loc.name, lat=end_loc.latitude,
                                  lng=end_loc.longitude, node_type="location"),
                    ],
                    total_distance_meters=round(dist, 1),
                    eta_seconds=dur,
                    eta_text=f"~{max(1, round(dur/60))} mins",
                    step_by_step=steps,
                    polyline=outdoor.get("polyline"),
                )
            except Exception:
                pass  # fall through to straight-line fallback

        # Straight-line fallback (no Google Maps key)
        import math
        dlat = (end_loc.latitude - start_loc.latitude) * 111320
        dlng = (end_loc.longitude - start_loc.longitude) * 111320 * math.cos(math.radians(start_loc.latitude))
        dist = math.sqrt(dlat**2 + dlng**2)
        eta  = calculate_eta(dist)
        steps = [
            f"Start at {start_loc.name}",
            f"Walk approximately {int(dist)}m to {end_loc.name}",
            f"Arrive at {end_loc.name}",
        ]
        if end_loc.node_id is None:
            steps.append(
                "⚠️ Indoor navigation unavailable for this location — please ask at reception."
            )
        return NavigateResponse(
            found=True,
            route_type="outdoor",
            path=[
                RouteNode(id=0, label=start_loc.name, lat=start_loc.latitude,
                          lng=start_loc.longitude, node_type="location"),
                RouteNode(id=1, label=end_loc.name, lat=end_loc.latitude,
                          lng=end_loc.longitude, node_type="location"),
            ],
            total_distance_meters=round(dist, 1),
            **eta,
            step_by_step=steps,
            message="Approximate straight-line distance (outdoor path data unavailable).",
        )

    # -----------------------------------------------------------------------
    # CASE 3: No coordinates at all
    # -----------------------------------------------------------------------
    return NavigateResponse(
        found=False,
        route_type="none",
        step_by_step=[
            f"Navigation from {start_loc.name} to {end_loc.name} is not yet mapped.",
            "Please ask campus staff for directions.",
        ],
        message="Location coordinates not available.",
    )
