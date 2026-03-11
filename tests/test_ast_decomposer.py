import unittest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ast_decomposer import ASTDecomposer

class TestASTDecomposer(unittest.TestCase):
    def test_basic_decomposition(self):
        code = """
import os
from typing import List

PI = 3.14

class Shape:
    def area(self):
        pass

def get_pi():
    return PI
"""
        decomposer = ASTDecomposer(code)
        data = decomposer.get_full_decomposition()
        
        # Check imports
        self.assertEqual(len(data["imports"]), 2)
        self.assertEqual(data["imports"][0]["module"], None)
        self.assertEqual(data["imports"][0]["names"], ["os"])
        self.assertEqual(data["imports"][1]["module"], "typing")
        self.assertEqual(data["imports"][1]["names"], ["List"])
        
        # Check constants
        self.assertEqual(len(data["constants"]), 1)
        self.assertEqual(data["constants"][0]["name"], "PI")
        self.assertEqual(data["constants"][0]["value"], "3.14")
        
        # Check classes
        self.assertEqual(len(data["classes"]), 1)
        self.assertEqual(data["classes"][0]["name"], "Shape")
        self.assertEqual(len(data["classes"][0]["methods"]), 1)
        self.assertEqual(data["classes"][0]["methods"][0]["self_explanatory_name"], "area")
        
        # Check functions
        self.assertEqual(len(data["functions"]), 1)
        self.assertEqual(data["functions"][0]["self_explanatory_name"], "get_pi")

    def test_syntax_error(self):
        code = "def incomplete_func("
        with self.assertRaises(ValueError) as cm:
            ASTDecomposer(code)
        self.assertIn("CRITICAL: Syntax error", str(cm.exception))

    def test_logic_calls(self):
        code = """
def helper():
    pass

def main_func():
    helper()
    print("hello")
"""
        decomposer = ASTDecomposer(code)
        data = decomposer.get_full_decomposition()
        
        main_fn = next(f for f in data["functions"] if f["self_explanatory_name"] == "main_func")
        calls = set(main_fn["logic_calls"])
        self.assertIn("helper", calls)
        self.assertIn("print", calls)

if __name__ == "__main__":
    unittest.main()
