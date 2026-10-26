#!/usr/bin/env python3
"""Independent actual Linux syscall-width oracle; all files are disposable."""
import ctypes
import json
import os
from pathlib import Path
import tempfile

libc=ctypes.CDLL(None,use_errno=True)
libc.syscall.restype=ctypes.c_long
rows=[]
def call(name,number,*arguments):
    ctypes.set_errno(0)
    result=libc.syscall(ctypes.c_long(number),*(ctypes.c_long(value) if isinstance(value,int) else value for value in arguments))
    rows.append({'name':name,'return':result,'errno':ctypes.get_errno()})
    return result

with tempfile.TemporaryDirectory(prefix='space-linux-width-host-') as directory:
    path=Path(directory)/'input'
    path.write_bytes(b'x'*45)
    fd=call('openat upper32 dirfd/flags',257,0x12345678ffffff9c,ctypes.c_char_p(bytes(path)),0xabcdef1200000000,0)
    assert fd>=3
    try:
        assert call('write upper32 fd with zero size',1,0x1234567800000001,0,0)==0
        assert call('lseek upper32 fd/whence',8,0x1234567800000000|fd,0,0xabcdef1200000002)==45
        # Host Linux additionally reports O_LARGEFILE; compare actual access.
        assert call('fcntl upper32 fd/cmd',72,0x1234567800000000|fd,0xabcdef1200000003,0)&3==0
        stat=ctypes.create_string_buffer(144)
        assert call('newfstatat upper32 dirfd/flags',262,0x12345678ffffff9c,ctypes.c_char_p(bytes(path)),ctypes.byref(stat),0xabcdef1200000100)==0
        assert call('negative low32 fd',0,0x12345678ffffffff,0,0)==-1 and ctypes.get_errno()==9
        assert call('getpid upper32 syscall number',0x100000027)==os.getpid()
        assert call('full64 off_t',8,fd,0x100000000,0)==0x100000000
        os.lseek(fd,0,0)
        buffer=ctypes.create_string_buffer(64)
        # The file holds45 bytes, so this full-size short read copies at most45.
        assert call('full64 size_t short read',0,fd,ctypes.byref(buffer),0x100000000)==45
        os.lseek(fd,0,0)
        assert call('full64 pointer EFAULT',0,fd,ctypes.addressof(buffer)|0x1234000000000000,1)==-1 and ctypes.get_errno()==14
    finally:
        os.close(fd)
print(json.dumps({'status':'passed','syscalls':rows},indent=2))
