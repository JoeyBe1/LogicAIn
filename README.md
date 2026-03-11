# LogicAIn

LogicAIn is a high-fidelity toolkit that implements the **Codebase-as-Data architecture**.
It turns a Python codebase into a queryable data graph, decomposing every function 
and class into a SQL registry, mapping the dependencies between them, and exposing 
the entire structure through a single CLI tool—no manual SQL required.

---

## What it does

| Layer | File | Purpose |
|---|---|---|
| AST Decomposer | `src/ast_decomposer.py` | Parses Python files and extracts every function, class, import, and constant. |
| Graph Engine | `src/graph_engine.py` | Builds a `networkx` directed graph from the registry and answers dependency queries. |
| Sync Script | `sync_codebase.py` | Walks `src/`, decomposes each file, and writes the results to `logic_registry.db`. |
| CLI | `logic.py` | Single entry-point for all registry operations (no SQL needed). |

---

## Quick Start

### 1. Install dependencies

```bash
pip install networkx
```

### 2. Sync your codebase into the registry

```bash
python logic.py sync
```

Scans `src/`, decomposes every `.py` file, and upserts all logic nodes into
`logic_registry.db`.

---

## Commands

### `logic sync`

```bash
python logic.py sync
# optional overrides:
python logic.py sync --src ./my_src --db /tmp/my_registry.db
```

Scans the source directory and updates the registry.

---

### `logic trace <node>`

```bash
python logic.py trace ASTDecomposer
```

Prints all **direct** and **transitive** callers and callees for the named
function or class.

```
Trace: ASTDecomposer
====================

Direct callers  (1 found):
  ↑ run_sync

Direct callees  (3 found):
  ↓ get_full_decomposition
  ...
```

---

### `logic check`

```bash
python logic.py check
```

Reports:
- **Circular dependencies** — code that loops back on itself.
- **Orphaned nodes** — functions or classes that are not called by anything
  and do not call anything.

Returns exit code `1` if any circular dependencies are found.

---

### `logic context <node>`

```bash
python logic.py context my_function
```

Outputs a **Markdown block** containing the node's metadata and its immediate
dependencies. Designed for copy-pasting into an LLM prompt.

```markdown
# Logic Context: `my_function`

## `my_function`
- **Type**: function
- **File**: `src/my_module.py`
- **Lines**: 42–58
- **Arguments**: `radius: float`
- **Returns**: `float`
- **Calls**: `helper_one`, `helper_two`
...
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LOGIC_DB_PATH` | `logic_registry.db` | Path to the SQLite registry database. |

---

## Database schema

The SQLite database (`logic_registry.db`) mirrors the target PostgreSQL schema:

```sql
CREATE TABLE logic_registry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name   TEXT    NOT NULL,
    node_type   TEXT    NOT NULL,   -- 'function' | 'class'
    source_file TEXT    NOT NULL,
    line_start  INTEGER,
    line_end    INTEGER,
    docstring   TEXT,
    logic_calls TEXT,               -- JSON array of callee names
    metadata    TEXT,               -- JSON object (args, return_type, …)
    synced_at   TEXT,
    UNIQUE(node_name, source_file)
);
```

Switching to PostgreSQL requires only changing the connection call in
`sync_codebase.py` and `src/graph_engine.py`.

---

## Branch

All work on this toolkit lives on the `codebase-as-data-v2` branch and is
intentionally kept separate from the main TFusion project.
