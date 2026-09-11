import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shear", ROOT / "render.py")
shear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shear)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_relative_cli(self):
        executable = self.root / "vercel"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o700)
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(shear.resolve_cli("./vercel"), str(executable.resolve()))
        finally:
            os.chdir(previous)

    def test_atomic_failure_preserves_previous_file(self):
        path = self.root / "test-shear.html"
        path.write_text("previous")
        with patch.object(shear.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                shear.private_write(path, "replacement")
        self.assertEqual(path.read_text(), "previous")
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_private_permissions(self):
        path = self.root / "test-shear.html"
        shear.private_write(path, "private")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_setup_rejects_codex_incompatible_names_before_saving(self):
        config = self.root / "test.shear.json"
        config.write_text("{}")
        for name in (
            "deployments.shear.html",
            "Deployments-shear.html",
            "deployments_test-shear.html",
            "deployments test-shear.html",
            "deployments--shear.html",
            "déployments-shear.html",
        ):
            with self.subTest(name=name), patch.object(shear, "read_json") as read:
                with self.assertRaises(ValueError):
                    self.run_main(
                        "--configure", "--config", config,
                        "--cli", sys.executable, "--scope", "test",
                        "--output", self.root / name,
                    )
                read.assert_not_called()
                self.assertEqual(config.read_text(), "{}")
                self.assertFalse((self.root / name).exists())

    def test_reject_unrelated_path_and_symlink(self):
        with self.assertRaises(ValueError):
            shear.private_path(self.root / "README.md", "-shear.html")
        original = self.root / "original"
        original.write_text("original")
        link = self.root / "link-shear.html"
        link.symlink_to(original)
        with self.assertRaises(ValueError):
            shear.private_path(link, "-shear.html")

    def test_git_requires_ignored_untracked_path(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        path = self.root / "custom-shear.html"
        with self.assertRaises(ValueError):
            shear.private_path(path, "-shear.html")
        (self.root / ".gitignore").write_text("*-shear.html\n")
        self.assertEqual(shear.private_path(path, "-shear.html"), path.resolve())
        path.write_text("private")
        subprocess.run(
            ["git", "-C", str(self.root), "add", "-f", str(path)], check=True
        )
        with self.assertRaises(ValueError):
            shear.private_path(path, "-shear.html")

    def run_main(self, *args):
        with patch.object(sys, "argv", ["render.py", *map(str, args)]):
            shear.main()

    def test_config_repair_and_failed_auth(self):
        config = self.root / "test.shear.json"
        config.write_text("{broken")
        output = self.root / "test-shear.html"
        args = [
            "--configure",
            "--config",
            config,
            "--cli",
            sys.executable,
            "--scope",
            "test",
            "--output",
            output,
        ]
        with patch.object(shear, "read_json", side_effect=ValueError("unauthorized")):
            with self.assertRaises(ValueError):
                self.run_main(*args)
        self.assertEqual(config.read_text(), "{broken")
        with patch.object(shear, "read_json", return_value={"projects": []}):
            self.run_main(*args)
        self.assertEqual(json.loads(config.read_text())["scope"], "test")
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_paginate_and_stall(self):
        with patch.object(
            shear,
            "read_json",
            side_effect=[
                {"items": [1], "pagination": {"next": 7}},
                {"items": [2], "pagination": {"next": None}},
            ],
        ) as read:
            self.assertEqual(list(shear.pages("cli", "scope", "/x", "items")), [1, 2])
            self.assertIn("until=7", read.call_args.args[2])
        with patch.object(
            shear, "read_json", return_value={"items": [], "pagination": {"next": 7}}
        ):
            with self.assertRaises(RuntimeError):
                list(shear.pages("cli", "scope", "/x", "items"))

    def test_snapshot_project_escaping_and_failure(self):
        config = self.root / "test.shear.json"
        output = self.root / "test-shear.html"
        args = [
            "--config",
            config,
            "--cli",
            sys.executable,
            "--scope",
            "test",
            "--output",
            output,
            "--project",
            "demo",
        ]

        def pages(cli, scope, endpoint, key, params=None):
            if key == "projects":
                return iter([{"id": "p", "name": "demo", "accountId": "t"}])
            self.assertEqual(params, {"projectId": "p"})
            return iter(
                [
                    {
                        "uid": "d",
                        "projectId": "p",
                        "url": "example.invalid",
                        "created": 1,
                        "meta": {
                            "githubCommitMessage": "</script><script>alert(1)</script>"
                        },
                    }
                ]
            )

        with patch.object(shear, "pages", side_effect=pages):
            self.run_main(*args)
        before = output.read_text()
        self.assertIn('"project": "demo"', before)
        self.assertNotIn("</script><script>alert", before)
        with patch.object(shear, "pages", side_effect=ValueError("network failed")):
            with self.assertRaises(ValueError):
                self.run_main(*args)
        self.assertEqual(output.read_text(), before)
        output.write_text("unrelated document")
        with self.assertRaises(SystemExit):
            self.run_main(*args)
        self.assertEqual(output.read_text(), "unrelated document")


if __name__ == "__main__":
    unittest.main()
