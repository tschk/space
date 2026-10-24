#!/usr/bin/env python3
"""Bind generic compiler metadata to an explicit bounded native execution profile."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC = 0x5350434e41545631


def require(test, message):
    if not test:
        raise ValueError(message)


def translate(raw, metadata, immutable=False):
    image = bytearray(raw)
    require(isinstance(metadata, dict), 'component metadata must be an object')
    identity = metadata.get('component')
    require(isinstance(identity, str) and identity.strip() == identity and identity and '\0' not in identity,
            'nonempty component identity required')
    require(metadata.get('target') == 'x86_64-unknown-none' and metadata.get('entry') == 'native-entry',
            'unexpected protected component target or entry')
    require(64 < len(image) <= 0x200000 - 64, 'image must fit the bounded SCI v2 profile')
    magic, ordinals, entry, size, exports, export_off, imports, import_off = struct.unpack_from('<8Q', image)
    require(magic == 0x5343490000000002 and size == len(image) and entry == 0x60000040,
            'SCI v2 extent/base mismatch')
    caps = metadata.get('capabilities_required')
    require(isinstance(caps, list) and all(isinstance(cap, dict) for cap in caps), 'capability declarations required')
    require(metadata.get('capabilities_exported') == caps, 'exported capability declarations disagree')
    mask = 0
    seen = set()
    for cap in caps:
        name = cap.get('name')
        require(isinstance(name, str) and name not in seen, 'duplicate capability declaration')
        seen.add(name)
        if name == 'serial' and cap.get('capability_type') == 'DebugConsole' and cap.get('args') == ['write']:
            mask |= 1
        elif name == 'memory' and cap.get('capability_type') == 'NativeMemory' and cap.get('args') == ['allocate']:
            mask |= 4
        else:
            raise ValueError('unsupported protected component capability declaration')
    require(mask & 4 != 0, 'explicit NativeMemory(allocate) declaration required')
    require(ordinals == (1 << len(caps)) - 1, 'compiler capability ordinals disagree with declarations')
    original = len(image)
    if immutable:
        profile, text, data, data_size = 1, original - 64, 0, 0
    else:
        layout = metadata.get('sci_layout')
        fields = ('version', 'image_size', 'load_base', 'page_size', 'text_offset', 'text_size',
                  'data_offset', 'data_size', 'binding_offset', 'binding_size')
        require(isinstance(layout, dict) and all(type(layout.get(field)) is int for field in fields),
                'integer sci_layout required; immutable-image is a separate limited profile')
        require(tuple(layout[field] for field in fields[:5]) == (1, original, 0x60000000, 4096, 64),
                'sci_layout identity mismatch')
        require(layout.get('artifact_sha256') == hashlib.sha256(image).hexdigest(), 'sci_layout does not bind the exact artifact')
        text, data, data_size = (layout[field] for field in ('text_size', 'data_offset', 'data_size'))
        require(0 < text <= original - 64 and ((64 + text + 4095) & ~4095) <= data <= original
                and data % 4096 == 0 and 0 <= data_size <= original - data, 'invalid text/data ranges')
        binding, binding_size = layout['binding_offset'], layout['binding_size']
        require(binding % 4096 == 0 and ((data + data_size + 4095) & ~4095) <= binding <= original
                and binding_size > 0 and binding + binding_size == original, 'invalid independently aligned binding range')
        require(not any(image[64 + text:data]) and not any(image[data + data_size:binding]), 'section padding is not zero')
        require(metadata.get('code_sections') == [{'name': '.text', 'offset': 64, 'size': text, 'flags': 'rx'}],
                'code sections disagree with sci_layout')
        expected_data = [{'name': '.data', 'offset': data, 'size': data_size, 'flags': 'rw'}] if data_size else []
        require(metadata.get('data_sections') == expected_data, 'data sections disagree with sci_layout')
        require(isinstance(metadata.get('memory'), dict) and type(metadata['memory'].get('static_data')) is int
                and metadata['memory']['static_data'] == data_size, 'static data disagrees with sci_layout')
        require(export_off == binding, 'binding table disagrees with sci_layout')
        profile = 2
    # Validate actual tables and raw call sites even for the explicit legacy RX profile.
    require(0 < exports <= 128 and imports <= 128 and 64 <= export_off <= original
            and import_off == export_off + exports * 16 and import_off + imports * 16 < original,
            'invalid SCI binding tables')
    names = import_off + imports * 16

    def name_at(offset):
        require(names <= offset < original, 'symbol outside binding name pool')
        end = image.find(b'\0', offset, min(original, offset + 129))
        require(end > offset, 'symbol must be a bounded nonempty C string')
        try:
            return image[offset:end].decode('ascii')
        except UnicodeDecodeError as error:
            raise ValueError('symbol must be ASCII') from error

    code_limit = text if not immutable else export_off - 64
    exported = set()
    entry_found = False
    for index in range(exports):
        name, offset = struct.unpack_from('<2Q', image, export_off + index * 16)
        symbol = name_at(name)
        require(offset < code_limit and symbol not in exported, 'duplicate export or export outside text')
        exported.add(symbol)
        entry_found |= symbol == 'native-entry' and offset == 0
    require(entry_found, 'native entry export missing or mismatched')
    sites = set()
    for index in range(imports):
        name, site = struct.unpack_from('<2Q', image, import_off + index * 16)
        name_at(name)
        require(site not in sites and site + 5 <= code_limit and image[64 + site:64 + site + 5] == b'\xe8\0\0\0\0',
                'duplicate or invalid raw import call site')
        sites.add(site)
    struct.pack_into('<Q', image, 8, mask)
    image.extend(struct.pack('<8Q', MAGIC, 1, profile, original, text, data, data_size, 0))
    struct.pack_into('<Q', image, 24, len(image))
    return bytes(image)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('metadata', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--immutable-image', action='store_true', help='explicit RX-only profile; mutable image writes fault')
    a = p.parse_args()
    try:
        image = translate(a.image.read_bytes(), json.loads(a.metadata.read_text()), a.immutable_image)
    except (ValueError, TypeError, OSError) as error:
        p.error(str(error))
    a.output.write_bytes(image)
    print(f'protected SCI profile{1 if a.immutable_image else 2}: {len(image)} bytes, grants0x{struct.unpack_from("<Q", image, 8)[0]:x}')


if __name__ == '__main__':
    main()
