#!/usr/bin/env python3
"""Real PS/2 vi edits across cold NVMe boots, with filesystem-only ELF reopen.

Creates its own disk. Only installation boot receives the original ELF loader;
later boots use native immutable file observations. No host disk seeding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--app',type=Path,required=True)
p.add_argument('--oracle-python',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--utc',action='store_true')
a=p.parse_args();out=a.out.resolve();compiler=a.compiler.resolve();app=a.app.resolve()
assert not out.exists() or not any(out.iterdir()),'preserve prior evidence'
out.mkdir(parents=True,exist_ok=True)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest=ROOT/'fixtures/applications/busybox-vi-1.36.1.json'
pin=json.loads(manifest.read_text())['apps'][0]
assert sha(app)==pin['sha256'] and app.stat().st_size==pin['size_bytes']
paths=[path for group in ('components','kernel','protocol','services','fixtures/terminal-session') for path in (ROOT/group).rglob('*.in')]
paths += [ROOT/name for name in ('boot/multiboot.asm','scripts/pack-gui-sci.py','scripts/pack-sci-image.py',
          'scripts/check-terminal-view-pixels.py','assets/fonts/desktop/DejaVuSansMono.ttf')]+[manifest,Path(__file__)]
frozen={str(path.relative_to(ROOT)):path.read_bytes() for path in paths};snapshot=out/'source'
for name,data in frozen.items():
    path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
report=dict(status='running',goal_status='OPEN',scope='Original protected vi, private SCI terminal, real PS2, installed ELF and text across3 cold NVMe boots; no ordinary launcher/resize/concurrency claim',
            compiler_sha256=sha(compiler),application_sha256=sha(app),filesystem_version=2 if a.utc else 1,
            source_sha256={name:hashlib.sha256(data).hexdigest() for name,data in frozen.items()},boots=[])
disk=out/'owned.raw'
with disk.open('xb') as file:file.truncate(64*1024*1024)

def disk_file(name):
    # Independent read-only root/direct/indirect/inline parser. Schemas1/2
    # preserve these fields; timestamps are not used to manufacture content.
    data=disk.read_bytes();u32=lambda p:struct.unpack_from('<I',data,p)[0];u64=lambda p:struct.unpack_from('<Q',data,p)[0]
    assert (u32(0),u32(4),u32(8))==(0x53504146,report['filesystem_version'],4096)
    total,count,table,root=u64(12),u32(20),u64(40),u32(56)
    assert 2<=total<=len(data)//4096 and 0<=root<count<=4096
    assert table<total and table*4096+count*256<=len(data)
    record=lambda number:table*4096+number*256
    directory=record(root);assert u32(directory)==2 and u64(directory+16)<=12*4096
    found=None
    for index in range((u64(directory+16)+4095)//4096):
        block=u64(directory+64+index*8);assert 0<block<total
        for position in range(block*4096,(block+1)*4096,32):
            inode,length=u32(position),data[position+4]
            if inode:assert inode<count and 1<=length<=24
            if inode and data[position+8:position+8+length]==name.encode():found=inode
    assert found is not None and found<count,(name,'missing from real disk')
    item=record(found);assert u32(item)==1;size=u64(item+16);assert size<=2146304
    inline=u32(item+176);assert inline in (0,1)
    if inline:
        assert size<=96;return data[item+64:item+64+size]
    output=bytearray()
    for index in range((size+4095)//4096):
        if index<12:block=u64(item+64+index*8)
        else:
            indirect=u64(item+160);assert 0<indirect<total;block=u64(indirect*4096+(index-12)*8)
        assert 0<block<total;output.extend(data[block*4096:(block+1)*4096])
    return bytes(output[:size])

def build(command,log):subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
class VM:
    def __init__(self,folder,command):
        self.folder=folder;self.received=bytearray();self.serial=self.monitor=None
        self.log=(folder/'qemu.log').open('w');self.process=subprocess.Popen(command,stdout=self.log,stderr=subprocess.STDOUT)
        self.serial=self.connect(folder/'serial.sock');self.monitor=self.connect(folder/'monitor.sock')
    def connect(self,path):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            channel=socket.socket(socket.AF_UNIX);channel.settimeout(.2)
            try:channel.connect(str(path));return channel
            except (FileNotFoundError,ConnectionRefusedError):channel.close();time.sleep(.02)
        raise AssertionError('QEMU socket unavailable')
    def receive(self):
        try:
            block=self.serial.recv(65536);assert block;self.received.extend(block)
        except socket.timeout:pass
    def wait(self,marker):
        deadline=time.monotonic()+180
        while marker not in self.received:
            if b'PANIC' in self.received or b'CPU EXCEPTION' in self.received:
                until=time.monotonic()+.3
                while time.monotonic()<until:self.receive()
                raise AssertionError(self.received[-4000:])
            assert self.process.poll() is None and time.monotonic()<deadline,(marker,self.received[-4000:])
            self.receive()
    def capture(self,count):
        marker=f'vi-durable: painted {count} '.encode();self.wait(marker)
        pattern=re.escape(marker)+rb'(\d+)\n';deadline=time.monotonic()+10
        while not re.search(pattern,self.received) and time.monotonic()<deadline:self.receive()
        match=re.search(pattern,self.received);assert match;size=int(match[1])
        address=int(re.search(rb'vi-durable: trace address (\d+)\n',self.received)[1])
        image=self.folder/'editing.ppm';stream=self.folder/'editing-stream.bin'
        self.monitor.sendall(f'stop\npmemsave {address:#x} {size} "{stream}"\nscreendump "{image}"\ncont\n'.encode())
        deadline=time.monotonic()+10
        while (not image.exists() or image.stat().st_size<1024*768*3 or not stream.exists() or stream.stat().st_size!=size) and time.monotonic()<deadline:time.sleep(.02)
        oracle=self.folder/'pixels.json'
        with (self.folder/'pixels.log').open('w') as log:
            build([a.oracle_python,snapshot/'scripts/check-terminal-view-pixels.py','--capture',image,'--stream',stream,
                   '--font',snapshot/'assets/fonts/desktop/DejaVuSansMono.ttf','--out',oracle],log)
        return json.loads(oracle.read_text())
    def close(self):
        (self.folder/'serial.log').write_bytes(self.received)
        if self.serial:self.serial.close()
        if self.monitor:self.monitor.close()
        self.process.terminate()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.log.close()

try:
    fnv=0xcbf29ce484222325
    for byte in app.read_bytes():fnv=((fnv^byte)*1099511628211)&((1<<64)-1)
    if fnv>=1<<63:fnv-=1<<64
    with (out/'common-build.log').open('w') as log:
        build(['nasm','-f','bin',snapshot/'boot/multiboot.asm','-o',out/'trampoline.bin'],log)
        build([compiler,'compile','--path',snapshot/'components/app-terminal-view.in','--entry','client-entry','--emit','sci','--base','0x60000000',
               '--target','native','--target-triple','x86_64-unknown-none','--out',out/'view.raw.sci'],log)
        build(['python3',snapshot/'scripts/pack-gui-sci.py',out/'view.raw.sci',out/'view.raw.component-metadata.json',out/'view.sci','--protected'],log)
    for stage in range(3):
        folder=out/f'boot-{stage}';folder.mkdir();before=sha(disk)
        source=(snapshot/'kernel/kernel-root.in').read_text()
        source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(snapshot/m[1])),source)
        source=(f'const VI-DURABLE-STAGE={stage}\nconst VI-DURABLE-UTC={int(a.utc)}\nconst TERMINAL-VI-ELF-SIZE={app.stat().st_size}\nconst TERMINAL-VI-FNV={fnv}\n'
                'import '+json.dumps(str(snapshot/'fixtures/terminal-session/vi-durable.in'))+'\n'+source)
        assert source.count('  shell(port)')==1;source=source.replace('  shell(port)','  vi-durable-check(port)\n  while true{hlt()}')
        (folder/'kernel.in').write_text(source)
        with (folder/'build.log').open('w') as log:
            build([compiler,'compile','--path',folder/'kernel.in','--entry','kernel-entry','--emit','boot','--trampoline',out/'trampoline.bin',
                   '--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',folder/'kernel.bin'],log)
            build(['python3',snapshot/'scripts/pack-sci-image.py',folder/'kernel.bin',folder/'combined.bin','270:'+str(out/'view.sci')],log)
        command=['qemu-system-x86_64','-cpu','max','-kernel',str(folder/'combined.bin'),'-m','512M','-display','none','-no-reboot',
                 '-serial',f'unix:{folder}/serial.sock,server=on,wait=on','-monitor',f'unix:{folder}/monitor.sock,server=on,wait=off',
                 '-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough','-device','nvme,drive=owned,serial=space-vi-durable',
                 '-rtc',f'base=2026-10-{25+stage}T00:00:00,clock=vm']
        if stage==0:command+=['-device',f'loader,file={app},addr=0x10000000,force-raw=on']
        entry=dict(stage=stage,qemu_command=command,kernel_sha256=sha(folder/'combined.bin'),elf_staged=stage==0,disk_before=before,original_application_entries=0)
        vm=None
        try:
            vm=VM(folder,command)
            vm.wait(f'vi-durable: original ELF from native filesystem {stage}\n'.encode())
            if stage<2:
                vm.wait(b'vi-durable: keyboard ready\n')
                typed='native24' if stage==0 else 'again42'
                edits=[('i',105)]+[(ch,ord(ch)) for ch in typed]
                if stage==0:edits += [('left',129),('backspace',8),('delete',134),('4',52),('2',50)]
                edits += [('home',132),('right',130),('end',133)]
                keys=edits+[('esc',27),('shift-semicolon',58),('w',119),('q',113),('ret',10)]
                for index,(key,code) in enumerate(keys):
                    vm.monitor.sendall(f'sendkey {key} 50\n'.encode());vm.wait(f'vi-durable: key {index} {code}\n'.encode());time.sleep(.08)
                    if index==len(edits)-1:entry['pixels']=vm.capture(index+1)
                vm.wait(f'vi-durable: saved exact and retired {stage}\n'.encode())
                entry.update(original_application_entries=1,keyboard_events=len(keys),expected_text='native42original\n' if stage==0 else 'again42native42original\n')
            else:vm.wait(b'vi-durable: cold readonly ELF and exact text verified PASS\n')
        finally:
            if vm:vm.close()
        executable=disk_file('busybox');text=disk_file('tui.txt')
        assert hashlib.sha256(executable).hexdigest()==pin['sha256'] and len(executable)==pin['size_bytes']
        expected=b'native42original\n' if stage==0 else b'again42native42original\n'
        assert text==expected,(stage,text)
        after=sha(disk)
        if stage==2:assert after==before,'read-only verification boot modified the disk'
        entry.update(status='passed',disk_after=after,persisted_elf_sha256=hashlib.sha256(executable).hexdigest(),persisted_text_sha256=hashlib.sha256(text).hexdigest(),persisted_text=text.decode('ascii'))
        report['boots'].append(entry);print('PASS cold vi boot',stage,'staged ELF' if stage==0 else 'filesystem-only ELF',flush=True)
    assert all((ROOT/name).read_bytes()==data for name,data in frozen.items()),'source changed during run'
    assert sha(compiler)==report['compiler_sha256'] and sha(app)==pin['sha256']
    report.update(status='passed',original_application_entries=2,keyboard_events=38,cold_boots=3,readonly_verification=True)
    print('PASS original interactive vi:3 cold NVMe boots,2 original processes,38 PS2 keys,exact saved text and filesystem-only ELF reopen',flush=True)
except Exception as error:
    report.update(status='failed',error=str(error));raise
finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
