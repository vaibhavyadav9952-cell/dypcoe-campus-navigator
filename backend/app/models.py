"""
models.py - SQLAlchemy ORM models for DYPCOE Smart Campus Navigator.

Tables (creation order avoids circular FK):
  1. graph_nodes  - waypoints / corridor junctions (FK to locations via use_alter)
  2. locations    - all campus POIs (FK to graph_nodes via use_alter)
  3. graph_edges  - undirected connections between graph_nodes
  4. users        - admin accounts
  5. chat_history - AI chat logs
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# GraphNode — created before Location so the circular FK is handled safely
# ---------------------------------------------------------------------------
class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, index=True)

    # Back-ref to the Location this node represents (NULL for corridor junctions)
    location_id = Column(
        Integer,
        ForeignKey("locations.id", use_alter=True, name="fk_graphnode_location",
                   ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    node_type = Column(
        String(32), nullable=False, default="junction",
        # location | corridor | staircase | elevator | junction | entrance | outdoor
    )
    floor    = Column(Integer, nullable=True)   # 0=ground, None=outdoor
    lat      = Column(Float,   nullable=True)   # WGS-84 latitude
    lng      = Column(Float,   nullable=True)   # WGS-84 longitude
    indoor_x = Column(Float,   nullable=True)   # 0-100 on floor-plan image
    indoor_y = Column(Float,   nullable=True)   # 0-100 on floor-plan image
    label    = Column(String(255), nullable=True)

    # Relationships — no back_populates here; Location.graph_node_ref uses post_update
    location = relationship(
        "Location",
        foreign_keys=[location_id],
        primaryjoin="GraphNode.location_id == Location.id",
        # NOTE: no back_populates to avoid circular direction conflict
    )
    outgoing_edges = relationship(
        "GraphEdge", foreign_keys="GraphEdge.from_node_id",
        back_populates="from_node", cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "GraphEdge", foreign_keys="GraphEdge.to_node_id",
        back_populates="to_node", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<GraphNode id={self.id} type={self.node_type!r} label={self.label!r}>"


# ---------------------------------------------------------------------------
# Location — primary table of campus points of interest
# ---------------------------------------------------------------------------
class Location(Base):
    __tablename__ = "locations"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False, unique=True, index=True)
    category    = Column(String(64),  nullable=True, index=True)
    # e.g. lab | classroom | office | cafeteria | library | hostel | sports |
    #      entrance | restroom | medical | admin | auditorium | workshop | parking
    building    = Column(String(128), nullable=True, index=True)
    floor       = Column(Integer, nullable=True)   # 0=ground, None=outdoor
    room_number = Column(String(32),  nullable=True)
    latitude    = Column(Float, nullable=True)
    longitude   = Column(Float, nullable=True)
    indoor_x    = Column(Float, nullable=True)  # 0-100
    indoor_y    = Column(Float, nullable=True)  # 0-100
    description = Column(Text, nullable=True)
    is_navigable = Column(Boolean, default=True, nullable=False)

    # FK to the representative GraphNode — deferred to avoid circular issue
    node_id = Column(
        Integer,
        ForeignKey("graph_nodes.id", use_alter=True, name="fk_location_node",
                   ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    # Relationship to the representative graph node — no back_populates (see GraphNode)
    graph_node_ref = relationship(
        "GraphNode",
        foreign_keys=[node_id],
        primaryjoin="Location.node_id == GraphNode.id",
        post_update=True,
    )

    def __repr__(self):
        return f"<Location id={self.id} name={self.name!r} building={self.building!r}>"


# ---------------------------------------------------------------------------
# GraphEdge — undirected weighted connection between two GraphNodes
# ---------------------------------------------------------------------------
class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", name="uq_edge_direction"),
    )

    id           = Column(Integer, primary_key=True, index=True)
    from_node_id = Column(Integer, ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    to_node_id   = Column(Integer, ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    weight       = Column(Float, nullable=False, default=1.0)   # metres
    is_indoor    = Column(Boolean, default=True, nullable=False)
    is_accessible = Column(Boolean, default=True, nullable=False)
    edge_type    = Column(String(32), nullable=False, default="corridor")
    # corridor | staircase | elevator | outdoor_path

    from_node = relationship("GraphNode", foreign_keys=[from_node_id],
                             back_populates="outgoing_edges")
    to_node   = relationship("GraphNode", foreign_keys=[to_node_id],
                             back_populates="incoming_edges")

    def __repr__(self):
        return (f"<GraphEdge id={self.id} "
                f"{self.from_node_id}→{self.to_node_id} "
                f"w={self.weight}m type={self.edge_type}>")


# ---------------------------------------------------------------------------
# User — admin accounts
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_admin        = Column(Boolean, default=False, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r} admin={self.is_admin}>"


# ---------------------------------------------------------------------------
# ChatHistory — optional AI conversation logs
# ---------------------------------------------------------------------------
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(String(64),  nullable=True,  index=True)
    user_query  = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ChatHistory id={self.id}>"
