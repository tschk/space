#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
"""Check SCI Volume's disk boundary with RAM NVMe and component RPC stubs.

The actual loader/flush functions are translated to C; domain mapping and
component execution are mocked. This does not validate native boot or RPC ABI.
"""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
loader = SourceFileLoader("sparkfs_fixture", str(ROOT / "scripts/check-sparkfs-init.sh"))
spec = spec_from_loader(loader.name, loader)
base = module_from_spec(spec)
loader.exec_module(base)
source = (ROOT / "components/sci-loader.in").read_text()
parts = [base.translate(base.function(source, name)) for name in (
    "sci-volume-nvme-load", "sci-volume-nvme-flush", "sci-volume-rpc", "volume-rpc-call")]
constants = "\n".join(line for line in source.splitlines() if line.startswith("const ") and
                      line.split()[1] in ("SCI-MAGIC", "SCI-MAGIC-V2", "SCI-V2-HEADER", "SCI-VOLUME-GRANTS", "VOLUME-NVME-LBA", "COMP-HEAP-SIZE", "COMP-HEAP-VIRT"))
globals = "\n".join(line for line in source.splitlines() if line.startswith("var volume-"))
fixture = base.fixture.split("static void reset(", 1)[0].replace("disk[32 *", "disk[64 *").replace("before[32 *", "before[64 *")
fixture += r'''
static unsigned char shared[4096], stage[4096], image[64];
#define COMP_SHARED_VIRT ((int64_t)(intptr_t)shared)
static int64_t storage_data_page = (intptr_t)stage;
static int invocations;
static int64_t domain_create(void) { return 1; }
static void domain_map_user_code(int64_t a, int64_t b, int64_t c) { }
static void domain_map_user_data(int64_t a, int64_t b, int64_t c) { }
static int64_t sci_bind_imports(int64_t a, int64_t b, int64_t c, int64_t d) { return 0; }
static int64_t domain_create_shared_page(int64_t a, int64_t b, int64_t c, int64_t d) { return COMP_SHARED_VIRT; }
static void domain_switch(int64_t a) { }
static int64_t domain_get_current(void) { return 0; }
static void serial_write_cstr(int64_t a, const char *b) { }
static void serial_nl(int64_t a) { }
static int64_t com1(void) { return 0; }
static int64_t invoke1(int64_t entry, int64_t cap) {
  invocations++;
  int64_t op = load64(COMP_SHARED_VIRT + 16);
  store64(COMP_SHARED_VIRT + 24, 0);
  if (op == 1 && load64(cap + 40) == 0) {
    /* Simulate a new memory filesystem, never execute guest instructions. */
    store8(load64((intptr_t)heap + 16), 0x46);
  }
  if (op == 2) store64(COMP_SHARED_VIRT + 56, 0);
  if (op == 4) memcpy(shared + 768, "volume", 6);
  if (op == 4 || op == 5) store64(COMP_SHARED_VIRT + 56, 6);
  return 0;
}
'''
fixture += base.translate(constants + "\n" + globals) + "\n"
fixture += "\n".join(part.split("{", 1)[0].strip() + ";" for part in parts) + "\n" + "\n".join(parts)
fixture += r'''
static void reset_volume(int present) {
  memset(heap, 0, sizeof(heap)); memset(shared, 0, sizeof(shared)); heap_next = 0;
  reads = writes = read_error = invocations = 0; nvme_ready = present;
  volume_ready = volume_domain = volume_entry_addr = volume_cap_info = volume_heap_frames = volume_shared = volume_via_marker = 0;
  memset(image, 0, sizeof(image)); store64((intptr_t)image, SCI_MAGIC); store64((intptr_t)image + 16, 123); store64((intptr_t)image + 24, 64);
}
static void unknown(int blank, int fail_read) {
  memset(disk, blank ? 0 : 0xa5, sizeof(disk)); memcpy(before, disk, sizeof(disk)); reset_volume(1); read_error = fail_read;
  int64_t rc = sci_volume_rpc(0, (intptr_t)image);
  printf("Volume unknown: blank=%d read_error=%d rc=%lld writes=%d invocations=%d unchanged=%d\n", blank, fail_read, (long long)rc, writes, invocations, memcmp(disk, before, sizeof(disk)) == 0);
  CHECK(rc == -1); CHECK(writes == 0); CHECK(invocations == 0); CHECK(volume_ready == 0); CHECK(memcmp(disk, before, sizeof(disk)) == 0);
  CHECK(volume_rpc_call(5, 1) == -1); CHECK(writes == 0);
}
int main(int argc, char **argv) {
  unknown(0, 0); unknown(1, 0); unknown(0, 1);
  reset_volume(0); CHECK(sci_volume_rpc(0, (intptr_t)image) == 0); CHECK(volume_ready == 1); CHECK(invocations == 4); CHECK(writes == 0);
  /* Prepare an explicitly initialized synthetic backing, using SparkFS's RAM formatter. */
  sf_super = sf_bitmap = sf_inodes = sf_block_buf = sf_initialized = sf_disk_ready = sf_mem_disk = 0;
  sf_cache_buf = sf_cache_meta = sf_nvme_buf = 0; heap_next = 0; sparkfs_init();
  memset(disk, 0, sizeof(disk)); memcpy(disk + 65536 * 512, (void *)(intptr_t)sf_mem_disk, SF_MEM_DISK_SIZE);
  if (argc == 2) { FILE *out = fopen(argv[1], "r+b"); if (!out || fseek(out, 65536 * 512, SEEK_SET) || fwrite(disk + 65536 * 512, 1, SF_MEM_DISK_SIZE, out) != SF_MEM_DISK_SIZE || fclose(out)) return 1; }
  reset_volume(1); CHECK(sci_volume_rpc(0, (intptr_t)image) == 0); CHECK(volume_ready == 1); CHECK(invocations == 4); CHECK(reads == 256); CHECK(writes == 256);
  CHECK(volume_rpc_call(5, 1) == 6); CHECK(writes == 512);
  if (failures) return 1;
  puts("PASS: unknown/blank/read-error backing preserved; RAM-only and initialized-backed RPC controls retained"); return 0;
}
'''
args = []
if len(sys.argv) == 3 and sys.argv[1] == "--seed":
    image_path = Path(sys.argv[2])
    if image_path.is_symlink() or not image_path.is_file() or image_path.stat().st_size != 64 * 1024 * 1024:
        raise SystemExit("--seed requires an existing regular 64 MiB test image")
    args = [str(image_path)]
elif len(sys.argv) != 1:
    raise SystemExit("usage: check-volume-preservation.sh [--seed test-image]")
with tempfile.TemporaryDirectory(prefix="space-volume-") as temp:
    path = Path(temp)
    (path / "fixture.c").write_text(fixture)
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O0", "-Werror=implicit-function-declaration",
                    str(path / "fixture.c"), "-o", str(path / "fixture")], check=True)
    subprocess.run([str(path / "fixture"), *args], check=True)
