import unittest
import sys
import os
import subprocess
from pathlib import Path

class TestLogicCLI(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.parent
        self.logic_py = str(self.root / "logic.py")
        self.db_path = "cli_test.db"
        self.env = os.environ.copy()
        self.env["LOGIC_DB_PATH"] = self.db_path
        
        # Create a temp src directory
        self.src_dir = self.root / "tests" / "temp_src"
        self.src_dir.mkdir(exist_ok=True)
        (self.src_dir / "math_utils.py").write_text("def add(a, b): return a + b")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if self.src_dir.exists():
            for f in self.src_dir.glob("*.py"):
                f.unlink()
            self.src_dir.rmdir()

    def run_logic(self, *args):
        cmd = [sys.executable, self.logic_py] + list(args)
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True)

    def test_cli_flow(self):
        # 1. Sync
        res = self.run_logic("sync", "--src", str(self.src_dir))
        self.assertEqual(res.returncode, 0)
        self.assertIn("Sync complete", res.stdout)
        
        # 2. Check
        res = self.run_logic("check")
        self.assertEqual(res.returncode, 0)
        self.assertIn("No circular dependencies", res.stdout)
        
        # 3. Trace
        res = self.run_logic("trace", "add")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Trace: add", res.stdout)
        
        # 4. Context
        res = self.run_logic("context", "add")
        self.assertEqual(res.returncode, 0)
        self.assertIn("# Logic Context: `add`", res.stdout)

    def test_missing_node(self):
        self.run_logic("sync", "--src", str(self.src_dir))
        res = self.run_logic("trace", "non_existent")
        self.assertEqual(res.returncode, 1)
        self.assertIn("not found in the registry", res.stderr)

if __name__ == "__main__":
    unittest.main()
