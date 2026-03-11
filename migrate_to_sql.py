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