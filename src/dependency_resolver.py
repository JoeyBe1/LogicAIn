import sqlite3
import json
import os

DB_PATH = "db/logic_registry.db"

class DependencyResolver:
    """
    Phase 2: Cross-Module Dependency Resolver.
    Resolves local logic calls to their globally unique SQL IDs in the registry.
    """
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def resolve_all(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Get all functions and their logic calls
        cursor.execute("SELECT id, module_id, logic_calls FROM functions")
        functions = cursor.fetchall()
        
        for func_id, module_id, calls_json in functions:
            logic_calls = json.loads(calls_json)
            if not logic_calls:
                continue
                
            # 2. Get imports for this module to map aliases
            cursor.execute("SELECT imported_module, imported_names FROM imports WHERE module_id = ?", (module_id,))
            module_imports = cursor.fetchall()
            
            # Map of name -> module_path
            import_map = {}
            for imp_mod, imp_names_json in module_imports:
                imp_names = json.loads(imp_names_json)
                for name in imp_names:
                    # Basic mapping: assumes module structure matches file path
                    # e.g., 'from utils import helper' -> { 'helper': 'src/utils.py' }
                    # This logic can be expanded for complex package structures
                    path = f"src/{imp_mod.replace('.', '/')}.py"
                    import_map[name] = path

            for call in logic_calls:
                target_id = None
                
                # Check if the call is an imported function
                if call in import_map:
                    target_path = import_map[call]
                    cursor.execute("""
                        SELECT f.id FROM functions f
                        JOIN modules m ON f.module_id = m.id
                        WHERE m.path = ? AND f.name = ?
                    """, (target_path, call))
                    res = cursor.fetchone()
                    if res:
                        target_id = res[0]
                
                # Check if it's a local function in the same module
                if not target_id:
                    cursor.execute("SELECT id FROM functions WHERE module_id = ? AND name = ?", (module_id, call))
                    res = cursor.fetchone()
                    if res:
                        target_id = res[0]

                if target_id:
                    # Update resolved_logic_id
                    cursor.execute("UPDATE functions SET resolved_logic_id = ? WHERE id = ?", (target_id, func_id))
                    
                    # Log in dependency_map
                    cursor.execute("""
                        INSERT INTO dependency_map (source_function_id, target_function_id, call_type)
                        VALUES (?, ?, 'direct')
                    """, (func_id, target_id))

        conn.commit()
        conn.close()
        print("Dependency mapping complete.")

if __name__ == "__main__":
    resolver = DependencyResolver()
    resolver.resolve_all()