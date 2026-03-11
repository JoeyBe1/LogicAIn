"""
sync_codebase.py — Scans the src/ directory, decomposes each Python file via
the ASTDecomposer, and writes all logic units into the SQLite logic_registry.

The schema mirrors the PostgreSQL schema described in the project plan so that
swapping the backend to PostgreSQL requires only changing the connection call.

Usage:
    python sync_codebase.py
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ast_decomposer import ASTDecomposer  # noqa: E402

DB_PATH = os.environ.get("LOGIC_DB_PATH", "logic_registry.db")
SRC_DIR = Path(__file__).parent / "src"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS logic_registry (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            node_name   TEXT    NOT NULL,
            node_type   TEXT    NOT NULL,
            source_file TEXT    NOT NULL,
            line_start  INTEGER,
            line_end    INTEGER,
            docstring   TEXT,
            logic_calls TEXT,   -- JSON array of callee names
            metadata    TEXT,   -- JSON object (args, return_type, decorators, …)
            synced_at   TEXT    DEFAULT (datetime('now')),
            UNIQUE(node_name, source_file)
        );
        CREATE TABLE IF NOT EXISTS sync_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at      TEXT    DEFAULT (datetime('now')),
            files_scanned INTEGER,
            nodes_upserted INTEGER,
            status      TEXT
        );
        """
    )
    conn.commit()


def upsert_node(conn: sqlite3.Connection, node: dict) -> None:
    conn.execute(
        """
        INSERT INTO logic_registry
            (node_name, node_type, source_file, line_start, line_end,
             docstring, logic_calls, metadata, synced_at)
        VALUES
            (:node_name, :node_type, :source_file, :line_start, :line_end,
             :docstring, :logic_calls, :metadata, datetime('now'))
        ON CONFLICT(node_name, source_file) DO UPDATE SET
            node_type   = excluded.node_type,
            line_start  = excluded.line_start,
            line_end    = excluded.line_end,
            docstring   = excluded.docstring,
            logic_calls = excluded.logic_calls,
            metadata    = excluded.metadata,
            synced_at   = datetime('now')
        """,
        node,
    )


def decompose_file(filepath: Path) -> list:
    """
    Decompose a single Python file and return a flat list of node dicts
    ready for upsert into logic_registry.
    """
    source = filepath.read_text(encoding="utf-8")
    rel_path = str(filepath)

    try:
        decomposer = ASTDecomposer(source)
        data = decomposer.get_full_decomposition()
    except ValueError as exc:
        print(f"  [SKIP] {rel_path}: {exc}", file=sys.stderr)
        return []

    nodes = []

    for fn in data.get("functions", []):
        nodes.append(
            {
                "node_name": fn["self_explanatory_name"],
                "node_type": "function",
                "source_file": rel_path,
                "line_start": fn.get("line_start"),
                "line_end": fn.get("line_end"),
                "docstring": fn.get("docstring", ""),
                "logic_calls": json.dumps(fn.get("logic_calls", [])),
                "metadata": json.dumps(
                    {
                        "arguments": fn.get("arguments", []),
                        "return_type": fn.get("return_type", "MISSING"),
                    }
                ),
            }
        )

    for cls in data.get("classes", []):
        method_names = [m["self_explanatory_name"] for m in cls.get("methods", [])]
        nodes.append(
            {
                "node_name": cls["name"],
                "node_type": "class",
                "source_file": rel_path,
                "line_start": cls.get("line"),
                "line_end": cls.get("line"),
                "docstring": cls.get("docstring", ""),
                "logic_calls": json.dumps(method_names),
                "metadata": json.dumps({"bases": cls.get("bases", [])}),
            }
        )

    return nodes


def run_sync(src_dir: Path = SRC_DIR, db_path: str = DB_PATH) -> dict:
    """
    Main sync routine. Returns a summary dict with files_scanned and
    nodes_upserted.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    py_files = sorted(src_dir.rglob("*.py"))
    files_scanned = 0
    nodes_upserted = 0

    for filepath in py_files:
        files_scanned += 1
        nodes = decompose_file(filepath)
        for node in nodes:
            upsert_node(conn, node)
            nodes_upserted += 1

    conn.execute(
        "INSERT INTO sync_log (files_scanned, nodes_upserted, status) VALUES (?, ?, ?)",
        (files_scanned, nodes_upserted, "ok"),
    )
    conn.commit()
    conn.close()

    return {"files_scanned": files_scanned, "nodes_upserted": nodes_upserted}


if __name__ == "__main__":
    print(f"Syncing {SRC_DIR} → {DB_PATH} …")
    summary = run_sync()
    print(
        f"Done. {summary['files_scanned']} file(s) scanned, "
        f"{summary['nodes_upserted']} node(s) upserted."
    )
