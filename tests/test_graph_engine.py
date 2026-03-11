import unittest
import sys
import sqlite3
import json
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from graph_engine import GraphEngine

class TestGraphEngine(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_logic.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE logic_registry (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name   TEXT    NOT NULL,
                node_type   TEXT    NOT NULL,
                source_file TEXT    NOT NULL,
                line_start  INTEGER,
                line_end    INTEGER,
                docstring   TEXT,
                logic_calls TEXT,
                metadata    TEXT,
                synced_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(node_name, source_file)
            )
        """)
        
        # Seed data
        data = [
            ("A", "function", "f1.py", '["B", "C"]'),
            ("B", "function", "f2.py", '["C"]'),
            ("C", "function", "f3.py", '[]'),
            ("D", "function", "f4.py", '[]'), # Orphan
            ("E", "function", "f5.py", '["F"]'), # Cycle
            ("F", "function", "f6.py", '["E"]')  # Cycle
        ]
        for name, ntype, file, calls in data:
            self.conn.execute(
                "INSERT INTO logic_registry (node_name, node_type, source_file, logic_calls) VALUES (?, ?, ?, ?)",
                (name, ntype, file, calls)
            )
        self.conn.commit()
        self.engine = GraphEngine(db_path=self.db_path)
        self.engine.load_graph()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_upstream_downstream(self):
        # A -> B -> C
        # A -> C
        self.assertIn("B", self.engine.get_downstream("A"))
        self.assertIn("C", self.engine.get_downstream("A"))
        self.assertIn("A", self.engine.get_upstream("B"))
        self.assertIn("A", self.engine.get_upstream("C"))
        self.assertIn("B", self.engine.get_upstream("C"))

    def test_direct_deps(self):
        deps = self.engine.get_direct_dependencies("B")
        self.assertEqual(deps["callers"], ["A"])
        self.assertEqual(deps["callees"], ["C"])

    def test_cycles(self):
        cycles = self.engine.find_circular_dependencies()
        self.assertEqual(len(cycles), 1)
        self.assertEqual(sorted(cycles[0]), ["E", "F"])

    def test_orphans(self):
        orphans = self.engine.find_orphans()
        self.assertEqual(orphans, ["D"])

if __name__ == "__main__":
    unittest.main()
