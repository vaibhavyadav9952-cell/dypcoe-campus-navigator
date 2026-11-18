import heapq
import math
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Module-level graph cache
# ---------------------------------------------------------------------------
_graph_cache: Optional[Dict] = None


def invalidate_graph_cache() -> None:
    global _graph_cache
    _graph_cache = None


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(db: Session) -> Dict[int, List[Tuple[float, int]]]:
    """
    Returns adjacency list: {node_id: [(weight, neighbor_id), ...]}
    Edges are undirected — added in both directions.
    Result is cached at module level.
    """
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache

    from app.models import GraphEdge  # noqa: WPS433

    graph: Dict[int, List[Tuple[float, int]]] = {}
    edges = db.query(GraphEdge).all()

    for edge in edges:
        graph.setdefault(edge.from_node_id, [])
        graph.setdefault(edge.to_node_id, [])
        graph[edge.from_node_id].append((edge.weight, edge.to_node_id))
        graph[edge.to_node_id].append((edge.weight, edge.from_node_id))

    _graph_cache = graph
    return graph


# ---------------------------------------------------------------------------
# Dijkstra
# ---------------------------------------------------------------------------

def dijkstra(
    graph: Dict[int, List[Tuple[float, int]]],
    start_id: int,
    end_id: int,
) -> Tuple[List[int], float]:
    """
    Returns (ordered list of node IDs, total distance in meters).
    Raises ValueError if no path exists.
    """
    if start_id not in graph:
        raise ValueError(f"Start node {start_id} not in graph")
    if end_id not in graph:
        raise ValueError(f"End node {end_id} not in graph")

    dist: Dict[int, float] = {start_id: 0.0}
    prev: Dict[int, Optional[int]] = {start_id: None}
    heap: List[Tuple[float, int]] = [(0.0, start_id)]

    while heap:
        current_dist, current_node = heapq.heappop(heap)

        if current_node == end_id:
            break

        if current_dist > dist.get(current_node, math.inf):
            continue

        for weight, neighbor in graph.get(current_node, []):
            new_dist = current_dist + weight
            if new_dist < dist.get(neighbor, math.inf):
                dist[neighbor] = new_dist
                prev[neighbor] = current_node
                heapq.heappush(heap, (new_dist, neighbor))

    if end_id not in dist:
        raise ValueError(f"No path found between nodes {start_id} and {end_id}")

    # Reconstruct path
    path: List[int] = []
    node: Optional[int] = end_id
    while node is not None:
        path.append(node)
        node = prev.get(node)
    path.reverse()

    return path, dist[end_id]


# ---------------------------------------------------------------------------
# ETA calculation  (average walking speed 1.4 m/s ≈ 84 m/min)
# ---------------------------------------------------------------------------
WALKING_SPEED_MPS = 1.4


def calculate_eta(meters: float) -> dict:
    eta_seconds = int(meters / WALKING_SPEED_MPS)
    eta_minutes = max(1, round(eta_seconds / 60))
    return {
        "eta_seconds": eta_seconds,
        "eta_text": f"~{eta_minutes} min{'s' if eta_minutes != 1 else ''}",
    }


# ---------------------------------------------------------------------------
# Step-by-step instruction generator
# ---------------------------------------------------------------------------

def generate_step_instructions(
    path_nodes: list,  # list of GraphNode ORM objects
    start_loc,         # Location ORM object
    end_loc,           # Location ORM object
) -> List[str]:
    """
    Produces a human-readable list of navigation steps from a list of
    GraphNode ORM objects (which may have edge_type hints via their edges).
    """
    if not path_nodes:
        return [f"Go to {end_loc.name}"]

    steps: List[str] = []

    # Starting step
    if start_loc.floor is not None and start_loc.floor != 0:
        steps.append(f"Start at {start_loc.name} on Floor {start_loc.floor}")
    else:
        steps.append(f"Start at {start_loc.name}")

    prev_node = path_nodes[0]
    for i in range(1, len(path_nodes)):
        node = path_nodes[i]

        # Detect floor changes
        prev_floor = getattr(prev_node, "floor", None)
        curr_floor = getattr(node, "floor", None)

        if prev_floor is not None and curr_floor is not None and prev_floor != curr_floor:
            direction = "up" if curr_floor > prev_floor else "down"
            steps.append(
                f"Take stairs/elevator {direction} to Floor {curr_floor}"
            )

        prev_node = node

    # Ending step
    if end_loc.floor is not None and end_loc.floor != 0:
        steps.append(
            f"Arrive at {end_loc.name}"
            + (f" (Room {end_loc.room_number})" if getattr(end_loc, "room_number", None) else "")
            + f" on Floor {end_loc.floor}"
        )
    else:
        steps.append(
            f"Arrive at {end_loc.name}"
            + (f" (Room {end_loc.room_number})" if getattr(end_loc, "room_number", None) else "")
        )

    return steps
