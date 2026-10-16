#!/usr/bin/env python3
"""Bind the pixel-proof SCI's ordinal capability mask to Space's named rights.

This packaging policy is deliberately limited to the checked-in PixelProof.
The compiler's canonical SCI sidecar supplies names and operations.
"""
import argparse
import json
from pathlib import Path
import struct
import tempfile

EXPECTED = {
    'memory': ('PixelMemory', ['map'], 4),
    'display': ('PixelDisplay', ['present'], 16),
}


def translate(image, metadata):
    if not isinstance(metadata, dict):
        raise ValueError('malformed component metadata')
    if metadata.get('component') != 'space.spdp.proof/PixelProof':
        raise ValueError('unexpected component identity')
    if metadata.get('target') != 'x86_64-unknown-none' or metadata.get('entry') != 'client-entry':
        raise ValueError('unexpected target or entry')
    capabilities = metadata.get('capabilities_required')
    if not isinstance(capabilities, list):
        raise ValueError('missing capability metadata')
    seen = set()
    mask = 0
    for capability in capabilities:
        if not isinstance(capability, dict):
            raise ValueError('malformed capability')
        name = capability.get('name')
        if name not in EXPECTED or name in seen:
            raise ValueError('unknown or duplicate capability')
        interface, operations, bit = EXPECTED[name]
        if capability.get('capability_type') != interface or capability.get('args') != operations:
            raise ValueError('unexpected capability rights')
        seen.add(name)
        mask |= bit
    if seen != set(EXPECTED):
        raise ValueError('missing required pixel capabilities')
    if metadata.get('capabilities_exported') != capabilities:
        raise ValueError('unexpected exported capability metadata')
    if len(image) < 64 or struct.unpack_from('<Q', image)[0] != 0x5343490000000002:
        raise ValueError('expected SCI v2 image')
    if struct.unpack_from('<Q', image, 24)[0] != len(image):
        raise ValueError('SCI image size mismatch')
    if struct.unpack_from('<Q', image, 8)[0] != (1 << len(capabilities)) - 1:
        raise ValueError('unexpected compiler ordinal capability mask')
    result = bytearray(image)
    struct.pack_into('<Q', result, 8, mask)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('metadata', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    # Complete all validation before creating/replacing any output artifact.
    try:
        packed = translate(args.image.read_bytes(), json.loads(args.metadata.read_text()))
    except (ValueError, OSError, TypeError) as error:
        raise SystemExit(f'SCI capability packaging refused: {error}') from error
    with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as temporary:
        path = Path(temporary.name)
        temporary.write(packed)
    try:
        path.replace(args.output)
    finally:
        path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
