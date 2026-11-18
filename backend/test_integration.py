"""
test_integration.py - Full integration test using SQLite (no PostgreSQL needed).
Run: python test_integration.py
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///./dypcoe_integration.db"

from app.database import engine, Base, SessionLocal
import app.models  # register models
Base.metadata.create_all(bind=engine)
print("[test] Tables created OK")

# Run seed
from seed import seed
seed()

# Test queries
db = SessionLocal()
from app.models import Location, GraphNode, GraphEdge, User

nloc  = db.query(Location).count()
nnode = db.query(GraphNode).count()
nedge = db.query(GraphEdge).count()
nuser = db.query(User).count()
print(f"[test] Locations: {nloc}, Nodes: {nnode}, Edges: {nedge}, Users: {nuser}")

assert nloc >= 32,  f"Expected >=32 locations, got {nloc}"
assert nnode >= 32, f"Expected >=32 nodes, got {nnode}"
assert nedge >= 20, f"Expected >=20 edges, got {nedge}"
assert nuser >= 1,  f"Expected >=1 user, got {nuser}"

# Test navigation — CE-101 Networking Lab to CE-201 AI/ML Lab (cross-floor indoor)
lab1 = db.query(Location).filter(Location.name.contains("CE-101")).first()
lab2 = db.query(Location).filter(Location.name.contains("CE-201")).first()
print(f"[test] From: {lab1.name if lab1 else 'NOT FOUND'} (node_id={lab1.node_id if lab1 else None})")
print(f"[test] To:   {lab2.name if lab2 else 'NOT FOUND'} (node_id={lab2.node_id if lab2 else None})")

# Test Dijkstra
from app.services.pathfinding import build_graph, dijkstra, calculate_eta, generate_step_instructions
graph = build_graph(db)
print(f"[test] Graph has {len(graph)} nodes")

if lab1 and lab2 and lab1.node_id and lab2.node_id:
    path, dist = dijkstra(graph, lab1.node_id, lab2.node_id)
    eta = calculate_eta(dist)
    nodes = db.query(GraphNode).filter(GraphNode.id.in_(path)).all()
    nm    = {n.id: n for n in nodes}
    ordered = [nm[nid] for nid in path if nid in nm]
    steps = generate_step_instructions(ordered, lab1, lab2)
    print(f"[test] Path node IDs: {path}")
    print(f"[test] Distance: {dist:.1f}m, ETA: {eta['eta_text']}")
    print("[test] Step-by-step:")
    for s in steps:
        print(f"       - {s}")
    assert dist > 0, "Distance must be > 0"
    assert len(steps) >= 2, "Must have at least 2 steps"
else:
    print("[test] WARN: One or both locations missing node_id — checking all locations...")
    for loc in db.query(Location).all():
        print(f"       {loc.name!r}: node_id={loc.node_id}")
    raise AssertionError("CE-101 or CE-201 missing node_id")

# Test outdoor route calculation (straight-line, no Google Maps key)
main_gate = db.query(Location).filter(Location.name == "Main Gate").first()
library   = db.query(Location).filter(Location.name == "Library").first()
print(f"[test] Outdoor: {main_gate.name} → {library.name}")
assert main_gate.latitude and main_gate.longitude, "Main Gate missing coords"
assert library.latitude  and library.longitude,  "Library missing coords"
import math
dlat = (library.latitude  - main_gate.latitude)  * 111320
dlng = (library.longitude - main_gate.longitude) * 111320 * math.cos(math.radians(main_gate.latitude))
straight = math.sqrt(dlat**2 + dlng**2)
print(f"[test] Straight-line Main Gate→Library: {straight:.0f}m")
assert 50 < straight < 2000, f"Implausible distance: {straight}"

# Test admin user password
from app.security import verify_password
admin_user = db.query(User).filter(User.email == "admin@dypcoe.ac.in").first()
assert admin_user, "Admin user not found"
assert verify_password("dypcoe@2024", admin_user.hashed_password), "Admin password verification failed"
print("[test] Admin login OK")

db.close()
print("\n[integration] ✅ ALL TESTS PASSED")
