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
