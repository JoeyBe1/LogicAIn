# LogicAIn Fix Plan — COMPLETE INSTRUCTIONS

## Owner: JoeyBe1
## Date: 2026-03-11
## Status: URGENT — 3 fixes + 2 new files needed

---

## RULES (NON-NEGOTIABLE)
- DO NOT delete ANY files
- DO NOT modify any file not listed below
- DO NOT redesign the architecture
- Match existing code style — human-readable, component-based
- Work ONE FILE AT A TIME, confirm each is done

---

## FILES THAT ARE WORKING (DO NOT TOUCH)
- `src/ast_decomposer.py` — WORKING
- `src/graph_engine.py` — WORKING
- `src/codegen.py` — LEAVE AS-IS
- `src/dependency_resolver.py` — LEAVE AS-IS
- `sync_codebase.py` — WORKING
- `logic.py` — WORKING
- `db/pdx_exploration.sql` — LEAVE AS-IS
- `tests/test_ast_decomposer.py` — WORKING
- `tests/test_graph_engine.py` — WORKING
- `tests/test_logic_cli.py` — WORKING

---

## FIX 1: `migrate_to_sql.py` (2 bugs)

### Bug A — Line 5: Bad import
BROKEN:
```python
from src.ast_decomposer import decompose_source
```
FIX:
```python
from src.ast_decomposer import ASTDecomposer
```

### Bug B — Line 43: Must use the class
BROKEN:
```python
logic = decompose_source(source)
```
FIX:
```python
decomposer = ASTDecomposer(source)
logic = decomposer.get_full_decomposition()
```

### Bug C — Line 61: Stray token `nhm`
BROKEN:
```python
(module_id, imp["module"], json.dumps(imp["names"]), imp["line" nhm]))
```
FIX:
```python
(module_id, imp["module"], json.dumps(imp["names"]), imp["line"])
```

### Bug D — Lines 69-70 and 74-75: Wrong key name for methods/functions
The ASTDecomposer returns `self_explanatory_name` not `name` for functions.
For methods (line 69-70), change `method["name"]` to `method["self_explanatory_name"]`
For functions (line 74-75), change `func["name"]` to `func["self_explanatory_name"]`

### COMPLETE FIXED FILE:
```python
import os
import sqlite3
import json
import hashlib
from src.ast_decomposer import ASTDecomposer

DB_PATH = "db/logic_registry.db"
SCHEMA_PATH = "db/schema.sql"

def get_file_sha256(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def init_db():
    if not os.path.exists("db"):
        os.makedirs("db")
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    return conn

def migrate():
    conn = init_db()
    cursor = conn.cursor()
    
src_dir = "src"
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                sha256 = get_file_sha256(file_path)
                
                # Check if already synced
                cursor.execute("SELECT id, sha256 FROM modules WHERE path = ?", (file_path,))
                row = cursor.fetchone()
                if row and row[1] == sha256:
                    print(f"Skipping {file_path}, no changes.")
                    continue
                
                with open(file_path, "r") as f:
                    source = f.read()
                
                decomposer = ASTDecomposer(source)
                logic = decomposer.get_full_decomposition()
                
                # Upsert module
                if row:
                    module_id = row[0]
                    cursor.execute("UPDATE modules SET sha256 = ?, last_synced = CURRENT_TIMESTAMP WHERE id = ?", (sha256, module_id))
                    # Clear old related data for fresh sync
                    cursor.execute("DELETE FROM imports WHERE module_id = ?", (module_id,))
                    cursor.execute("DELETE FROM functions WHERE module_id = ?", (module_id,))
                    cursor.execute("DELETE FROM classes WHERE module_id = ?", (module_id,))
                    cursor.execute("DELETE FROM constants WHERE module_id = ?", (module_id,))
                else:
                    cursor.execute("INSERT INTO modules (path, sha256) VALUES (?, ?)", (file_path, sha256))
                    module_id = cursor.lastrowid
                
                # Insert Imports
                for imp in logic["imports"]:
                    cursor.execute("INSERT INTO imports (module_id, imported_module, imported_names, line_number) VALUES (?, ?, ?, ?)",
                                   (module_id, imp["module"], json.dumps(imp["names"]), imp["line"]))
                
                # Insert Classes
                for cls in logic["classes"]:
                    cursor.execute("INSERT INTO classes (module_id, name, bases, docstring, line_number) VALUES (?, ?, ?, ?, ?)",
                                   (module_id, cls["name"], json.dumps(cls["bases"]), cls["docstring"], cls["line"]))
                    class_id = cursor.lastrowid
                    for method in cls["methods"]:
                        cursor.execute("INSERT INTO functions (module_id, class_id, name, arguments, return_type, docstring, logic_calls, line_start, line_end) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (module_id, class_id, method["self_explanatory_name"], json.dumps(method["arguments"]), method["return_type"], method["docstring"], json.dumps(method["logic_calls"]), method["line_start"], method["line_end"]))

                # Insert Top-level Functions
                for func in logic["functions"]:
                    cursor.execute("INSERT INTO functions (module_id, class_id, name, arguments, return_type, docstring, logic_calls, line_start, line_end) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)",
                                   (module_id, func["self_explanatory_name"], json.dumps(func["arguments"]), func["return_type"], func["docstring"], json.dumps(func["logic_calls"]), func["line_start"], func["line_end"]))
                
                # Insert Constants
                for const in logic["constants"]:
                    cursor.execute("INSERT INTO constants (module_id, name, value, line_number) VALUES (?, ?, ?, ?)",
                                   (module_id, const["name"], const["value"], const["line"]))
                
                print(f"Migrated {file_path} to SQL registry.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
```
---

