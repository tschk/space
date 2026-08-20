"exec" "python3" "$0" "$@"
# check-spdp-protocol.sh — Host-side SPDP wire-format + compositor parse checks.
# No QEMU / compiler. Run: bash scripts/check-spdp-protocol.sh
"""Validate protocol/display.in against the compositor's 32-byte SPDP frames.

The kernel parser in components/display.in (dsp-run / dsp-handle-msg) is the
source of truth: four little-endian u64 words, no argc field.
"""
import os, re, struct, sys

passed, failed = 0, 0

def check(label, ok):
    global passed, failed
    if ok:
        print(f"  ok: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1

def parse_consts(text):
    found = {}
    for name, val in re.findall(r"^const (SPDP-[A-Z0-9-]+) = (\d+)", text, re.M):
        found[name] = int(val)
    return found

def encode(obj_id, opcode, arg0, arg1):
    return struct.pack("<QQQQ", obj_id, opcode, arg0, arg1)

def decode(buf):
    if len(buf) != 32:
        raise ValueError("SPDP frame must be 32 bytes")
    return struct.unpack("<QQQQ", buf)

def pack_attach(pool_id, offset):
    return ((pool_id & 0xFFFFFFFF) << 32) | (offset & 0xFFFFFFFF)

def pack_geometry(x, y, w, h):
    return ((x & 0xFFFF) << 48) | ((y & 0xFFFF) << 32) | ((w & 0xFFFF) << 16) | (h & 0xFFFF)

def unpack_attach(packed):
    return (packed >> 32) & 0xFFFFFFFF, packed & 0xFFFFFFFF

def unpack_geometry(packed):
    return (
        (packed >> 48) & 0xFFFF,
        (packed >> 32) & 0xFFFF,
        (packed >> 16) & 0xFFFF,
        packed & 0xFFFF,
    )

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    space = os.path.abspath(os.path.join(here, ".."))
    proto_path = os.path.join(space, "protocol", "display.in")
    display_path = os.path.join(space, "components", "display.in")
    ci_path = os.path.join(space, ".github", "workflows", "ci.yml")

    proto = open(proto_path).read()
    display = open(display_path).read()
    ci = open(ci_path).read()
    consts = parse_consts(proto)

    print("[1/4] Protocol constants and frame layout...")
    check("SPDP-MSG-SIZE == 32", consts.get("SPDP-MSG-SIZE") == 32)
    check("SPDP-HEADER-SIZE == 16 (obj_id + opcode, no argc)",
          consts.get("SPDP-HEADER-SIZE") == 16)
    check("header + two args == message size",
          consts.get("SPDP-HEADER-SIZE", 0) + 16 == consts.get("SPDP-MSG-SIZE", -1))
    check("protocol does not reserve an argc word",
          "argc" not in proto.lower())

    for name, val in [
        ("SPDP-OBJ-DISPLAY", 1),
        ("SPDP-OBJ-COMPOSITOR", 2),
        ("SPDP-OBJ-SHM", 3),
        ("SPDP-OBJ-SEAT", 4),
        ("SPDP-OBJ-SURFACE", 5),
        ("SPDP-COMPOSITOR-CREATE-SURFACE", 0),
        ("SPDP-SURFACE-ATTACH", 1),
        ("SPDP-SURFACE-DAMAGE", 2),
        ("SPDP-SURFACE-COMMIT", 3),
        ("SPDP-SHM-CREATE-POOL", 0),
    ]:
        check(f"{name} == {val}", consts.get(name) == val)

    print("[2/4] Encode/decode packed arguments...")
    surface = consts.get("SPDP-OBJ-SURFACE", 5)
    attach_op = consts.get("SPDP-SURFACE-ATTACH", 1)
    frame = encode(surface, attach_op, 7, pack_attach(3, 0x1000))
    check("encoded frame is 32 bytes", len(frame) == 32)
    obj_id, opcode, arg0, arg1 = decode(frame)
    check("decode obj_id/opcode/arg0", obj_id == surface and opcode == attach_op and arg0 == 7)
    pool, off = unpack_attach(arg1)
    check("SURFACE-ATTACH packs pool<<32 | offset", pool == 3 and off == 0x1000)

    gx, gy, gw, gh = unpack_geometry(pack_geometry(100, 100, 64, 64))
    check("SURFACE-DAMAGE packs x<<48|y<<32|w<<16|h",
          (gx, gy, gw, gh) == (100, 100, 64, 64))

    # A client that followed the old argc-at-offset-16 layout would put argc in
    # the word the compositor reads as arg0. That must not be the spec.
    wrong = struct.pack("<QQQQ", 5, 1, 2, pack_attach(3, 0x1000))  # argc=2 as arg0
    w_obj, w_op, w_a0, w_a1 = decode(wrong)
    check("argc-shaped frame is distinguishable from attach(sid=7)",
          not (w_a0 == 7 and unpack_attach(w_a1) == (3, 0x1000)))
    check("argc-shaped frame's arg0 is the bogus argc, not surface_id", w_a0 == 2)

    print("[3/4] Compositor parser matches the four-word layout...")
    check("dsp-run stores word 0 at dsp-msg+0", "store64(dsp-msg + 0, chan-recv(ch))" in display)
    check("dsp-run stores word 1 at dsp-msg+8", "store64(dsp-msg + 8, chan-recv(ch))" in display)
    check("dsp-run stores word 2 at dsp-msg+16", "store64(dsp-msg + 16, chan-recv(ch))" in display)
    check("dsp-run stores word 3 at dsp-msg+24", "store64(dsp-msg + 24, chan-recv(ch))" in display)
    check("dsp-run loads obj-id from +0", "let obj-id = load64(dsp-msg + 0)" in display)
    check("dsp-run loads opcode from +8", "let opcode = load64(dsp-msg + 8)" in display)
    check("dsp-run loads arg0 from +16", "let arg0 = load64(dsp-msg + 16)" in display)
    check("dsp-run loads arg1 from +24", "let arg1 = load64(dsp-msg + 24)" in display)
    check("dsp-init allocates the hoisted 32-byte message buffer",
          "dsp-msg = alloc(SPDP-MSG-SIZE)" in display)
    check("dsp-handle-msg dispatches SURFACE on SPDP-OBJ-SURFACE",
          "obj-id == SPDP-OBJ-SURFACE" in display)
    check("display.in does not re-declare SPDP-OBJ-SURFACE",
          "const SPDP-OBJ-SURFACE" not in display)

    print("[4/4] CI compile entry matches kernel-entry...")
    check("ci.yml uses --entry kernel-entry", "--entry kernel-entry" in ci)
    check("ci.yml does not use C-style kernel_entry", "--entry kernel_entry" not in ci)
    check("ci.yml runs check-spdp-protocol.sh", "scripts/check-spdp-protocol.sh" in ci)

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: SPDP protocol/parser contract mismatch.")
        sys.exit(1)
    print("PASS: SPDP 32-byte frames match the compositor parser.")

if __name__ == "__main__":
    main()
