"""
api/admin.py - Admin CRUD endpoints for DYPCOE Campus Navigator.
All routes require a valid JWT with is_admin=True.

Auto-node creation:
  When admin creates a Location with is_navigable=True, the system automatically
  creates a matching GraphNode and links it to the location.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, GraphNode, GraphEdge, User
from app.schemas import (
    LocationCreate, LocationUpdate, LocationResponse,
    GraphNodeCreate, GraphNodeResponse,
    GraphEdgeCreate, GraphEdgeResponse,
    GraphDump,
    UserCreate, UserResponse,
)
from app.security import get_current_admin_user, get_password_hash
from app.services.pathfinding import invalidate_graph_cache

router = APIRouter(prefix="/api/admin", tags=["admin"])

Admin = Depends(get_current_admin_user)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@router.get("/locations", response_model=List[LocationResponse])
def admin_list_locations(db: Session = Depends(get_db), _=Admin):
    return db.query(Location).order_by(Location.id).all()


@router.post("/locations", response_model=LocationResponse, status_code=201)
def admin_create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    _=Admin,
):
    # Check for duplicate name
    if db.query(Location).filter(Location.name == payload.name).first():
        raise HTTPException(status_code=400, detail="A location with this name already exists")

    loc = Location(**payload.model_dump())
    db.add(loc)
    db.flush()  # get loc.id

    if loc.is_navigable:
        # Auto-create a graph node for this location
        node = GraphNode(
            location_id=loc.id,
            node_type="location",
            floor=loc.floor,
            lat=loc.latitude,
            lng=loc.longitude,
            indoor_x=loc.indoor_x,
            indoor_y=loc.indoor_y,
            label=loc.name,
        )
        db.add(node)
        db.flush()
        loc.node_id = node.id
        invalidate_graph_cache()

    db.commit()
    db.refresh(loc)
    return loc


@router.put("/locations/{location_id}", response_model=LocationResponse)
def admin_update_location(
    location_id: int,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    _=Admin,
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(loc, key, value)

    # Sync the linked graph node's coordinates if they changed
    if loc.node_id:
        node = db.query(GraphNode).filter(GraphNode.id == loc.node_id).first()
        if node:
            if payload.latitude is not None:
                node.lat = payload.latitude
            if payload.longitude is not None:
                node.lng = payload.longitude
            if payload.indoor_x is not None:
                node.indoor_x = payload.indoor_x
            if payload.indoor_y is not None:
                node.indoor_y = payload.indoor_y
            if payload.floor is not None:
                node.floor = payload.floor
            if payload.name is not None:
                node.label = payload.name

    # If is_navigable was just switched ON and there's no node yet, create one
    if loc.is_navigable and not loc.node_id:
        node = GraphNode(
            location_id=loc.id,
            node_type="location",
            floor=loc.floor,
            lat=loc.latitude,
            lng=loc.longitude,
            indoor_x=loc.indoor_x,
            indoor_y=loc.indoor_y,
            label=loc.name,
        )
        db.add(node)
        db.flush()
        loc.node_id = node.id

    invalidate_graph_cache()
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/locations/{location_id}", status_code=204)
def admin_delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _=Admin,
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    # Remove linked node (cascades to edges)
    if loc.node_id:
        node = db.query(GraphNode).filter(GraphNode.id == loc.node_id).first()
        if node:
            db.delete(node)

    db.delete(loc)
    invalidate_graph_cache()
    db.commit()


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------

@router.get("/nodes", response_model=List[GraphNodeResponse])
def admin_list_nodes(db: Session = Depends(get_db), _=Admin):
    return db.query(GraphNode).order_by(GraphNode.id).all()


@router.post("/nodes", response_model=GraphNodeResponse, status_code=201)
def admin_create_node(
    payload: GraphNodeCreate,
    db: Session = Depends(get_db),
    _=Admin,
):
    node = GraphNode(**payload.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    invalidate_graph_cache()
    return node


@router.delete("/nodes/{node_id}", status_code=204)
def admin_delete_node(node_id: int, db: Session = Depends(get_db), _=Admin):
    node = db.query(GraphNode).filter(GraphNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Unlink any location pointing to this node
    db.query(Location).filter(Location.node_id == node_id).update({"node_id": None})
    db.delete(node)
    invalidate_graph_cache()
    db.commit()


# ---------------------------------------------------------------------------
# Graph Edges
# ---------------------------------------------------------------------------

@router.get("/edges", response_model=List[GraphEdgeResponse])
def admin_list_edges(db: Session = Depends(get_db), _=Admin):
    return db.query(GraphEdge).order_by(GraphEdge.id).all()


@router.post("/edges", response_model=GraphEdgeResponse, status_code=201)
def admin_create_edge(
    payload: GraphEdgeCreate,
    db: Session = Depends(get_db),
    _=Admin,
):
    # Verify nodes exist
    for nid in (payload.from_node_id, payload.to_node_id):
        if not db.query(GraphNode).filter(GraphNode.id == nid).first():
            raise HTTPException(status_code=404, detail=f"Node {nid} not found")

    edge = GraphEdge(**payload.model_dump())
    db.add(edge)
    db.commit()
    db.refresh(edge)
    invalidate_graph_cache()
    return edge


@router.delete("/edges/{edge_id}", status_code=204)
def admin_delete_edge(edge_id: int, db: Session = Depends(get_db), _=Admin):
    edge = db.query(GraphEdge).filter(GraphEdge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    invalidate_graph_cache()
    db.commit()


# ---------------------------------------------------------------------------
# Full graph dump (for admin UI visualisation)
# ---------------------------------------------------------------------------

@router.get("/graph", response_model=GraphDump)
def admin_get_graph(db: Session = Depends(get_db), _=Admin):
    nodes = db.query(GraphNode).all()
    edges = db.query(GraphEdge).all()
    return GraphDump(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Users (admin management)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
def admin_list_users(db: Session = Depends(get_db), _=Admin):
    return db.query(User).all()


@router.post("/users", response_model=UserResponse, status_code=201)
def admin_create_user(payload: UserCreate, db: Session = Depends(get_db), _=Admin):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
