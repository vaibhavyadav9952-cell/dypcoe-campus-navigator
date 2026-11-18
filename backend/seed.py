"""
seed.py - Comprehensive seed script for DYPCOE Smart Campus Navigator.
Seeds campus locations, graph nodes, edges, and admin user for PostgreSQL.

Run: python seed.py
     (from the backend/ directory with DATABASE_URL set in .env)
"""

import os
import sys

# Allow running from backend/ directly
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
import app.models  # noqa: register models

Base.metadata.create_all(bind=engine)

from app.models import Location, GraphNode, GraphEdge, User
from app.security import get_password_hash


def seed():
    db = SessionLocal()
    try:
        # Skip if already seeded
        if db.query(Location).count() > 0:
            print("[seed] Database already seeded — skipping.")
            return

        print("[seed] Seeding DYPCOE campus data...")

        # -----------------------------------------------------------------------
        # CAMPUS BUILDINGS & OUTDOOR LOCATIONS
        # Coordinates near DYPCOE Akurdi: 18.644838, 73.758234
        # -----------------------------------------------------------------------
        buildings = [
            # (name, category, building, floor, lat, lng, description)
            ("Main Gate", "entrance", "Campus", None, 18.6440, 73.7570,
             "Main entrance gate of DYPCOE campus on Old Mumbai-Pune Highway"),
            ("Main Building", "admin", "Main Building", 0, 18.6449, 73.7582,
             "Administrative building housing Principal's office, admin offices, and seminar halls"),
            ("Computer Engineering Department", "academic", "CE Building", 0, 18.6447, 73.7580,
             "Department of Computer Engineering — 4 floors, houses all CE labs and classrooms"),
            ("Mechanical Engineering Department", "academic", "Mechanical Block", 0, 18.6451, 73.7585,
             "Department of Mechanical Engineering with workshops and labs"),
            ("Civil Engineering Department", "academic", "Civil Block", 0, 18.6445, 73.7578,
             "Department of Civil Engineering"),
            ("Electronics & Telecom Department", "academic", "E&TC Block", 0, 18.6448, 73.7584,
             "Department of Electronics & Telecommunication Engineering"),
            ("Information Technology Department", "academic", "IT Block", 0, 18.6446, 73.7581,
             "Department of Information Technology"),
            ("Library", "library", "Library Building", 0, 18.6446, 73.7579,
             "Central library with reading halls, digital resources, and reference section"),
            ("Canteen", "cafeteria", "Canteen Block", 0, 18.6444, 73.7576,
             "Main campus canteen serving breakfast, lunch, and snacks"),
            ("Boys Hostel", "hostel", "Boys Hostel", 0, 18.6453, 73.7590,
             "On-campus boys hostel accommodation"),
            ("Girls Hostel", "hostel", "Girls Hostel", 0, 18.6442, 73.7574,
             "On-campus girls hostel accommodation"),
            ("Sports Ground", "sports", "Campus", None, 18.6455, 73.7592,
             "Main sports ground for cricket, football, and athletics"),
            ("Parking Area", "parking", "Campus", None, 18.6441, 73.7572,
             "Student and staff vehicle parking area near main gate"),
            ("Medical Center", "medical", "Main Building", 0, 18.6447, 73.7577,
             "Campus medical center / first-aid room"),
            ("Auditorium", "auditorium", "Main Building", 0, 18.6450, 73.7583,
             "Main auditorium for college events, seminars, and convocation"),
            ("Workshop Building", "workshop", "Workshop Block", 0, 18.6452, 73.7587,
             "Central workshop for all engineering practical work"),
            ("NSS / NCC Room", "office", "Main Building", 1, 18.6449, 73.7583,
             "NSS and NCC activity room"),
            ("Principal's Office", "office", "Main Building", 1, 18.6449, 73.7582,
             "Principal's office — first floor, Main Building"),
        ]

        # CE Building rooms (floors 0-3)
        ce_rooms = [
            # Ground Floor
            ("CE Reception / Info Desk", "office", "CE Building", 0, 18.6447, 73.7580,
             "Ground floor reception and information desk of CE Department", "G-00",
             50.0, 90.0),
            ("CE-G01 Data Structures Lab", "lab", "CE Building", 0, 18.6447, 73.7580,
             "Undergraduate lab for Data Structures and Algorithms practical", "G-01",
             20.0, 50.0),
            ("CE-G02 Classroom", "classroom", "CE Building", 0, 18.6447, 73.7580,
             "Ground floor classroom — capacity 60 students", "G-02",
             80.0, 50.0),
            # First Floor
            ("CE-101 Networking Lab", "lab", "CE Building", 1, 18.6447, 73.7580,
             "Computer Networking and Network Security lab with 40 workstations", "101",
             20.0, 40.0),
            ("CE-102 Programming Lab", "lab", "CE Building", 1, 18.6447, 73.7580,
             "Advanced programming lab — Python, Java, C++ practicals", "102",
             60.0, 40.0),
            ("CE-103 Classroom", "classroom", "CE Building", 1, 18.6447, 73.7580,
             "First floor classroom — capacity 60 students", "103",
             80.0, 70.0),
            ("CE Faculty Room", "office", "CE Building", 1, 18.6447, 73.7580,
             "Faculty room for CE department staff", "F-01",
             20.0, 80.0),
            # Second Floor
            ("CE-201 AI/ML Lab", "lab", "CE Building", 2, 18.6447, 73.7580,
             "Artificial Intelligence and Machine Learning research lab with GPU workstations", "201",
             20.0, 40.0),
            ("CE-202 Project Lab", "lab", "CE Building", 2, 18.6447, 73.7580,
             "Final year project lab — open 8am–8pm", "202",
             60.0, 40.0),
            ("CE-203 Seminar Room", "classroom", "CE Building", 2, 18.6447, 73.7580,
             "Seminar room for department presentations — capacity 40 students", "203",
             80.0, 60.0),
            ("CE HOD Office", "office", "CE Building", 2, 18.6447, 73.7580,
             "Head of Department office — Computer Engineering", "H-01",
             20.0, 80.0),
            # Third Floor
            ("CE Research Lab", "lab", "CE Building", 3, 18.6447, 73.7580,
             "Postgraduate research laboratory", "R-01",
             30.0, 40.0),
            ("CE Server Room", "office", "CE Building", 3, 18.6447, 73.7580,
             "Department server room — restricted access", "S-01",
             70.0, 40.0),
            ("CE-301 Classroom", "classroom", "CE Building", 3, 18.6447, 73.7580,
             "Third floor classroom — capacity 60 students", "301",
             80.0, 70.0),
        ]

        # -----------------------------------------------------------------------
        # Insert building/outdoor locations (no indoor_x/y)
        # -----------------------------------------------------------------------
        building_locs = {}
        for name, cat, building, floor, lat, lng, desc in buildings:
            loc = Location(
                name=name, category=cat, building=building, floor=floor,
                latitude=lat, longitude=lng, description=desc, is_navigable=True,
            )
            db.add(loc)
            db.flush()
            # Create graph node
            node = GraphNode(
                location_id=loc.id, node_type="location" if floor is not None else "entrance",
                floor=floor, lat=lat, lng=lng, label=name,
            )
            db.add(node)
            db.flush()
            loc.node_id = node.id
            building_locs[name] = (loc, node)

        # -----------------------------------------------------------------------
        # Insert CE Building rooms (with indoor_x/y)
        # -----------------------------------------------------------------------
        ce_room_nodes = {}
        for entry in ce_rooms:
            name, cat, building, floor, lat, lng, desc, room_no, ix, iy = entry
            loc = Location(
                name=name, category=cat, building=building, floor=floor,
                latitude=lat, longitude=lng,
                indoor_x=ix, indoor_y=iy,
                room_number=room_no,
                description=desc, is_navigable=True,
            )
            db.add(loc)
            db.flush()
            node = GraphNode(
                location_id=loc.id, node_type="location",
                floor=floor, lat=lat, lng=lng,
                indoor_x=ix, indoor_y=iy, label=name,
            )
            db.add(node)
            db.flush()
            loc.node_id = node.id
            ce_room_nodes[(floor, room_no)] = (loc, node)

        # -----------------------------------------------------------------------
        # Create corridor / staircase junction nodes for CE Building
        # -----------------------------------------------------------------------
        # Ground floor corridor
        g_corridor = GraphNode(node_type="corridor", floor=0, lat=18.6447, lng=73.7580,
                               indoor_x=50.0, indoor_y=50.0, label="CE Ground Floor Corridor")
        db.add(g_corridor); db.flush()

        # First floor corridor
        f1_corridor = GraphNode(node_type="corridor", floor=1, lat=18.6447, lng=73.7580,
                                indoor_x=50.0, indoor_y=50.0, label="CE First Floor Corridor")
        db.add(f1_corridor); db.flush()

        # Second floor corridor
        f2_corridor = GraphNode(node_type="corridor", floor=2, lat=18.6447, lng=73.7580,
                                indoor_x=50.0, indoor_y=50.0, label="CE Second Floor Corridor")
        db.add(f2_corridor); db.flush()

        # Third floor corridor
        f3_corridor = GraphNode(node_type="corridor", floor=3, lat=18.6447, lng=73.7580,
                                indoor_x=50.0, indoor_y=50.0, label="CE Third Floor Corridor")
        db.add(f3_corridor); db.flush()

        # Staircase nodes (connect floors)
        stair_g_f1 = GraphNode(node_type="staircase", floor=0, lat=18.6447, lng=73.7580,
                               indoor_x=50.0, indoor_y=10.0, label="CE Staircase G→1")
        db.add(stair_g_f1); db.flush()

        stair_f1_top = GraphNode(node_type="staircase", floor=1, lat=18.6447, lng=73.7580,
                                 indoor_x=50.0, indoor_y=10.0, label="CE Staircase 1→2")
        db.add(stair_f1_top); db.flush()

        stair_f2_top = GraphNode(node_type="staircase", floor=2, lat=18.6447, lng=73.7580,
                                 indoor_x=50.0, indoor_y=10.0, label="CE Staircase 2→3")
        db.add(stair_f2_top); db.flush()

        # CE Building entrance node
        ce_entrance = GraphNode(node_type="entrance", floor=0, lat=18.6447, lng=73.7580,
                                indoor_x=50.0, indoor_y=98.0, label="CE Building Entrance")
        db.add(ce_entrance); db.flush()

        # -----------------------------------------------------------------------
        # Create edges connecting CE Building internal graph
        # -----------------------------------------------------------------------
        def edge(a, b, w, etype="corridor", indoor=True):
            db.add(GraphEdge(from_node_id=a.id, to_node_id=b.id,
                             weight=w, edge_type=etype, is_indoor=indoor))

        # CE Building entrance ↔ ground corridor
        edge(ce_entrance, g_corridor, 8)
        # Staircase ground ↔ first floor
        edge(stair_g_f1, stair_f1_top, 10, "staircase")
        edge(g_corridor, stair_g_f1, 5)
        edge(f1_corridor, stair_f1_top, 5)
        # Staircase first ↔ second
        stair_f1_f2 = stair_f1_top  # reuse node — same staircase column
        edge(stair_f1_top, stair_f2_top, 10, "staircase")
        edge(f2_corridor, stair_f2_top, 5)
        # Staircase second ↔ third — dedicated node for 3rd floor stair landing
        stair_f3_top = GraphNode(node_type="staircase", floor=3, lat=18.6447, lng=73.7580,
                                 indoor_x=50.0, indoor_y=10.0, label="CE Staircase 3→Top")
        db.add(stair_f3_top); db.flush()
        edge(stair_f2_top, stair_f3_top, 10, "staircase")
        edge(f3_corridor, stair_f3_top, 5)

        # Ground floor rooms ↔ ground corridor
        for (fl, rm), (loc, node) in ce_room_nodes.items():
            if fl == 0:
                edge(node, g_corridor, 10)
            elif fl == 1:
                edge(node, f1_corridor, 10)
            elif fl == 2:
                edge(node, f2_corridor, 10)
            elif fl == 3:
                edge(node, f3_corridor, 10)

        # Connect outdoor CE building entrance to main campus locations
        ce_main_node = building_locs["Computer Engineering Department"][1]
        outdoor_edge_node = ce_entrance
        edge(ce_main_node, outdoor_edge_node, 20, "outdoor_path", False)

        # Connect main campus buildings via outdoor paths (approximate distances in metres)
        outdoor_paths = [
            ("Main Gate", "Main Building", 120),
            ("Main Gate", "Parking Area", 30),
            ("Main Building", "Library", 50),
            ("Main Building", "Computer Engineering Department", 80),
            ("Main Building", "Principal's Office", 10),
            ("Main Building", "Auditorium", 40),
            ("Main Building", "Medical Center", 30),
            ("Computer Engineering Department", "Information Technology Department", 60),
            ("Computer Engineering Department", "Electronics & Telecom Department", 90),
            ("Information Technology Department", "Library", 40),
            ("Library", "Canteen", 70),
            ("Canteen", "Sports Ground", 100),
            ("Civil Engineering Department", "Main Building", 100),
            ("Civil Engineering Department", "Library", 60),
            ("Mechanical Engineering Department", "Workshop Building", 50),
            ("Mechanical Engineering Department", "Main Building", 110),
            ("Boys Hostel", "Sports Ground", 80),
            ("Girls Hostel", "Main Gate", 60),
            ("NSS / NCC Room", "Principal's Office", 20),
        ]
        for a_name, b_name, dist in outdoor_paths:
            if a_name in building_locs and b_name in building_locs:
                a_node = building_locs[a_name][1]
                b_node = building_locs[b_name][1]
                # Avoid duplicate edge error
                existing = db.query(GraphEdge).filter(
                    ((GraphEdge.from_node_id == a_node.id) & (GraphEdge.to_node_id == b_node.id)) |
                    ((GraphEdge.from_node_id == b_node.id) & (GraphEdge.to_node_id == a_node.id))
                ).first()
                if not existing:
                    edge(a_node, b_node, dist, "outdoor_path", False)

        # -----------------------------------------------------------------------
        # Admin user
        # -----------------------------------------------------------------------
        if db.query(User).filter(User.email == "admin@dypcoe.ac.in").count() == 0:
            admin_user = User(
                email="admin@dypcoe.ac.in",
                hashed_password=get_password_hash("dypcoe@2024"),
                is_admin=True,
            )
            db.add(admin_user)

        db.commit()
        print(f"[seed] Done! Inserted {db.query(Location).count()} locations, "
              f"{db.query(GraphNode).count()} nodes, {db.query(GraphEdge).count()} edges.")

    except Exception as e:
        db.rollback()
        print(f"[seed] Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
