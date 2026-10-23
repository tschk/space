#!/usr/bin/env python3
"""Explicit Space packaging policy for the bounded native GUI applications."""
import importlib.util
from pathlib import Path

POLICIES = {"space.app.gui/GuiCalc", "space.app.gui/GuiEditor"}


def translate(image, metadata):
    if not isinstance(metadata, dict) or metadata.get("component") not in POLICIES:
        raise ValueError("unexpected native GUI component identity")
    # Reuse the checked SCI envelope/ordinal checks after this policy validates
    # its own identities and exact named interfaces. Never widen the rights.
    expected = [("memory", "GuiMemory", ["map"]), ("display", "GuiDisplay", ["present"])]
    caps = metadata.get("capabilities_required")
    if not isinstance(caps, list) or not all(isinstance(c, dict) for c in caps) or [(c.get("name"), c.get("capability_type"), c.get("args")) for c in caps] != expected:
        raise ValueError("unexpected native GUI capabilities")
    if metadata.get("capabilities_exported") != caps:
        raise ValueError("unexpected native GUI exported capabilities")
    normalized = dict(metadata)
    normalized["component"] = "space.spdp.proof/PixelProof"
    normalized["capabilities_required"] = [dict(c, capability_type={"memory": "PixelMemory", "display": "PixelDisplay"}[c["name"]]) for c in caps]
    normalized["capabilities_exported"] = normalized["capabilities_required"]
    spec = importlib.util.spec_from_file_location("space_pixel_policy", Path(__file__).with_name("pack-spdp-sci.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.translate(image, normalized)


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
