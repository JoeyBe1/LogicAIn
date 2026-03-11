#!/usr/bin/env python3
"""
logic.py — Command-line interface for the Codebase-as-Data Logic Registry.

Commands
--------
  sync                  Scan src/ and update the logic_registry database.
  trace <node>          Show all upstream and downstream dependencies for a node.
  check                 Report circular dependencies and orphaned logic nodes.
  context <node>        Print a Markdown block with source code and dependencies
                        for a node and its immediate dependencies. Ideal for
                        copy-pasting into an LLM prompt.

Environment
-----------
  LOGIC_DB_PATH         Path to the SQLite database (default: logic_registry.db)

Usage examples
--------------
  python logic.py sync
  python logic.py trace MyClass
  python logic.py check
  python logic.py context my_function
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from graph_engine import GraphEngine  # noqa: E402
from sync_codebase import run_sync, SRC_DIR  # noqa: E402

DB_PATH = os.environ.get("LOGIC_DB_PATH", "logic_registry.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_graph(db_path: str = DB_PATH) -> GraphEngine:
    engine = GraphEngine(db_path=db_path)
    engine.load_graph()
    return engine


def _fetch_node_record(node_name: str, db_path: str = DB_PATH) -> dict | None:
    """Return the first registry row for *node_name*, or None if not found."""
    conn = _get_db_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM logic_registry WHERE node_name = ? ORDER BY id LIMIT 1",
            (node_name,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_sync(args: argparse.Namespace) -> int:
    db_path = args.db or DB_PATH
    src_dir = Path(args.src) if args.src else SRC_DIR
    print(f"Syncing {src_dir} → {db_path} …")
    summary = run_sync(src_dir=src_dir, db_path=db_path)
    print(
        f"Sync complete. "
        f"{summary['files_scanned']} file(s) scanned, "
        f"{summary['nodes_upserted']} node(s) upserted."
    )
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    db_path = args.db or DB_PATH
    node = args.node

    if not Path(db_path).exists():
        print(
            f"Error: registry not found at '{db_path}'. Run 'logic sync' first.",
            file=sys.stderr,
        )
        return 1

    engine = _load_graph(db_path)

    if not engine.node_exists(node):
        print(f"Error: node '{node}' not found in the registry.", file=sys.stderr)
        return 1

    upstream = engine.get_upstream(node)
    downstream = engine.get_downstream(node)
    direct = engine.get_direct_dependencies(node)

    print(f"\nTrace: {node}")
    print("=" * (len(node) + 7))

    print(f"\nDirect callers  ({len(direct['callers'])} found):")
    for n in sorted(direct["callers"]) or ["  (none)"]:
        print(f"  ↑ {n}")

    print(f"\nDirect callees  ({len(direct['callees'])} found):")
    for n in sorted(direct["callees"]) or ["  (none)"]:
        print(f"  ↓ {n}")

    print(f"\nAll upstream (transitive)  ({len(upstream)} found):")
    for n in sorted(upstream) or ["  (none)"]:
        print(f"  ↑↑ {n}")

    print(f"\nAll downstream (transitive)  ({len(downstream)} found):")
    for n in sorted(downstream) or ["  (none)"]:
        print(f"  ↓↓ {n}")

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    db_path = args.db or DB_PATH

    if not Path(db_path).exists():
        print(
            f"Error: registry not found at '{db_path}'. Run 'logic sync' first.",
            file=sys.stderr,
        )
        return 1

    engine = _load_graph(db_path)
    cycles = engine.find_circular_dependencies()
    orphans = engine.find_orphans()

    exit_code = 0

    if cycles:
        print(f"\n⚠  Circular dependencies ({len(cycles)} found):")
        for cycle in cycles:
            print("  " + " ↔ ".join(cycle))
        exit_code = 1
    else:
        print("✓  No circular dependencies found.")

    if orphans:
        print(f"\n⚠  Orphaned nodes ({len(orphans)} found):")
        for node in orphans:
            print(f"  • {node}")
    else:
        print("✓  No orphaned nodes found.")

    return exit_code


def cmd_context(args: argparse.Namespace) -> int:
    db_path = args.db or DB_PATH
    node_name = args.node

    if not Path(db_path).exists():
        print(
            f"Error: registry not found at '{db_path}'. Run 'logic sync' first.",
            file=sys.stderr,
        )
        return 1

    engine = _load_graph(db_path)

    if not engine.node_exists(node_name):
        print(f"Error: node '{node_name}' not found in the registry.", file=sys.stderr)
        return 1

    # Gather the target node and its immediate dependencies.
    direct = engine.get_direct_dependencies(node_name)
    nodes_to_show = [node_name] + direct["callees"]

    lines = [f"# Logic Context: `{node_name}`\n"]

    for name in nodes_to_show:
        record = _fetch_node_record(name, db_path)
        meta = engine.get_node_metadata(name) or {}

        lines.append(f"## `{name}`")
        if record:
            lines.append(f"- **Type**: {record.get('node_type', 'unknown')}")
            lines.append(f"- **File**: `{record.get('source_file', 'unknown')}`")
            if record.get("line_start"):
                lines.append(
                    f"- **Lines**: {record['line_start']}–{record.get('line_end', record['line_start'])}"
                )
            if record.get("docstring") and record["docstring"] != "MISSING":
                lines.append(f"- **Docstring**: {record['docstring']}")

            raw_meta = record.get("metadata")
            if raw_meta:
                try:
                    parsed_meta = json.loads(raw_meta)
                    if parsed_meta.get("arguments"):
                        arg_str = ", ".join(
                            f"{a['name']}: {a['type']}" for a in parsed_meta["arguments"]
                        )
                        lines.append(f"- **Arguments**: `{arg_str}`")
                    if parsed_meta.get("return_type") and parsed_meta["return_type"] != "MISSING":
                        lines.append(f"- **Returns**: `{parsed_meta['return_type']}`")
                except (json.JSONDecodeError, TypeError):
                    pass

            raw_calls = record.get("logic_calls")
            if raw_calls:
                try:
                    calls = json.loads(raw_calls)
                    if calls:
                        lines.append(f"- **Calls**: `{'`, `'.join(calls)}`")
                except (json.JSONDecodeError, TypeError):
                    pass

        direct_deps = engine.get_direct_dependencies(name)
        if direct_deps["callers"]:
            lines.append(
                f"- **Called by**: `{'`, `'.join(sorted(direct_deps['callers']))}`"
            )

        lines.append("")  # blank line between nodes

    print("\n".join(lines))
    return 0


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logic",
        description="Codebase-as-Data CLI — interact with the logic registry without writing SQL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help=f"Path to the logic registry database (default: {DB_PATH})",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync
    p_sync = subparsers.add_parser("sync", help="Scan src/ and update the logic registry.")
    p_sync.add_argument(
        "--src",
        metavar="DIR",
        help="Directory to scan (default: src/)",
        default=None,
    )
    p_sync.set_defaults(func=cmd_sync)

    # trace
    p_trace = subparsers.add_parser(
        "trace",
        help="Show upstream and downstream dependencies for a node.",
    )
    p_trace.add_argument("node", help="Name of the function or class to trace.")
    p_trace.set_defaults(func=cmd_trace)

    # check
    p_check = subparsers.add_parser(
        "check",
        help="Report circular dependencies and orphaned logic nodes.",
    )
    p_check.set_defaults(func=cmd_check)

    # context
    p_context = subparsers.add_parser(
        "context",
        help="Output a Markdown context block for a node and its immediate dependencies.",
    )
    p_context.add_argument("node", help="Name of the function or class.")
    p_context.set_defaults(func=cmd_context)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
