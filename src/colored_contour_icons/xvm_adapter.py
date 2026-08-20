"""Prepare an opt-in XVM players-panel adapter without editing the source profile.

XVM's JSONx format is JSON with comments and ``${...}`` imports, so a normal
JSON parser cannot preserve a user's configuration.  This module performs only
two narrow edits to a copy of ``playersPanel.xc``:

* import the raw contour image field into every visible panel mode;
* optionally import a compact vehicle-name overlay into short and medium mode.

All other bytes, including comments and custom fields, are retained.
"""

from __future__ import annotations

import argparse
import codecs
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRAGMENT = PROJECT_ROOT / "xvm" / "_rcooler_colored_contour_icons.xc"
VISIBLE_MODES = ("short", "medium", "medium2", "large")
COMPACT_NAME_MODES = ("short", "medium")


class AdapterError(ValueError):
    """Raised when a playersPanel file is not safe to patch automatically."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str


def _tokens(text: str) -> list[Token]:
    """Tokenize the structural subset of XVM JSONx while ignoring comments."""
    result: list[Token] = []
    index = 0
    length = len(text)
    punctuation = "{}[]:,"
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            if close < 0:
                raise AdapterError("Unterminated block comment in playersPanel.xc")
            index = close + 2
            continue
        if char == '"':
            start = index
            index += 1
            escaped = False
            while index < length:
                current = text[index]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    index += 1
                    break
                index += 1
            else:
                raise AdapterError("Unterminated string in playersPanel.xc")
            raw = text[start:index]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw[1:-1]
            result.append(Token("string", value, start, index))
            continue
        if char in punctuation:
            result.append(Token(char, char, index, index + 1))
            index += 1
            continue
        start = index
        while index < length:
            if text[index].isspace() or text[index] in punctuation + '"':
                break
            if text.startswith("//", index) or text.startswith("/*", index):
                break
            index += 1
        result.append(Token("bare", text[start:index], start, index))
    return result


def _matches(tokens: list[Token]) -> dict[int, int]:
    stack: list[int] = []
    result: dict[int, int] = {}
    pairs = {"}": "{", "]": "["}
    for index, token in enumerate(tokens):
        if token.kind in ("{", "["):
            stack.append(index)
        elif token.kind in ("}", "]"):
            if not stack or tokens[stack[-1]].kind != pairs[token.kind]:
                raise AdapterError("Unbalanced brackets in playersPanel.xc")
            opening = stack.pop()
            result[opening] = index
            result[index] = opening
    if stack:
        raise AdapterError("Unbalanced brackets in playersPanel.xc")
    return result


def _property_value(
    tokens: list[Token], matches: dict[int, int], object_index: int, name: str
) -> int:
    if tokens[object_index].kind != "{":
        raise AdapterError("Expected an inline object while looking for %r" % name)
    close_index = matches[object_index]
    curly_depth = 0
    square_depth = 0
    index = object_index + 1
    while index < close_index:
        token = tokens[index]
        if (
            curly_depth == 0
            and square_depth == 0
            and token.kind == "string"
            and token.value == name
            and index + 2 < close_index
            and tokens[index + 1].kind == ":"
        ):
            return index + 2
        if token.kind == "{":
            curly_depth += 1
        elif token.kind == "}":
            curly_depth -= 1
        elif token.kind == "[":
            square_depth += 1
        elif token.kind == "]":
            square_depth -= 1
        index += 1
    raise AdapterError("Required property %r was not found" % name)


def _object_property(
    tokens: list[Token], matches: dict[int, int], object_index: int, name: str
) -> int:
    value_index = _property_value(tokens, matches, object_index, name)
    if tokens[value_index].kind != "{":
        raise AdapterError(
            "%r is imported or is not an inline object; patch its source file manually" % name
        )
    return value_index


def _array_property(
    tokens: list[Token], matches: dict[int, int], object_index: int, name: str
) -> int:
    value_index = _property_value(tokens, matches, object_index, name)
    if tokens[value_index].kind != "[":
        raise AdapterError("%r is not an inline array" % name)
    return value_index


def _append_array_values(
    text: str,
    tokens: list[Token],
    matches: dict[int, int],
    array_index: int,
    values: list[str],
) -> list[Edit]:
    close_index = matches[array_index]
    opening = tokens[array_index]
    closing = tokens[close_index]
    content = text[opening.end : closing.start]
    missing = [value for value in values if value not in content]
    if not missing:
        return []

    significant = [
        index for index in range(array_index + 1, close_index) if tokens[index].kind != ","
    ]
    newline = "\r\n" if "\r\n" in text else "\n"
    if not significant:
        if newline not in content:
            return [Edit(opening.end, closing.start, " " + ", ".join(missing) + " ")]
        line_start = text.rfind("\n", 0, closing.start) + 1
        closing_indent = text[line_start:closing.start]
        item_indent = closing_indent + "  "
        insertion = item_indent + ("," + newline + item_indent).join(missing) + newline
        return [Edit(line_start, line_start, insertion)]

    last_index = significant[-1]
    last = tokens[last_index]
    edits: list[Edit] = []
    has_trailing_comma = last_index + 1 < close_index and tokens[last_index + 1].kind == ","
    if newline not in content:
        prefix = " " if has_trailing_comma else ", "
        edits.append(Edit(last.end, last.end, prefix + ", ".join(missing)))
        return edits

    if not has_trailing_comma:
        edits.append(Edit(last.end, last.end, ","))
    line_start = text.rfind("\n", 0, closing.start) + 1
    closing_indent = text[line_start:closing.start]
    if closing_indent.strip():
        edits.append(Edit(closing.start, closing.start, newline + ", ".join(missing)))
    else:
        item_indent = closing_indent + "  "
        insertion = item_indent + ("," + newline + item_indent).join(missing) + newline
        edits.append(Edit(line_start, line_start, insertion))
    return edits


def _prepend_array_values(
    text: str,
    tokens: list[Token],
    matches: dict[int, int],
    array_index: int,
    values: list[str],
) -> list[Edit]:
    """Insert fields before existing fields so their overlays retain precedence."""
    close_index = matches[array_index]
    opening = tokens[array_index]
    closing = tokens[close_index]
    content = text[opening.end : closing.start]
    missing = [value for value in values if value not in content]
    if not missing:
        return []

    significant = [
        index for index in range(array_index + 1, close_index) if tokens[index].kind != ","
    ]
    if not significant:
        return _append_array_values(text, tokens, matches, array_index, missing)

    first = tokens[significant[0]]
    newline = "\r\n" if "\r\n" in text else "\n"
    if newline not in content:
        return [Edit(first.start, first.start, ", ".join(missing) + ", ")]

    line_start = text.rfind("\n", 0, first.start) + 1
    item_indent = text[line_start:first.start]
    insertion = ("," + newline + item_indent).join(missing) + "," + newline + item_indent
    return [Edit(first.start, first.start, insertion)]


def _apply_edits(text: str, edits: list[Edit]) -> str:
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end), reverse=True)
    previous_start = len(text) + 1
    for edit in ordered:
        if edit.end > previous_start:
            raise AdapterError("Internal error: overlapping playersPanel edits")
        text = text[: edit.start] + edit.replacement + text[edit.end :]
        previous_start = edit.start
    return text


def patch_players_panel(
    text: str,
    fragment_name: str = DEFAULT_FRAGMENT.name,
    include_names: bool = False,
) -> str:
    """Return a minimally patched copy of a default-style XVM playersPanel file."""
    tokens = _tokens(text)
    matches = _matches(tokens)
    try:
        root = next(index for index, token in enumerate(tokens) if token.kind == "{")
    except StopIteration as error:
        raise AdapterError("playersPanel.xc has no root object") from error
    panel = _object_property(tokens, matches, root, "playersPanel")
    edits: list[Edit] = []

    icon_references = {
        "extraFieldsLeft": '${"%s":"fields.vehicleIconLeft"}' % fragment_name,
        "extraFieldsRight": '${"%s":"fields.vehicleIconRight"}' % fragment_name,
    }
    compact_name_references = {
        "extraFieldsLeft": '${"%s":"fields.compactVehicleNameLeft"}' % fragment_name,
        "extraFieldsRight": '${"%s":"fields.compactVehicleNameRight"}' % fragment_name,
    }
    for mode_name in VISIBLE_MODES:
        mode = _object_property(tokens, matches, panel, mode_name)
        for side in ("extraFieldsLeft", "extraFieldsRight"):
            array = _array_property(tokens, matches, mode, side)
            references = [icon_references[side]]
            if include_names and mode_name in COMPACT_NAME_MODES:
                references.append(compact_name_references[side])
            edits.extend(
                _prepend_array_values(text, tokens, matches, array, references)
            )

    return _apply_edits(text, edits)


def prepare_adapter(
    players_panel: Path,
    output_directory: Path,
    fragment: Path = DEFAULT_FRAGMENT,
    include_names: bool = False,
) -> dict[str, str]:
    """Write a reviewable adapter copy; never mutate ``players_panel`` itself."""
    players_panel = players_panel.resolve()
    fragment = fragment.resolve()
    output_directory = output_directory.resolve()
    if not players_panel.is_file():
        raise FileNotFoundError(players_panel)
    if not fragment.is_file():
        raise FileNotFoundError(fragment)

    original_bytes = players_panel.read_bytes()
    has_utf8_bom = original_bytes.startswith(codecs.BOM_UTF8)
    original = original_bytes.decode("utf-8-sig")
    patched = patch_players_panel(original, fragment.name, include_names=include_names)
    patched_path = output_directory / players_panel.name
    fragment_path = output_directory / fragment.name
    if patched_path.resolve() == players_panel:
        raise AdapterError("Output directory must not be the source profile directory")
    if fragment_path.resolve() == fragment:
        raise AdapterError("Output directory must not be the adapter source directory")
    output_directory.mkdir(parents=True, exist_ok=True)
    patched_bytes = patched.encode("utf-8")
    if has_utf8_bom:
        patched_bytes = codecs.BOM_UTF8 + patched_bytes
    patched_path.write_bytes(patched_bytes)
    shutil.copy2(fragment, fragment_path)
    return {
        "source": str(players_panel),
        "patchedCopy": str(patched_path),
        "fragmentCopy": str(fragment_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare, but do not install, the optional XVM ears adapter"
    )
    parser.add_argument("--players-panel", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "build" / "xvm-adapter-preview",
    )
    parser.add_argument("--fragment", type=Path, default=DEFAULT_FRAGMENT)
    parser.add_argument(
        "--include-names",
        action="store_true",
        help="Overlay vehicle names in XVM short and medium panel modes",
    )
    arguments = parser.parse_args(argv)
    result = prepare_adapter(
        arguments.players_panel,
        arguments.output,
        arguments.fragment,
        include_names=arguments.include_names,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
