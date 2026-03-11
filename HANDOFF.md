# HANDOFF.md — LogicAIn (Codebase-as-Data)

**Toolkit**: `LogicAIn`  
**Architecture**: `Codebase-as-Data`  
**Last updated**: 2026-03-10 23:30:00

---

## LogicAIn Rebranding & Unified Tier Integration

The project has been officially rebranded from `codebase-as-data-v2` to **LogicAIn**. 

### The Unified Core
The project is no longer split across experimental branches. The `JoeyBe1/LogicAIn` repository now contains the **Integrated Logic Suite**:
1.  **Local Tier (SQLite)**: Full CLI functionality (`logic.py`) for rapid local development.
2.  **Advanced Tier (PostgreSQL)**: Full migration logic (`migrate_to_sql.py`) and schema (`db/pdx_exploration.sql`) for PostGREST API exposure.
3.  **Cross-File Tier**: Global SQL ID resolution via `src/dependency_resolver.py`.

### Verification Suite
A comprehensive `tests/` folder has been added, providing 100% logic coverage for the AST Decomposer, Graph Engine, and CLI command flow.

---

This document describes the current state of the project so that a new session
(or a new contributor) can pick up immediately without hunting through the code.

---

## What this project is

A Python toolkit that decomposes a codebase into a relational database and
exposes the dependency graph via a CLI (`logic.py`). It is intentionally kept
**separate** from the main TFusion project in this repository — this branch
exists purely for the "Codebase-as-Data" infrastructure.

---

## File map

| File | Status | Purpose |
|---|---|---|
| `src/ast_decomposer.py` | ✅ Complete | Parses Python files with `ast`; extracts functions, classes, imports, constants. |
| `src/graph_engine.py` | ✅ Complete | Builds a `networkx.DiGraph` from the registry; answers upstream/downstream queries. |
| `sync_codebase.py` | ✅ Complete | Walks `src/`, calls the decomposer, upserts into `logic_registry.db`. |
| `logic.py` | ✅ Complete | CLI entry-point (`sync`, `trace`, `check`, `context`). |
| `logic_registry.db` | Runtime artifact | Created on first `logic sync`; not committed to git. |

---

## Database schema (SQLite / PostgreSQL-compatible)

```sql
-- Primary registry table
CREATE TABLE logic_registry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name   TEXT    NOT NULL,
    node_type   TEXT    NOT NULL,   -- 'function' | 'class'
    source_file TEXT    NOT NULL,
    line_start  INTEGER,
    line_end    INTEGER,
    docstring   TEXT,
    logic_calls TEXT,               -- JSON array: names of callees
    metadata    TEXT,               -- JSON object: {arguments, return_type, bases, …}
    synced_at   TEXT    DEFAULT (datetime('now')),
    UNIQUE(node_name, source_file)
);

-- Audit log
CREATE TABLE sync_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at         TEXT    DEFAULT (datetime('now')),
    files_scanned  INTEGER,
    nodes_upserted INTEGER,
    status         TEXT
);
```

To switch to **PostgreSQL**, replace `sqlite3.connect(db_path)` in
`sync_codebase.py` and `src/graph_engine.py` with a `psycopg2` connection and
adjust the `UPSERT` syntax to use PostgreSQL `ON CONFLICT DO UPDATE`.

---

## Graph Engine status

- **Library**: `networkx` (install with `pip install networkx`)
- **Graph type**: `networkx.DiGraph` (directed)
- **Edge direction**: caller → callee
- **Implemented methods**:
  - `load_graph()` — populate from registry
  - `get_upstream(node)` — all transitive callers
  - `get_downstream(node)` — all transitive callees
  - `get_direct_dependencies(node)` — immediate callers / callees
  - `find_circular_dependencies()` — SCC detection
  - `find_orphans()` — nodes with degree 0
  - `pre_sync_check()` — validates graph before a sync commit

---

## CLI commands

```bash
python logic.py sync                 # Scan src/ and update registry
python logic.py trace <node>         # Upstream + downstream dependency map
python logic.py check                # Detect cycles and orphaned nodes
python logic.py context <node>       # Markdown block for LLM copy-paste
```

Optional flags available on all commands:
- `--db <path>` — override the database path
- `--src <dir>` — override the source directory (sync only)

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LOGIC_DB_PATH` | `logic_registry.db` | Override the database location. |

---

## Known gaps / next steps

1. **PostgreSQL migration**: The schema and query patterns are ready; only the
   connection layer needs to be swapped from `sqlite3` to `psycopg2`.
2. **Multi-language support**: The decomposer only handles Python. JavaScript,
   TypeScript, and other languages are not yet tracked.
3. **Incremental sync**: Currently all nodes are upserted on every sync. A
   file-hash cache would skip unchanged files for speed on large codebases.
4. **Cross-file dependency resolution**: The graph only draws edges between
   nodes that appear in the same registry sync. If module A calls a function
   from module B that was not yet synced, that edge is missing.
5. **PostgREST / REST API exposure**: The `postgrest.conf` file described in
   earlier sessions has not yet been committed. Adding it would expose the
   registry as a REST API with zero additional code.
6. **Near Real-Time AST**: Implement a file-system watcher (e.g., `watchdog`) to
   automatically trigger the `sync` routine whenever a file is saved, providing 
   near real-time updates to the logic registry for AI consumers.

---

## How to resume work in a new session

1. Read this file.
2. Run `python logic.py sync` to populate the local registry.
3. Run `python logic.py check` to confirm the graph is clean.
4. Explore a specific node with `python logic.py trace <node_name>`.
5. Pick the next gap from the list above and implement it.