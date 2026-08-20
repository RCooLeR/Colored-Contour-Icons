"""Remove only this project's XVM field references from a players-panel file."""

from __future__ import annotations

import re
import codecs
from pathlib import Path


REFERENCE_LINE = re.compile(
    r"^[ \t]*\$\{[\"']_rcooler_colored_contour_icons\.xc[\"']:[\"']"
    r"fields\.(?:vehicleIcon|compactVehicleName)(?:Left|Right)[\"']\},?[ \t]*\r?\n?",
    re.MULTILINE,
)


def remove_adapter_references(text: str) -> str:
    """Return ``text`` with RCooLeR fields removed, preserving everything else."""
    return REFERENCE_LINE.sub("", text)


def prepare_clean_copy(source: Path, destination: Path) -> bool:
    """Write a cleaned byte-preserving copy and return whether it changed."""
    original_bytes = source.read_bytes()
    has_bom = original_bytes.startswith(codecs.BOM_UTF8)
    original = original_bytes.decode("utf-8-sig")
    cleaned = remove_adapter_references(original)
    cleaned_bytes = cleaned.encode("utf-8")
    if has_bom:
        cleaned_bytes = codecs.BOM_UTF8 + cleaned_bytes
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(cleaned_bytes)
    return cleaned_bytes != original_bytes


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    changed = prepare_clean_copy(arguments.source, arguments.output)
    print("changed" if changed else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
