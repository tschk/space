#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
"""Execute SparkFS initialization against bounded RAM-only NVMe fixtures.

Translate the selected .in functions mechanically to C for a host-side check.
This checks source behavior, not Inauguration lowering or hardware boot.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def function(text: str, name: str) -> str:
    match = re.search(rf"\nfn {re.escape(name)}\([^)]*\)[^{{]*\{{", text)
    if not match:
        raise ValueError(f"missing function {name}")
    end = match.end()
    depth = 1
    while depth:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[match.start() + 1:end]


def translate(text: str) -> str:
    # Only the line-oriented integer subset used by these functions is accepted.
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z][A-Za-z0-9]*)+\b",
                  lambda m: m[0].replace("-", "_"), text)
    output = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("fn "):
            match = re.fullmatch(r"fn (\w+)\(([^)]*)\) -> (Int|void) \{", line)
            if not match:
                raise ValueError(f"unsupported declaration: {line}")
            params = re.sub(r"(\w+): Int", r"int64_t \1", match[2]) or "void"
            output.append(f"{'int64_t' if match[3] == 'Int' else 'void'} {match[1]}({params}) {{")
        elif line.startswith("const "):
            output.append("static const int64_t " + line[6:] + ";")
        elif line.startswith("var "):
            output.append("static " + re.sub(r"(\w+): Int", r"int64_t \1", line[4:]) + ";")
        elif line.startswith("let "):
            output.append("int64_t " + line[4:] + ";")
        elif line.startswith("if ") or line.startswith("while "):
            match = re.fullmatch(r"(if|while) (.+) \{", line)
            if match:
                output.append(f"{match[1]} ({match[2]}) {{")
            else:
                match = re.fullmatch(r"if (.+) \{ (return(?: .+)?) \}", line)
                if not match:
                    raise ValueError(f"unsupported condition: {line}")
                output.append(f"if ({match[1]}) {{ {match[2]}; }}")
        elif line in ("}", "} else {"):
            output.append(line)
        elif line == "return":
            output.append("return;")
        else:
            output.append(line + ";")
    return "\n".join(output)


layout = (ROOT / "components/fs2-layout.in").read_text()
block = (ROOT / "components/fs2-block.in").read_text()
inode = (ROOT / "components/fs2-inode.in").read_text()
file = (ROOT / "components/fs2-file.in").read_text()
selected = [function(block, name) for name in (
    "sf-cache-init", "sf-cache-lookup", "sf-cache-find-empty", "sf-cache-install",
    "sf-bno-in-range", "sf-read-block", "sf-write-block", "sf-zero-block", "sf-mark-used")]
selected += [function(inode, name) for name in ("sf-inode-addr", "sf-read-inode", "sf-write-inode")]
selected += [function(file, name) for name in (
    "sparkfs-init", "sf-do-format", "sparkfs-format", "sparkfs-format-mem-disk")]
declarations = "\n".join(line for line in (layout + block).splitlines()
                         if line.startswith(("const ", "var ")))
translated = [translate(part) for part in selected]
prototypes = "\n".join(part.split("{", 1)[0].strip() + ";" for part in translated)

fixture = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(test) do { if (!(test)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #test); failures++; } } while (0)
static unsigned char heap[4 * 1024 * 1024], disk[32 * 1024 * 1024], before[32 * 1024 * 1024];
static size_t heap_next;
static int failures, reads, writes, read_error;
static int64_t nvme_ready;
static int64_t alloc(int64_t n) { if (n < 0 || heap_next + n > sizeof(heap)) abort(); int64_t p = (intptr_t)(heap + heap_next); heap_next += (n + 15) & -16; return p; }
static int64_t frame_alloc(void) { return alloc(4096); }
static int64_t load8(int64_t p) { return *(uint8_t *)(intptr_t)p; }
static int64_t load32(int64_t p) { uint32_t v; memcpy(&v, (void *)(intptr_t)p, 4); return v; }
static int64_t load64(int64_t p) { int64_t v; memcpy(&v, (void *)(intptr_t)p, 8); return v; }
static void store8(int64_t p, int64_t v) { *(uint8_t *)(intptr_t)p = v; }
static void store32(int64_t p, int64_t v) { uint32_t b = v; memcpy((void *)(intptr_t)p, &b, 4); }
static void store64(int64_t p, int64_t v) { memcpy((void *)(intptr_t)p, &v, 8); }
static int64_t nvme_read(int64_t lba, int64_t count, int64_t buf) { reads++; if (read_error) return -1; if (lba < 0 || count != 8 || (lba + count) * 512 > sizeof(disk)) abort(); memcpy((void *)(intptr_t)buf, disk + lba * 512, count * 512); return 0; }
static int64_t nvme_write(int64_t lba, int64_t count, int64_t buf) { if (lba < 0 || count != 8 || (lba + count) * 512 > sizeof(disk)) abort(); writes++; memcpy(disk + lba * 512, (void *)(intptr_t)buf, count * 512); return 0; }
'''
fixture += translate(declarations) + "\n" + prototypes + "\n" + "\n".join(translated)
fixture += r'''
static void reset(int present, int dirty_heap) {
  memset(heap, 0, sizeof(heap)); heap_next = 0;
  if (dirty_heap) store64((intptr_t)heap + SF_SB_TOTAL_BLOCKS, SF_DEFAULT_TOTAL_BLOCKS);
  sf_super = sf_bitmap = sf_inodes = sf_block_buf = sf_initialized = sf_disk_ready = sf_mem_disk = 0;
  sf_cache_buf = sf_cache_meta = sf_nvme_buf = 0;
  nvme_ready = present; reads = writes = read_error = 0;
}
static void unknown(int blank, int dirty_heap) {
  memset(disk, blank ? 0 : 0xa5, sizeof(disk)); memcpy(before, disk, sizeof(disk)); reset(1, dirty_heap);
  sparkfs_init();
  printf("unknown: blank=%d dirty_heap=%d reads=%d writes=%d ready=%lld unchanged=%d\n", blank, dirty_heap, reads, writes, (long long)sf_disk_ready, memcmp(disk, before, sizeof(disk)) == 0);
  CHECK(reads == 1); CHECK(writes == 0); CHECK(sf_disk_ready == 0); CHECK(memcmp(disk, before, sizeof(disk)) == 0);
}
int main(void) {
  unknown(0, 1); unknown(0, 0); unknown(1, 1); unknown(1, 0);
  memset(disk, 0xa5, sizeof(disk)); memcpy(before, disk, sizeof(disk)); reset(1, 1); read_error = 1;
  sparkfs_init(); CHECK(reads == 1); CHECK(writes == 0); CHECK(sf_disk_ready == 0); CHECK(memcmp(disk, before, sizeof(disk)) == 0);
  reset(0, 0); sparkfs_init(); CHECK(sf_disk_ready == 1); CHECK(sf_mem_disk != 0); CHECK(reads == 0); CHECK(writes == 0); CHECK(load32(sf_super) == SF_MAGIC);
  CHECK(load32(sf_inode_addr(0) + SF_IN_TYPE) == SF_TYPE_DIR);
  reset(1, 0); sparkfs_init(); CHECK(sf_disk_ready == 0); CHECK(writes == 0);
  CHECK(sparkfs_format() == 0); CHECK(sf_disk_ready == 1); CHECK(writes > 0); CHECK(load32((intptr_t)disk) == SF_MAGIC);
  memcpy(before, disk, sizeof(disk)); reset(1, 0); sparkfs_init(); CHECK(sf_disk_ready == 1); CHECK(reads > 1); CHECK(writes == 0);
  CHECK(memcmp(disk, before, sizeof(disk)) == 0); if (sf_disk_ready) CHECK(load32(sf_inode_addr(0) + SF_IN_TYPE) == SF_TYPE_DIR);
  CHECK(sf_read_block(-1, sf_block_buf) == -1); CHECK(sf_read_block(SF_DEFAULT_TOTAL_BLOCKS, sf_block_buf) == -1);
  CHECK(sf_write_block(-1, sf_block_buf) == -1); CHECK(sf_write_block(SF_DEFAULT_TOTAL_BLOCKS, sf_block_buf) == -1);
  if (failures) { fprintf(stderr, "FAIL: %d SparkFS fixture assertions\n", failures); return 1; }
  puts("PASS: unknown/blank/error NVMe preserved; memory bootstrap, explicit format, valid remount and bounds retained"); return 0;
}
'''
if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="space-sparkfs-") as temp:
        path = Path(temp)
        (path / "fixture.c").write_text(fixture)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O0", "-Werror=implicit-function-declaration",
                        str(path / "fixture.c"), "-o", str(path / "fixture")], check=True)
        subprocess.run([str(path / "fixture")], check=True)
