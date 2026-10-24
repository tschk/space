#!/usr/bin/env python3
"""Explicit Space packaging policy for the bounded native GUI applications."""
import struct
import hashlib
from pathlib import Path

POLICIES = {"space.app.gui/GuiCalc", "space.app.gui/GuiEditor",
            "space.app.gui/GuiWindowCalc", "space.app.gui/GuiWindowEditor"}
CANVAS = (0x5350414345434E56, 1, 768, 384, 3072, 1179648, 1, 0)
PROTECTED_POLICIES = {"space.app.gui/GuiProtectedWindowCalc", "space.app.gui/GuiProtectedWindowEditor",
                      "space.app.gui/GuiProtectedTerminalView"}
NATIVE_PROTECTED_MAGIC = 0x5350434E41545631
NATIVE_GUI_PAGED = 3
PROTECTED_BASE = 0x60000000


def protected_layout(image, metadata, editor):
    """Validate exact generic bytes before any Space-specific transformation."""
    layout = metadata.get("sci_layout")
    fields = ("version", "image_size", "load_base", "page_size", "text_offset",
              "text_size", "data_offset", "data_size", "binding_offset", "binding_size")
    if not isinstance(layout, dict) or any(type(layout.get(field)) is not int for field in fields):
        raise ValueError("protected GUI requires integer generic SCI layout")
    if layout.get("artifact_sha256") != hashlib.sha256(image).hexdigest():
        raise ValueError("protected GUI metadata does not bind exact raw SCI bytes")
    if (layout["version"], layout["image_size"], layout["load_base"],
        layout["page_size"], layout["text_offset"]) != (1, len(image), PROTECTED_BASE, 4096, 64):
        raise ValueError("protected GUI layout identity mismatch")
    text, data, size, binding, binding_size = (layout[field] for field in
        ("text_size", "data_offset", "data_size", "binding_offset", "binding_size"))
    if not (128 < len(image) <= 0x200000 - 128 and 0 < text <= len(image) - 64
            and (64 + text + 4095) & ~4095 <= data <= len(image) and data % 4096 == 0
            and 0 <= size <= len(image) - data and binding % 4096 == 0
            and (data + size + 4095) & ~4095 <= binding <= len(image)
            and binding_size > 0 and binding + binding_size == len(image)):
        raise ValueError("protected GUI layout ranges are not independently page aligned")
    if any(image[64 + text:data]) or any(image[data + size:binding]):
        raise ValueError("protected GUI section padding must match generic zero padding")
    expected_text = [{"name": ".text", "offset": 64, "size": text, "flags": "rx"}]
    expected_data = [{"name": ".data", "offset": data, "size": size, "flags": "rw"}] if size else []
    if metadata.get("code_sections") != expected_text or metadata.get("data_sections") != expected_data:
        raise ValueError("protected GUI section metadata disagrees with SCI layout")
    if (not isinstance(metadata.get("memory"), dict)
            or type(metadata["memory"].get("static_data")) is not int
            or metadata["memory"]["static_data"] != size):
        raise ValueError("protected GUI static data metadata mismatch")
    _, _, entry, _, exports, export_off, imports, import_off = struct.unpack_from("<8Q", image)
    if not (entry == PROTECTED_BASE + 64 and 0 < exports <= 128 and imports <= 128
            and export_off == binding and import_off == export_off + exports * 16
            and import_off + imports * 16 < len(image)):
        raise ValueError("protected GUI binding table layout mismatch")
    names = import_off + imports * 16

    def name_at(offset):
        if not names <= offset < len(image):
            raise ValueError("protected GUI symbol outside binding name pool")
        end = image.find(b"\0", offset, min(len(image), offset + 129))
        if end < 0 or end == offset:
            raise ValueError("protected GUI symbol is not a bounded C string")
        try:
            return image[offset:end].decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("protected GUI symbol must be ASCII") from error

    exported = set()
    entry_found = False
    for index in range(exports):
        name, offset = struct.unpack_from("<2Q", image, export_off + index * 16)
        symbol = name_at(name)
        if offset >= text or symbol in exported:
            raise ValueError("protected GUI export outside text or duplicated")
        exported.add(symbol)
        entry_found |= symbol == "client-entry" and offset == 0
    if not entry_found:
        raise ValueError("protected GUI entry export is missing")
    allowed = {"abort", "malloc", "calloc", "realloc", "free",
               "chan-page-send-frame", "chan-page-recv-frame"}
    if editor:
        allowed |= {"gui-note-read", "gui-note-write"}
    sites = set()
    for index in range(imports):
        name, site = struct.unpack_from("<2Q", image, import_off + index * 16)
        if (name_at(name) not in allowed or site in sites or site + 5 > text
                or image[64 + site:64 + site + 5] != b"\xe8\0\0\0\0"):
            raise ValueError("protected GUI import is not an admitted raw text call")
        sites.add(site)
    return text, data, size


def translate(image, metadata, protected=False):
    policies = PROTECTED_POLICIES if protected else POLICIES
    if not isinstance(metadata, dict) or metadata.get("component") not in policies:
        raise ValueError("unexpected native GUI component identity")
    window = protected or metadata["component"] in {"space.app.gui/GuiWindowCalc", "space.app.gui/GuiWindowEditor"}
    display = ["present", "window"] if window else ["present"]
    expected = [("memory", "GuiMemory", ["map"]), ("display", "GuiDisplay", display)]
    mask = 20
    editor = metadata["component"] in {"space.app.gui/GuiEditor", "space.app.gui/GuiWindowEditor", "space.app.gui/GuiProtectedWindowEditor"}
    if editor:
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
    layout = protected_layout(image, metadata, editor) if protected else None
    result = bytearray(image)
    struct.pack_into("<Q", result, 8, mask)
    if window:
        result.extend(struct.pack("<8Q", *CANVAS))
        if protected:
            result.extend(struct.pack("<8Q", NATIVE_PROTECTED_MAGIC, 1,
                                      NATIVE_GUI_PAGED, len(image), *layout, 0))
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
    parser.add_argument("--protected", action="store_true",
                        help="explicit paged CPL3 GUI profile; requires exact hash-bound generic layout")
    args = parser.parse_args()
    try:
        packed = translate(args.image.read_bytes(), json.loads(args.metadata.read_text()), args.protected)
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
