"""List installed packages that also provide the global battle atlas."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


ATLAS_MEMBERS = {
    "res/gui/flash/atlases/battleAtlas.dds",
    "res/gui/flash/atlases/battleAtlas.xml",
}


def find_conflicts(mods_directory: Path, target: Path) -> list[str]:
    conflicts: list[str] = []
    target = target.resolve()
    for package in sorted(mods_directory.glob("*.wotmod")):
        if package.resolve() == target:
            continue
        try:
            with zipfile.ZipFile(package) as archive:
                if ATLAS_MEMBERS.intersection(archive.namelist()):
                    conflicts.append(str(package))
        except zipfile.BadZipFile:
            continue
    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mods-directory", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(find_conflicts(arguments.mods_directory, arguments.target)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
