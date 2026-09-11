"""Exercise a clean checkout and CLI boundary without credentials or network."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FreshSetupTests(unittest.TestCase):
    def test_clean_checkout_setup_render_and_refresh(self):
        with tempfile.TemporaryDirectory(prefix="shear clean ") as folder:
            root = Path(folder)
            checkout = root / "checkout with spaces"
            checkout.mkdir()
            for filename in ("render.py", "picker.html", ".gitignore"):
                shutil.copyfile(ROOT / filename, checkout / filename)
            subprocess.run(
                ["git", "init", str(checkout)], check=True, capture_output=True
            )
            cli = root / "fake vercel"
            cli.write_text(
                "#!"
                + sys.executable
                + "\n"
                + """import json,sys
from urllib.parse import urlparse,parse_qs
assert sys.argv[1]=='api' and '--method' not in sys.argv
assert sys.argv[sys.argv.index('--scope')+1]=='test-team'
p=urlparse(sys.argv[2]);q=parse_qs(p.query)
project={'id':'p','name':'demo','accountId':'team'}
if p.path=='/v9/projects':
 print(json.dumps({'projects':[project],'pagination':{'next':None}}))
elif p.path=='/v6/deployments':
 index=2 if 'until' in q else 1
 print(json.dumps({'deployments':[{'uid':'d'+str(index),'projectId':'p','url':'test.invalid','created':index,'meta':{}}],'pagination':{'next':None if index==2 else 1}}))
else: raise RuntimeError('Unexpected endpoint')
"""
            )
            cli.chmod(0o700)
            output = checkout / "custom-shear.html"

            def run(*args):
                return subprocess.run(
                    [sys.executable, str(checkout / "render.py"), *args],
                    cwd=checkout,
                    capture_output=True,
                    text=True,
                )

            self.assertNotEqual(run().returncode, 0)
            configured = run(
                "--configure",
                "--cli",
                str(cli),
                "--scope",
                "test-team",
                "--output",
                str(output),
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            rendered = run("--project", "demo")
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertEqual(json.loads(rendered.stdout)["total"], 2)
            self.assertIn('"project": "demo"', output.read_text())
            self.assertEqual(run("--project", "demo").returncode, 0)
            status = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ],
                text=True,
            )
            self.assertNotIn(".shear.json", status)
            self.assertNotIn("custom-shear.html", status)


if __name__ == "__main__":
    unittest.main()
