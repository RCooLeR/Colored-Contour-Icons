"""Small reader for World of Tanks binary XML files.

The format description follows the GPL-3.0 BXML reader from WotDataLib,
which in turn credits World of Tanks Mod Tools by KatzSmile.
"""

from __future__ import annotations

import base64
import io
import struct
from typing import Any, BinaryIO


MAGIC = 0x62A14E45
TYPE_DICT = 0
TYPE_STRING = 1
TYPE_INT = 2
TYPE_FLOATS = 3
TYPE_BOOL = 4
TYPE_BASE64 = 5


class BxmlError(ValueError):
    pass


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise BxmlError("Unexpected end of BXML data")
    return value


def _unpack(stream: BinaryIO, fmt: str) -> Any:
    return struct.unpack(fmt, _read_exact(stream, struct.calcsize(fmt)))[0]


def loads(data: bytes) -> dict[str, Any]:
    stream = io.BytesIO(data)
    if _unpack(stream, "<I") != MAGIC:
        raise BxmlError("Not a World of Tanks BXML document")
    _read_exact(stream, 1)

    names: list[str] = []
    while True:
        raw = bytearray()
        while True:
            byte = _read_exact(stream, 1)
            if byte == b"\0":
                break
            raw.extend(byte)
        if not raw:
            break
        names.append(raw.decode("utf-8"))

    result = _read_dict(stream, names)
    if not isinstance(result, dict):
        raise BxmlError("BXML root is not a dictionary")
    return result


def _read_dict(stream: BinaryIO, names: list[str]) -> dict[str, Any]:
    child_count = _unpack(stream, "<h")
    end_and_type = _unpack(stream, "<I")
    own_length = end_and_type & 0x0FFFFFFF
    own_type = end_and_type >> 28
    if own_type == TYPE_DICT:
        raise BxmlError("Dictionary cannot be its own scalar value")

    previous_end = own_length
    children: list[tuple[str, int, int]] = []
    for _ in range(child_count):
        name_index = _unpack(stream, "<h")
        if not 0 <= name_index < len(names):
            raise BxmlError("Invalid BXML name index")
        end_and_type = _unpack(stream, "<I")
        end = end_and_type & 0x0FFFFFFF
        length = end - previous_end
        previous_end = end
        children.append((names[name_index], length, end_and_type >> 28))

    result: dict[str, Any] = {}
    if own_length > 0 or own_type != TYPE_STRING:
        result[""] = _read_data(stream, names, own_type, own_length)
    for name, length, value_type in children:
        result[name] = _read_data(stream, names, value_type, length)
    return result


def _read_data(stream: BinaryIO, names: list[str], value_type: int, length: int) -> Any:
    if value_type == TYPE_DICT:
        return _read_dict(stream, names)
    if value_type == TYPE_STRING:
        return _read_exact(stream, length).decode("utf-8")
    if value_type == TYPE_INT:
        if length == 0:
            return 0
        formats = {1: "<b", 2: "<h", 4: "<i"}
        if length not in formats:
            raise BxmlError("Unexpected integer length: %d" % length)
        return _unpack(stream, formats[length])
    if value_type == TYPE_FLOATS:
        if length % 4:
            raise BxmlError("Invalid float-array length")
        values = [_unpack(stream, "<f") for _ in range(length // 4)]
        return values[0] if len(values) == 1 else values
    if value_type == TYPE_BOOL:
        if length == 0:
            return False
        if length != 1 or _unpack(stream, "<b") != 1:
            raise BxmlError("Invalid boolean value")
        return True
    if value_type == TYPE_BASE64:
        return base64.b64encode(_read_exact(stream, length)).decode("ascii")
    raise BxmlError("Unknown BXML value type: %d" % value_type)
