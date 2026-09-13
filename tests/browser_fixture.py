"""Build a self-running browser regression page using synthetic data only."""

import argparse
import json
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
output = args.output or Path(tempfile.mkdtemp(prefix="shear-browser-")) / "test.html"
deployments = [
    {
        "id": f"d{i}",
        "url": f"d{i}.example.invalid",
        "message": "Message " + str(i),
        "created": i,
        "state": "READY" if i % 2 else "CANCELED",
        "target": "production",
        "branch": "main",
        "sha": "",
    }
    for i in range(60)
]
deployments[0]["message"] = '<img src=x onerror="window.injected=true">'
data = {
    "scope": "test",
    "snapshot": "test",
    "setup": {
        "project": "demo",
        "renderer": "render.py",
        "config": "test.shear.json",
        "cli": "vercel",
        "output": "test-shear.html",
    },
    "projects": [
        {"id": "p", "name": "demo", "teamId": "t", "deployments": deployments},
        {"id": "empty", "name": "empty", "teamId": "t", "deployments": []},
    ],
}
html = (
    (root / "picker.html")
    .read_text()
    .replace("/* PICKER_DATA */ null", json.dumps(data).replace("<", "\\u003c"))
)
bridge = "<script>window.sent=[];window.openai={sendFollowUpMessage:async ({prompt})=>window.sent.push(prompt)};</script>"
html = bridge + html
script = (root / "tests/browser.js").read_text()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    '<!doctype html><meta charset="utf-8"><title>Shear browser tests</title><style>body{background:#111;color:#eee;font:14px monospace}iframe{height:800px;border:0}</style><pre id="results">Running…</pre><iframe id="app" title="Shear test fixture"></iframe><script>const fixture='
    + json.dumps(html).replace("<", "\\u003c")
    + ";"
    + script
    + "</script>"
)
print(output.resolve())
