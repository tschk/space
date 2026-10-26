#!/usr/bin/env python3
"""Acquire checksum-pinned official Windows CLI bytes; never execute them."""
import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
assert not a.out.exists() or not any(a.out.iterdir()),'--out must be new or empty'
a.out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((ROOT/'fixtures/applications/windows-cli-2024.json').read_text())
for app in manifest['apps']:
    arc=app['archive']
    with urllib.request.urlopen(arc['url'],timeout=45) as r:data=r.read(32*1024*1024)
    assert hashlib.sha256(data).hexdigest()==arc['sha256'],'upstream archive changed'
    archive=a.out/arc['filename'];archive.write_bytes(data)
    if archive.suffix=='.zip':
        with zipfile.ZipFile(archive) as z:payload=z.read(arc['member'])
    else:
        # Use the host's generic libarchive reader solely to extract two named
        # bounded members. No archive paths are used as filesystem destinations.
        lib=c.CDLL('libarchive.so.13')
        for name,args,result in [('archive_read_new',[],c.c_void_p),('archive_read_support_filter_all',[c.c_void_p],c.c_int),('archive_read_support_format_all',[c.c_void_p],c.c_int),('archive_read_open_filename',[c.c_void_p,c.c_char_p,c.c_size_t],c.c_int),('archive_read_next_header',[c.c_void_p,c.POINTER(c.c_void_p)],c.c_int),('archive_entry_pathname',[c.c_void_p],c.c_char_p),('archive_read_data',[c.c_void_p,c.c_void_p,c.c_size_t],c.c_ssize_t),('archive_read_free',[c.c_void_p],c.c_int)]:
            fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
        handle=lib.archive_read_new();assert handle
        members={};wanted={arc['member'],arc['license_member']}
        try:
            assert lib.archive_read_support_filter_all(handle)==0
            assert lib.archive_read_support_format_all(handle)==0
            assert lib.archive_read_open_filename(handle,str(archive).encode(),10240)==0
            entry=c.c_void_p()
            while True:
                status=lib.archive_read_next_header(handle,c.byref(entry))
                if status==1:break
                assert status==0,'archive header failure'
                name=lib.archive_entry_pathname(entry).decode()
                if name not in wanted:continue
                assert name not in members,'duplicate requested member'
                chunks=[];total=0;buffer=c.create_string_buffer(65536)
                while True:
                    n=lib.archive_read_data(handle,buffer,len(buffer))
                    assert n>=0,'archive decode failure'
                    if n==0:break
                    total+=n;assert total<=16*1024*1024,'member exceeds bound'
                    chunks.append(buffer.raw[:n])
                members[name]=b''.join(chunks)
        finally:lib.archive_read_free(handle)
        payload=members[arc['member']]
        license=members[arc['license_member']]
        assert hashlib.sha256(license).hexdigest()==arc['license_sha256']
        (a.out/'7zip-24.09-License.txt').write_bytes(license)
    assert len(payload)==app['size_bytes'] and hashlib.sha256(payload).hexdigest()==app['sha256']
    for identity in app['embedded_identity']:assert identity.encode('ascii') in payload,'upstream embedded identity mismatch'
    (a.out/app['filename']).write_bytes(payload)
    print(app['id'],app['sha256'])
