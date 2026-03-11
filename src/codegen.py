import urllib.request
import urllib.error
import urllib.parse
import json
import os
import ast
from typing import List, Dict, Any, Tuple, Union

class ASTDecomposer:
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.tree = ast.parse(source_code)

    def get_full_decomposition(self) -> Dict[str, List[Dict[str, Any]]]:
        decomposition = {"imports": [], "classes": [], "functions": [], "constants": []}
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                decomposition["imports"].append(self._decompose_import(node))
            elif isinstance(node, ast.ClassDef):
                decomposition["classes"].append(self._decompose_class(node))
            elif isinstance(node, ast.FunctionDef):
                decomposition["functions"].append(self._decompose_function(node))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        decomposition["constants"].append({"name": target.id, "value": ast.unparse(node.value), "line": node.lineno})
        return decomposition

    def _decompose_import(self, node: Union[ast.Import, ast.ImportFrom]) -> Dict[str, Any]:
        return {"type": "import", "module": getattr(node, 'module', None), "names": [n.name for n in node.names], "line": node.lineno}

    def _decompose_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        methods = [self._decompose_function(n) for n in node.body if isinstance(n, ast.FunctionDef)]
        return {"type": "class", "name": node.name, "bases": [ast.unparse(b) for b in node.bases], "docstring": ast.get_docstring(node) or "MISSING", "methods": methods, "line": node.lineno}

    def _decompose_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        args = [{"name": arg.arg, "type": ast.unparse(arg.annotation) if arg.annotation else "MISSING"} for arg in node.args.args]
        calls = set()
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Call):
                if isinstance(sub_node.func, ast.Name): calls.add(sub_node.func.id)
                elif isinstance(sub_node.func, ast.Attribute): calls.add(sub_node.func.attr)
        return {"type": "function", "self_explanatory_name": node.name, "arguments": args, "return_type": ast.unparse(node.returns) if node.returns else "MISSING", "docstring": ast.get_docstring(node) or "MISSING", "logic_calls": list(calls), "line_start": node.lineno, "line_end": getattr(node, 'end_lineno', node.lineno)}

class CodebaseCodegen:
    def __init__(self, postgrest_base_url: str = "http://localhost:3000", output_root_directory: str = ".") -> None:
        self.postgrest_base_url = postgrest_base_url.rstrip("/")
        self.output_root_directory = output_root_directory

    def _get_json(self, url: str) -> Any:
        request = urllib.request.Request(url=url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response: return json.loads(response.read().decode("utf-8"))

    def _patch_json(self, url: str, payload: Dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url=url, data=encoded, headers={"Content-Type": "application/json"}, method="PATCH")
        try: urllib.request.urlopen(request, timeout=10)
        except: pass

    def fetch_active_modules(self) -> List[Dict[str, Any]]:
        return self._get_json(f"{self.postgrest_base_url}/code_modules?active=eq.true&order=module_name")

    def fetch_components_for_module(self, module_name: str) -> List[Dict[str, Any]]:
        return self._get_json(f"{self.postgrest_base_url}/code_components?module_name=eq.{module_name}&active=eq.true&order=sort_order")

    def sync_and_decompose_all(self) -> None:
        modules = self.fetch_active_modules()
        for mod in modules:
            components = self.fetch_components_for_module(mod['module_name'])
            source = "\n\n".join([c['source_text'] for c in components])
            decomposer = ASTDecomposer(source)
            decomp = decomposer.get_full_decomposition()
            # Update DB with decomposition results...
            print(f"Decomposed {mod['module_name']}: {len(decomp['functions'])} functions found.")