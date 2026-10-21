"""Verify the deliberately narrow copied core and its data-boundary contracts."""

import ast
import hashlib
import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from nestra_core.project_memory import compile_project_memory, restore_project_memory
from nestra_core.security import validate_project_id

ROOT = Path(__file__).resolve().parents[1]


def FIXED_CLOCK():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


class CoreIntegrityTests(unittest.TestCase):
    def test_copied_files_match_reviewed_provenance(self):
        manifest = json.loads((ROOT / "PROVENANCE.json").read_text(encoding="utf-8"))
        expected = {
            "LICENSE",
            "src/nestra_core/project_memory.py",
            "src/nestra_core/memory.py",
            "src/nestra_core/security.py",
        }
        self.assertEqual({row["showcase_path"] for row in manifest["copied_files"]}, expected)
        for row in manifest["copied_files"]:
            with self.subTest(path=row["showcase_path"]):
                self.assertIs(row["modified"], False)
                path = (ROOT / row["showcase_path"]).resolve()
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
        self.assertIn("Agent Hive Contributors", (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_application_dependencies_are_standard_library_or_local_only(self):
        allowed = set(sys.stdlib_module_names) | {"nestra_core", "nestra_showcase"}
        forbidden = {"socket", "urllib", "http", "requests", "httpx", "subprocess"}
        paths = list((ROOT / "src").rglob("*.py")) + [ROOT / "demo.py"]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [item.name.split(".")[0] for item in node.names]
                    elif isinstance(node, ast.ImportFrom) and not node.level:
                        names = [(node.module or "").split(".")[0]]
                    else:
                        continue
                    for name in names:
                        self.assertIn(name, allowed, f"External import: {path.name}: {name}")
                        self.assertNotIn(
                            name, forbidden, f"Network/process dependency: {path.name}: {name}"
                        )

    def test_snapshot_round_trip_and_tamper_rejection(self):
        document = {
            "id": "example-procedure",
            "title": "נוהל מומצא",
            "text": "נוהל מומצא קובע שמירת מסמך בתיקיית הדגמה.",
            "trust": "trusted",
            "sourceUri": "fixture://example-procedure",
        }
        memory = compile_project_memory(
            {"projectId": "showcase-test", "documents": [document]}, clock=FIXED_CLOCK
        )
        exported = memory.export()
        restored = restore_project_memory(exported)
        self.assertEqual(restored.export(), exported)
        tampered = deepcopy(exported)
        tampered["facts"][0]["text"] = "הוראה שהמקור אינו מכיל"
        with self.assertRaises(ValueError):
            restore_project_memory(tampered)

    def test_compilation_does_not_retain_caller_mutable_data(self):
        input_ = {
            "projectId": "detached",
            "documents": [{"id": "doc", "title": "דוגמה", "text": "דוגמה מקורית."}],
        }
        memory = compile_project_memory(input_, clock=FIXED_CLOCK)
        snapshot = memory.export()
        input_["documents"][0]["text"] = "שינוי לאחר קליטה"
        snapshot["documents"][0]["text"] = "שינוי לאחר ייצוא"
        self.assertEqual(memory.export()["documents"][0]["text"], "דוגמה מקורית.")

    def test_project_identifier_cannot_traverse_paths(self):
        for value in ("../secret", "..", "a/b", "a\\b", "", "שם"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_project_id(value)


if __name__ == "__main__":
    unittest.main()
