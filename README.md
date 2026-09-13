# Shear

![Layered pastel paper with precisely trimmed edges and detached offcuts](assets/shear-cover.png)

A private Vercel deployment picker for Codex. Browse 25 deployments per page, filter and select entries, then send exact deletion selections back to your task. Runs locally without hosting.

## Browse and select

| Browse deployments                                                                                | Filter and preview a selection                                                                                                   |
| ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| ![Shear showing deployment statuses, environments, and pagination](assets/browse-deployments.png) | ![Shear filtering preview deployments, selecting two entries, and previewing the deletion prompt](assets/select-deployments.png) |
| Switch projects, inspect deployment states, and browse 25 entries per page.                       | Search and filter, select exact deployments, and review the prompt before sending it to Codex.                                   |

Screenshots show the actual interface with fictional deployment data. The cover is AI-generated artwork. Image assets use Git LFS; run `git lfs pull` if they are missing from your checkout.

## Requirements

- Python 3.9 or newer; the renderer and tests use only the standard library.
- An authenticated Vercel CLI supporting `vercel api`, or a wrapper that accepts the same arguments. Verified with Vercel CLI 54.17.3. Setup verifies access to the selected scope; an unsupported CLI fails before saving configuration.
- A browser with the HTML Popover API, `:popover-open`, and `beforetoggle`. Verified in Chrome 152 on macOS. Other browsers, operating systems, and CLI versions are not yet verified.
- Git for repository ignore/tracking checks when private files are stored inside a repository.

The Codex inline view uses `window.openai.sendFollowUpMessage`. If the host doesn't provide it, the HTML supports copying the prompt into the task. The renderer never deletes deployments.

## Interactive setup

Clone or download Shear to a directory you choose. Ask Codex to read [setup-shear](skills/setup-shear/SKILL.md) from that checkout. When working in the repository, `.agents/skills/setup-shear` links to the same skill. For use elsewhere, link the canonical skill folder into your chosen agent skills directory, or explicitly ask Codex to read it. If your checkout does not preserve symlinks, use the canonical skill directly.

The skill asks for your authenticated CLI executable or wrapper, Vercel account scope, and private HTML output location. It validates account access before saving `.shear.json` beside the renderer. On a new machine, run setup again. No team name, CLI manager, or installation directory is assumed.

## Command-line setup

Run from the checkout, replacing the example values:

```sh
python3 render.py --configure --cli /path/to/vercel --scope your-team --output /path/to/private/deployments-shear.html
python3 render.py
```

Explicit relative executables such as `./tools/vercel` work, as do executable names on PATH. Arguments and credentials do not belong in the CLI setting; use an authenticated CLI or wrapper.

`--config` selects another config file ending in `.shear.json`. `--cli`, `--scope`, and `--output` override saved values for one invocation. `--project` limits the snapshot to one exact project name and remains part of its refresh prompt. Without it, every accessible project and deployment page is fetched.

If a config is malformed, supply all three replacement values with `--configure` to repair it. Failed access validation preserves the previous config. If the saved executable or output location no longer exists or is usable, rerun setup with corrected paths.

## Private files

Config filenames end in `.shear.json`; snapshot filenames end in `-shear.html`. Snapshot basenames use lowercase letters, digits, and single hyphens, for example `deployments-shear.html`. Those patterns are ignored by this repository. When choosing a location inside another Git repository, that repository must also ignore the destination, and the file must not already be tracked. Existing unrelated output files and symlinks are rejected.

Writes use a temporary file with private permissions and atomic replacement. POSIX permissions are `0600`; platform filesystem protections still apply. Fetch or replacement failure preserves the previous snapshot. Config stores only paths and scope, never authentication credentials. Generated HTML includes local setup paths and deployment metadata, so keep it private. Credentials remain managed by the CLI.

The UI fills its embedded container and is centered at 42rem when opened independently. Display a rendered snapshot in Codex using `visualize{"path":"<absolute-output-path>"}`.

## Verification

Run the renderer regression tests without installing dependencies:

```sh
python3 -m unittest discover -s tests -v
```

Generate a self-running browser test page using synthetic data:

```sh
python3 tests/browser_fixture.py
```

Open the printed file in Chrome. It displays PASS or FAIL and each check. Tests exercise selection, pagination, project-specific refresh, text escaping, keyboard navigation, empty states, focus restoration, tooltip exclusion, and layout at 320–1440px. It also checks 200 fresh iframe renders across viewport sizes, deployment counts, host bridge availability, script placement, and themes. The page never contacts Vercel or sends prompts to Codex.

## Deletion boundary

The picker sends selected IDs and URLs as a prompt; it is not a deletion executor. The receiving agent must verify the exact team, project, URLs, aliases, and current production routing before acting, and skip current production and already-deleted entries. These are agent instructions, not a transactional guarantee against concurrent routing changes.

## License

[MIT](LICENSE).
