import ast
from typing import List, Dict, Any, Union

class ASTDecomposer:
    """
    High-Fidelity Code Decomposer.
    Maps every Python element (Classes, Functions, Imports, Constants) 
    to relational data points for the Codebase-as-Data registry.
    """
    
    def __init__(self, source_code: str):
        self.source_code = source_code
        try:
            self.tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"CRITICAL: Syntax error in source code at line {e.lineno}: {e.msg}")

    def get_full_decomposition(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Decomposes the entire module into a complete relational graph.
        Covers: Imports, Classes, Functions, and Constants.
        """
        decomposition = {
            "imports": [],
            "classes": [],
            "functions": [],
            "constants": []
        }

        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                decomposition["imports"].append(self._decompose_import(node))
            elif isinstance(node, ast.ClassDef):
                decomposition["classes"].append(self._decompose_class(node))
            elif isinstance(node, ast.FunctionDef):
                decomposition["functions"].append(self._decompose_function(node))
            elif isinstance(node, ast.Assign):
                # Only capture top-level constants (Upper Case)
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        decomposition["constants"].append({
                            "name": target.id,
                            "value": ast.unparse(node.value),
                            "line": node.lineno
                        })

        return decomposition

    def _decompose_import(self, node: Union[ast.Import, ast.ImportFrom]) -> Dict[str, Any]:
        return {
            "type": "import",
            "module": getattr(node, 'module', None),
            "names": [n.name for n in node.names],
            "line": node.lineno
        }

    def _decompose_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        methods = [self._decompose_function(n) for n in node.body if isinstance(n, ast.FunctionDef)]
        return {
            "type": "class",
            "name": node.name,
            "bases": [ast.unparse(b) for b in node.bases],
            "docstring": ast.get_docstring(node) or "MISSING",
            "methods": methods,
            "line": node.lineno
        }

    def _decompose_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        args = []
        for arg in node.args.args:
            args.append({
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else "MISSING"
            })
        
        calls = set()
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Call):
                if isinstance(sub_node.func, ast.Name):
                    calls.add(sub_node.func.id)
                elif isinstance(sub_node.func, ast.Attribute):
                    calls.add(sub_node.func.attr)

        return {
            "type": "function",
            "self_explanatory_name": node.name,
            "arguments": args,
            "return_type": ast.unparse(node.returns) if node.returns else "MISSING",
            "docstring": ast.get_docstring(node) or "MISSING",
            "logic_calls": list(calls),
            "line_start": node.lineno,
            "line_end": getattr(node, 'end_lineno', node.lineno)
        }

if __name__ == "__main__":
    test_code = (
        "import math\n"
        "from typing import List\n"
        "PI_CONSTANT = 3.14159\n"
        "class GeometryEngine:\n"
        '    """Handles complex circular logic."""\n'
        "    def compute_area(self, radius: float) -> float:\n"
        "        return math.pi * (radius ** 2)\n"
        "\n"
        "def calculate_paint(radius: float) -> float:\n"
        "    engine = GeometryEngine()\n"
        "    area = engine.compute_area(radius)\n"
        "    return area / 5.0\n"
    )
    decomposer = ASTDecomposer(test_code)
    import json
    print(json.dumps(decomposer.get_full_decomposition(), indent=4))
