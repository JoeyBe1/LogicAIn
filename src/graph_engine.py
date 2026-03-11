import json
import sqlite3
from typing import Dict, List, Optional, Tuple

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class GraphEngine:
    """
    Builds and queries a directed dependency graph from the logic_registry.
    Supports upstream/downstream tracing, circular dependency detection,
    and orphan node identification.
    """

    def __init__(self, db_path: str = "logic_registry.db"):
        self.db_path = db_path
        if not HAS_NETWORKX:
            raise ImportError(
                "networkx is required. Install it with: pip install networkx"
            )
        self.graph: nx.DiGraph = nx.DiGraph()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_graph(self) -> None:
        """
        Builds a directed graph from the logic_registry table.
        Each node is a logic unit (function or class).
        Each edge represents a call/dependency relationship.
        """
        self.graph.clear()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_name, node_type, source_file, logic_calls FROM logic_registry"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        known_names = set()
        edges = []

        for row in rows:
            name = row["node_name"]
            known_names.add(name)
            self.graph.add_node(
                name,
                node_type=row["node_type"],
                source_file=row["source_file"],
            )
            raw_calls = row["logic_calls"]
            if raw_calls:
                try:
                    calls = json.loads(raw_calls)
                except (json.JSONDecodeError, TypeError):
                    calls = []
                for callee in calls:
                    edges.append((name, callee))

        for caller, callee in edges:
            if callee in known_names:
                self.graph.add_edge(caller, callee)

    def get_upstream(self, node_name: str) -> List[str]:
        """Returns all nodes that depend on (call) the given node."""
        if node_name not in self.graph:
            return []
        return list(nx.ancestors(self.graph, node_name))

    def get_downstream(self, node_name: str) -> List[str]:
        """Returns all nodes that the given node depends on (calls)."""
        if node_name not in self.graph:
            return []
        return list(nx.descendants(self.graph, node_name))

    def get_direct_dependencies(self, node_name: str) -> Dict[str, List[str]]:
        """Returns the immediate callers and callees for a node."""
        if node_name not in self.graph:
            return {"callers": [], "callees": []}
        return {
            "callers": list(self.graph.predecessors(node_name)),
            "callees": list(self.graph.successors(node_name)),
        }

    def find_circular_dependencies(self) -> List[List[str]]:
        """Returns all strongly connected components with more than one node (cycles)."""
        cycles = []
        for component in nx.strongly_connected_components(self.graph):
            if len(component) > 1:
                cycles.append(sorted(component))
        return cycles

    def find_orphans(self) -> List[str]:
        """
        Returns nodes with no callers and no callees — isolated logic units
        that are not referenced by anything and do not reference anything.
        """
        orphans = []
        for node in self.graph.nodes:
            if self.graph.in_degree(node) == 0 and self.graph.out_degree(node) == 0:
                orphans.append(node)
        return sorted(orphans)

    def pre_sync_check(self) -> Tuple[bool, str]:
        """
        Validates the current graph structure before a sync operation.
        Returns (is_valid, message).
        """
        cycles = self.find_circular_dependencies()
        if cycles:
            cycle_list = "; ".join([" -> ".join(c) for c in cycles])
            return False, f"Circular dependencies detected: {cycle_list}"
        return True, "Graph structure is valid."

    def node_exists(self, node_name: str) -> bool:
        return node_name in self.graph

    def get_node_metadata(self, node_name: str) -> Optional[Dict]:
        if node_name not in self.graph:
            return None
        data = dict(self.graph.nodes[node_name])
        data["name"] = node_name
        return data