## FIX 2: Create `db/schema.sql` (MISSING — migrate_to_sql.py crashes without it)

```sql
-- db/schema.sql
-- Normalized schema for the LogicAIn Codebase-as-Data registry.
-- Used by migrate_to_sql.py for the advanced cross-module pipeline.

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    sha256 TEXT,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    imported_module TEXT,
    imported_names TEXT,
    line_number INTEGER,
    FOREIGN KEY(module_id) REFERENCES modules(id)
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    bases TEXT,
    docstring TEXT,
    line_number INTEGER,
    FOREIGN KEY(module_id) REFERENCES modules(id)
);

CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    class_id INTEGER,
    name TEXT NOT NULL,
    arguments TEXT,
    return_type TEXT,
    docstring TEXT,
    logic_calls TEXT,
    line_start INTEGER,
    line_end INTEGER,
    resolved_logic_id INTEGER,
    FOREIGN KEY(module_id) REFERENCES modules(id),
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(resolved_logic_id) REFERENCES functions(id)
);

CREATE TABLE IF NOT EXISTS constants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    value TEXT,
    line_number INTEGER,
    FOREIGN KEY(module_id) REFERENCES modules(id)
);

CREATE TABLE IF NOT EXISTS dependency_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_function_id INTEGER NOT NULL,
    target_function_id INTEGER NOT NULL,
    call_type TEXT DEFAULT 'direct',
    FOREIGN KEY(source_function_id) REFERENCES functions(id),
    FOREIGN KEY(target_function_id) REFERENCES functions(id)
);
```

---

## FIX 3: Create `.gitignore` (MISSING)

```
__pycache__/
*.pyc
*.pyo
*.db
.env
.venv/
*.egg-info/
dist/
build/
.nuanced/
```

---

## FIX 4: `requirements.txt` — ALREADY DONE on fix/stabilize-foundation branch

Contents: `networkx>=3.0`

---

## VERIFICATION AFTER ALL FIXES

Run these commands to confirm everything works:
```bash
python -c "from src.ast_decomposer import ASTDecomposer; print('OK')"
python -c "from src.graph_engine import GraphEngine; print('OK')"
python -c "import migrate_to_sql; print('OK')"
python -m pytest tests/ -v
python logic.py sync --src src
python logic.py check
python migrate_to_sql.py
```

All must pass with zero errors.

---

## SUMMARY

| # | File | Action | Status |
|---|---|---|---|
| 1 | `migrate_to_sql.py` | Fix 4 bugs (import, class usage, nhm token, key names) | TODO |
| 2 | `db/schema.sql` | Create new file (exact SQL above) | TODO |
| 3 | `.gitignore` | Create new file | TODO |
| 4 | `requirements.txt` | Create new file | DONE |
| 5 | `PLAN.md` | This file | DONE |
