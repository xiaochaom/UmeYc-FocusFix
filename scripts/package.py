"""Package the built plugin for Decky's local ZIP installer."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path(__file__).resolve().parent.parent
name = json.loads((root / "plugin.json").read_text())["name"]
files = (
    "plugin.json", "package.json", "main.py", "gamescope.py",
    "star_rail.py", "dist/index.js", "README.md", "README.en.md",
)
for file in files:
    if not (root / file).is_file():
        raise SystemExit(f"Missing {file}")

output = root / "out" / f"{name}.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(root / file, f"{name}/{file}")
print(output)
