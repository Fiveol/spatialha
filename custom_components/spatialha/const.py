import json
from pathlib import Path

DOMAIN = "spatialha"

with open(Path(__file__).parent / "manifest.json") as f:
    manifest = json.load(f)

VERSION = manifest["version"]
