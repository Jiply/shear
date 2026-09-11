#!/usr/bin/env python3
"""Read Vercel through a configured CLI and render a private Codex deployment picker."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import os
import re
import shutil
import tempfile
from urllib.parse import urlencode


def private_write(path, text):
    """Replace a private file atomically without exposing partial contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".shear-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_path(value, suffix):
    """Require dedicated private filenames and ignore protection inside Git."""
    path = Path(value).expanduser().absolute()
    if path.is_symlink():
        raise ValueError("Private files must not be symlinks")
    path = path.resolve()
    if not path.name.endswith(suffix):
        raise ValueError(f"Private filename must end with {suffix}")
    if suffix == "-shear.html" and not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*\.html", path.name
    ):
        raise ValueError(
            "Snapshot filename must use lowercase letters, digits, and single hyphens; "
            "choose a name such as deployments-shear.html"
        )
    parent = path.parent
    while not parent.exists():
        parent = parent.parent
    if shutil.which("git"):
        result = subprocess.run(
            ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            root = result.stdout.strip()
            tracked = subprocess.run(
                ["git", "-C", root, "ls-files", "--error-unmatch", str(path)],
                capture_output=True,
            )
            ignored = subprocess.run(
                ["git", "-C", root, "check-ignore", "-q", str(path)],
                capture_output=True,
            )
            if tracked.returncode == 0 or ignored.returncode != 0:
                raise ValueError(
                    "Private file is tracked or not ignored by Git; choose an ignored location"
                )
    return path


def resolve_cli(value):
    """Preserve explicit relative executable paths instead of searching PATH."""
    value = os.path.expanduser(value)
    explicit = (
        os.path.isabs(value) or os.sep in value or (os.altsep and os.altsep in value)
    )
    candidate = str(Path(value).resolve()) if explicit else shutil.which(value)
    if (
        not candidate
        or not Path(candidate).is_file()
        or not os.access(candidate, os.X_OK)
    ):
        raise ValueError("Configured Vercel CLI is unavailable; run setup-shear")
    return candidate


def read_json(cli, scope, endpoint):
    result = subprocess.run(
        [cli, "api", endpoint, "--scope", scope, "--raw"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Vercel request failed")
    return json.loads(result.stdout)


def pages(cli, scope, endpoint, key, params=None):
    query = {"limit": 100, **(params or {})}
    seen = set()
    while True:
        data = read_json(cli, scope, endpoint + "?" + urlencode(query))
        yield from data[key]
        cursor = data.get("pagination", {}).get("next")
        if cursor is None:
            break
        if cursor in seen:
            raise RuntimeError(
                "Pagination stalled; refusing to present an incomplete history."
            )
        seen.add(cursor)
        query["until"] = cursor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).resolve().with_name(".shear.json")
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Validate and save local setup without rendering",
    )
    parser.add_argument("--cli", help="Vercel executable or wrapper path")
    parser.add_argument("--scope")
    parser.add_argument(
        "--project", help="Optional exact project name; otherwise include every project"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config_path = private_path(args.config, ".shear.json")
    try:
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        if not isinstance(config, dict) or any(
            not isinstance(v, str) for v in config.values()
        ):
            raise ValueError("Configuration must contain string settings")
    except (ValueError, OSError) as error:
        if args.configure and args.cli and args.scope and args.output:
            config = {}
        else:
            parser.error(
                f"Invalid configuration: {error}. Repair with --configure --cli PATH --scope TEAM --output FILE"
            )
    cli_value = args.cli or config.get("cli")
    args.scope = args.scope or config.get("scope")
    output = args.output or config.get("output")
    if not cli_value or not args.scope or not output:
        parser.error(
            "Shear needs setup: use the setup-shear skill, or --configure --cli PATH --scope TEAM --output FILE"
        )
    cli = resolve_cli(cli_value)
    args.output = private_path(output, "-shear.html")
    if args.output.exists() and not args.output.read_text().startswith(
        "<!-- shear-private-snapshot -->"
    ):
        parser.error("Output exists and is not a Shear snapshot; choose a new filename")
    if args.configure:
        read_json(cli, args.scope, "/v9/projects?limit=1")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(args.output.parent, os.W_OK):
            parser.error("Output directory is not writable")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        private_write(
            config_path,
            json.dumps(
                {"cli": cli, "scope": args.scope, "output": str(args.output)}, indent=2
            )
            + "\n",
        )
        print(f"Setup verified and saved: {config_path}")
        return
    projects = list(pages(cli, args.scope, "/v9/projects", "projects"))
    projects = [p for p in projects if not args.project or p["name"] == args.project]
    if not projects:
        raise ValueError("No matching accessible projects")
    params = {"projectId": projects[0]["id"]} if args.project else {}
    by_id = {
        p["id"]: {
            "id": p["id"],
            "name": p["name"],
            "teamId": p["accountId"],
            "deployments": [],
        }
        for p in projects
    }
    seen = set()
    for deployment in pages(cli, args.scope, "/v6/deployments", "deployments", params):
        project = by_id.get(deployment.get("projectId"))
        if project is None or deployment["uid"] in seen:
            continue
        seen.add(deployment["uid"])
        meta = deployment.get("meta") or {}
        project["deployments"].append(
            {
                "id": deployment["uid"],
                "url": deployment["url"],
                "created": deployment["created"],
                "state": deployment.get("state", "UNKNOWN"),
                "target": deployment.get("target") or "preview",
                "branch": meta.get("githubCommitRef")
                or meta.get("gitlabCommitRef")
                or meta.get("bitbucketCommitRef")
                or "",
                "sha": meta.get("githubCommitSha")
                or meta.get("gitlabCommitSha")
                or meta.get("bitbucketCommitSha")
                or "",
                "message": meta.get("githubCommitMessage")
                or meta.get("gitlabCommitMessage")
                or meta.get("bitbucketCommitMessage")
                or "",
            }
        )
        if len(seen) % 500 == 0:
            print(f"Loaded {len(seen)} deployments…", flush=True)
    for project in by_id.values():
        project["deployments"].sort(key=lambda d: (d["created"], d["id"]), reverse=True)
    data = {
        "setup": {
            "renderer": str(Path(__file__).resolve()),
            "config": str(config_path),
            "cli": cli,
            "output": str(args.output),
            "project": args.project,
        },
        "scope": args.scope,
        "snapshot": datetime.now(timezone.utc).isoformat(),
        "projects": sorted(by_id.values(), key=lambda p: p["name"]),
    }
    serialized = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    html = (
        Path(__file__)
        .with_name("picker.html")
        .read_text()
        .replace("/* PICKER_DATA */ null", serialized)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    private_write(args.output, "<!-- shear-private-snapshot -->\n" + html)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "projects": {
                    p["name"]: len(p["deployments"]) for p in data["projects"]
                },
                "total": len(seen),
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
