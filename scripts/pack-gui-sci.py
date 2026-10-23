#!/usr/bin/env python3
"""Explicit Space packaging policy for the bounded native GUI applications."""
import struct
from pathlib import Path

POLICIES = {"space.app.gui/GuiCalc", "space.app.gui/GuiEditor",
            "space.app.gui/GuiWindowCalc", "space.app.gui/GuiWindowEditor"}
CANVAS = (0x5350414345434E56, 1, 768, 384, 3072, 1179648, 1, 0)


def translate(image, metadata):
    if not isinstance(metadata, dict) or metadata.get("component") not in POLICIES:
        raise ValueError("unexpected native GUI component identity")
    window = metadata["component"] in {"space.app.gui/GuiWindowCalc", "space.app.gui/GuiWindowEditor"}
    display = ["present", "window"] if window else ["present"]
    expected = [("memory", "GuiMemory", ["map"]), ("display", "GuiDisplay", display)]
    mask = 20
    if metadata["component"] in {"space.app.gui/GuiEditor", "space.app.gui/GuiWindowEditor"}:
        expected.append(("storage", "GuiNoteFile", ["read", "write"]))
        mask |= 32
    if metadata.get("target") != "x86_64-unknown-none" or metadata.get("entry") != "client-entry":
        raise ValueError("unexpected native GUI target or entry")
    caps = metadata.get("capabilities_required")
    if not isinstance(caps, list) or not all(isinstance(c, dict) for c in caps) or [(c.get("name"), c.get("capability_type"), c.get("args")) for c in caps] != expected:
        raise ValueError("unexpected native GUI capabilities")
    if metadata.get("capabilities_exported") != caps:
        raise ValueError("unexpected native GUI exported capabilities")
    if len(image) < 64 or struct.unpack_from("<Q", image)[0] != 0x5343490000000002:
        raise ValueError("expected native GUI SCI v2 image")
    if struct.unpack_from("<Q", image, 24)[0] != len(image):
        raise ValueError("native GUI SCI size mismatch")
    if struct.unpack_from("<Q", image, 8)[0] != (1 << len(caps)) - 1:
        raise ValueError("unexpected native GUI compiler capability ordinals")
    result = bytearray(image)
    struct.pack_into("<Q", result, 8, mask)
    if window:
        result.extend(struct.pack("<8Q", *CANVAS))
        struct.pack_into("<Q", result, 24, len(result))
    return bytes(result)


def main():
    import argparse
    import json
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        packed = translate(args.image.read_bytes(), json.loads(args.metadata.read_text()))
    except (ValueError, OSError, TypeError) as error:
        raise SystemExit(f"native GUI packaging refused: {error}") from error
    with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as temporary:
        path = Path(temporary.name)
        temporary.write(packed)
    try:
        path.replace(args.output)
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
