# Validation

Run these checks from the OneShot repo root.

## JSON Parse

```bash
python3 -m json.tool plugins/codex/oneshot/.codex-plugin/plugin.json >/tmp/oneshot-codex-plugin-json.out
python3 -m json.tool .agents/plugins/marketplace.json >/tmp/oneshot-codex-marketplace-json.out
```

## Tree Inspection

```bash
find plugins/codex/oneshot -maxdepth 4 -print | sort
```

Expected files include `.codex-plugin/plugin.json`, `skills/oneshot/SKILL.md`, package docs, and the three PNG assets under `assets/`. `.codex-plugin/` should contain only the manifest.

## Manifest Path Resolution

Check every path-bearing manifest field starts with `./` and resolves from the plugin root:

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("plugins/codex/oneshot").resolve()
manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
paths = [("skills", manifest["skills"])]
interface = manifest["interface"]
paths.extend([
    ("interface.composerIcon", interface["composerIcon"]),
    ("interface.logo", interface["logo"]),
])
paths.extend((f"interface.screenshots[{i}]", value) for i, value in enumerate(interface["screenshots"]))
for name, value in paths:
    assert value.startswith("./"), f"{name} must start with ./"
    target = (root / value[2:]).resolve()
    assert target.exists(), f"{name} does not resolve: {target}"
    print(f"PASS {name}: {value} -> {target}")
assert len(interface["defaultPrompt"]) <= 3
PY
```

## Marketplace Path Resolution

```bash
python3 - <<'PY'
import json
from pathlib import Path

repo = Path.cwd()
marketplace = json.loads((repo / ".agents/plugins/marketplace.json").read_text())
entry = next(item for item in marketplace["plugins"] if item["name"] == "oneshot")
path = entry["source"]["path"]
assert path.startswith("./")
resolved = (repo / path[2:]).resolve()
expected = (repo / "plugins/codex/oneshot").resolve()
assert resolved == expected
assert resolved.exists()
print(f"PASS marketplace path: {path} -> {resolved}")
PY
```

## Static Copy Checks

Run the ticket validation script to scan this package and marketplace file for scaffold residue and fake URLs.

Expected result: no scaffold or fake-URL hits in `plugins/codex/oneshot` or `.agents/plugins`. The package intentionally names legacy source-project files only in setup guardrails that stop Codex from using an old vault.

## Image Checks

```bash
python3 - <<'PY'
from pathlib import Path
from PIL import Image

root = Path("plugins/codex/oneshot/assets")
expected = {
    "icon.png": (512, 512),
    "logo.png": (1200, 420),
    "screenshot-workflow.png": (1440, 900),
}
for name, size in expected.items():
    with Image.open(root / name) as image:
        assert image.format == "PNG"
        assert image.size == size
        print(f"PASS {name}: {image.format} {image.size}")
PY
```

## Codex CLI Surface

```bash
codex plugin --help
codex plugin marketplace --help
codex plugin marketplace add --help
```

The local CLI exposes marketplace management. A live add/install action is infrastructure-dependent and can modify local Codex configuration, so static package completion is proven by the checks above.
