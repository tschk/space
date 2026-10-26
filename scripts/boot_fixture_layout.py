"""Strict host-side placement of owned test fixtures below the unchanged heap."""

IMAGE_BASE = 0x100000
HEAP_BASE = 0x300000


def stage_fixture(kernel, payload, physical):
    """Preserve input bytes and reject code/fixture/heap overlap before writing."""
    if physical < IMAGE_BASE or physical >= HEAP_BASE or physical & 4095:
        raise ValueError('fixture address outside page-aligned boot window')
    if not payload or len(payload) > HEAP_BASE-physical:
        raise ValueError('fixture overlaps reserved kernel heap')
    offset=physical-IMAGE_BASE
    if len(kernel)>offset:
        raise ValueError('kernel overlaps staged fixture')
    return bytes(kernel)+bytes(offset-len(kernel))+bytes(payload)
