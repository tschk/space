#!/usr/bin/env python3
"""Attempt original BusyBox vi through protected Space execution; blockers fail."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--scripted-input', action='store_true',
    help='Feed owned VFS key bytes; this is not a focused interactive terminal')
p.add_argument('--repeat', type=int, default=21)
p.add_argument('--batch-ex', action='store_true', help='Run real vi EX edit/save and a separate reopen process; no interactive terminal claim')
p.add_argument('--nvme', action='store_true', help='Repeat across two real NVMe boots and inspect persisted bytes')
p.add_argument('--utc', action='store_true', help='Use schema2 metadata and a real TimeSource lease (requires --nvme)')
p.add_argument('--root', choices=['standard','minimal'], default='standard')
a = p.parse_args()
if not 1 <= a.repeat <= 100: p.error('--repeat must be 1..100')
if a.batch_ex and a.scripted_input: p.error('choose either batch EX or scripted keys')
if a.nvme and not a.batch_ex: p.error('--nvme requires --batch-ex')
if a.utc and not a.nvme: p.error('--utc requires --nvme')
a.out = a.out.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = ROOT/'fixtures/applications/busybox-vi-1.36.1.json'
app = json.loads(manifest.read_text())['apps'][0]
assert sha(a.app) == app['sha256'] and a.app.stat().st_size == app['size_bytes']
snapshot = a.out/'source'
inventory = {}
for directory in ('components', 'kernel', 'protocol', 'services', 'fixtures'):
    for path in (ROOT/directory).rglob('*.in'):
        relative = path.relative_to(ROOT)
        data = path.read_bytes()
        target = snapshot/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        inventory[str(relative)] = hashlib.sha256(data).hexdigest()
        target.chmod(0o444)
fixture_source=ROOT/'fixtures/linux-poll/regular.asm'
for path in (fixture_source,ROOT/'boot/multiboot.asm',manifest,Path(__file__).resolve()):
    relative=path.relative_to(ROOT);data=path.read_bytes()
    target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data);target.chmod(0o444)
    inventory[str(relative)]=hashlib.sha256(data).hexdigest()
report = dict(application_status='test-error', execution_started=False,
    application_sha256=sha(a.app), compiler_sha256=sha(a.compiler),
    manifest_sha256=sha(manifest), source_sha256=inventory,
    scope='Original static Linux vi; serial output, no terminal provider or GUI integration',
    scripted_input=a.scripted_input, batch_ex=a.batch_ex, interactive_terminal=False,root=a.root)
try:
    private=[]
    for index,(name,signature,call,result) in enumerate([
        ('fs-resize-inline','path:Int,inode:Int,mount:Int,size:Int','0,0,0,0','Int'),
        ('vfs-regular-readiness','fd:Int,inode:Int,mount:Int,scratch:Int','0,0,0,0','Int'),
        ('desktop-fonts-apply','mono:Int,sans:Int','0,0','void')]):
        entry=a.out/f'private-{index}.in';binary=a.out/f'private-{index}.sci'
        entry.write_text('package space.fixture\ninterrupt fn '+name+'('+signature+')->'+result+'{}\n'+
            'fn private-entry(info:Int)->Int{store64(0x13000000,1347374156);'+name+'('+call+');return 0;}\n')
        with (a.out/f'private-{index}-compile.log').open('w') as log:
            subprocess.run([str(a.compiler.resolve()),'compile','--path',str(entry),'--entry','private-entry',
                '--emit','sci','--base','0x7a000000','--target','native','--target-triple','x86_64-unknown-none',
                '--out',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        private.append(dict(name=name,path=str(binary),size=binary.stat().st_size,sha256=sha(binary)))
    report['private_sci_fixtures']=private
    fixture=a.out/'poll.elf'
    if a.scripted_input or a.batch_ex:
        subprocess.run(['nasm','-f','elf64',str(snapshot/fixture_source.relative_to(ROOT)),'-o',str(a.out/'poll.o')],check=True)
        subprocess.run(['ld','-static','-z','noexecstack','-o',str(fixture),str(a.out/'poll.o')],check=True)
        class PollFD(ctypes.Structure):
            _fields_=[('fd',ctypes.c_int),('events',ctypes.c_short),('revents',ctypes.c_short)]
        document=a.out/'poll-reference.txt';document.write_bytes(b'original\n')
        with document.open('r+b') as file:
            rows=(PollFD*3)(PollFD(file.fileno(),0x145,0x5555),PollFD(-1,1,0x5555),PollFD(9999,0,0x5555))
            result=ctypes.CDLL(None,use_errno=True).poll(rows,3,-1)
            assert result==2 and [row.revents for row in rows]==[0x145,0,32]
            assert os.lseek(file.fileno(),0,1)==0
            os.lseek(file.fileno(),0,2)
            assert ctypes.CDLL(None,use_errno=True).poll(rows,1,0)==1 and rows[0].revents==0x145
        report['host_regular_file_poll_oracle']='passed (including EOF and unchanged offset)'
        report['own_poll_fixture_sha256']=sha(fixture)
    fnv = 0xcbf29ce484222325
    for byte in a.app.read_bytes():
        fnv = ((fnv ^ byte)*1099511628211) & ((1 << 64)-1)
    signed_fnv = fnv if fnv < 1 << 63 else fnv-(1 << 64)
    root_name='kernel-root.in' if a.root=='standard' else 'kernel-root-minimal.in'
    source = (snapshot/'kernel'/root_name).read_text()
    source = re.sub(r'import "\.\./([^"]+)"',
        lambda m: 'import '+json.dumps(str(snapshot/m[1])), source)
    source = 'import '+json.dumps(str(snapshot/'components/linux-process.in'))+'\n'+source
    assert source.count('  shell(port)') == 1
    source = source.replace('  shell(port)', '  tui-probe(port)\n  shell(port)')
    source += '''
fn tui-free()->Int{let p=free-list;let n=0;while p!=0 && n<131072{n+=1;p=load64(p);}return n;}
fn tui-fds()->Int{let i=3;let count=0;while i<VFS-MAX-FDS{if vfs-fd-valid(i)!=0{count+=1;}i+=1;}return count;}
fn tui-probe(port:Int)->void{
 let authority=cap-mint(root-realm,cap-memory()|cap-serial()|cap-storage());
 if authority<0{panic("tui authority");}
 let prior-end=heap-end;heap-end=0x10000000;
 PRIVATE_IMPORTS
 PERSISTENCE_SETUP
 if fs-write-file("/tui.txt","original\\n",9)!=0{panic("tui seed");}
 INPUT_SETUP
 let original-fds=tui-fds();
 POLL_FIXTURE
 linux-process-trace=1;
 let cycle=0;let heap=0;let free=0;let domains=0;
 let caller=current-cap;let caps=cap-count;let owned=domain-user-owned;
 let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 while cycle<CYCLES{
  INPUT_RESET
  let hash=-3750763034362895579;let byte=0;
  while byte<APP_SIZE{hash=(hash^load8(0x10000000+byte))*1099511628211;byte+=1;}
  if hash!=APP_FNV{panic("tui original payload byte oracle");}
  serial-write-cstr(port,"tui: begin ");serial-write-dec-wide(port,cycle);serial-nl(port);
  let result=linux-process-run-counted-input(0x10000000,APP_SIZE,"/busybox","vi","/tui.txt",authority,INPUT_FD,3);
  serial-write-cstr(port,"tui: end ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,result);serial-put(port,32);serial-write-dec-wide(port,linux-process-syscalls);serial-nl(port);
  BATCH_REOPEN
  if tui-fds()!=original-fds{panic("vi descriptor leak");}
  if domain-current!=0 || domain-user-syscall-hook!=0 || user-budget-active!=0 || linux-process-active!=0 || linux-process-pages!=0 || cap-count!=caps || current-cap!=caller || domain-user-owned!=owned || rdmsr(0xC0000100)!=fs || rdmsr(0xC0000101)!=gs{panic("tui cleanup");}
  if cycle==0{heap=heap-next;free=tui-free();domains=domain-count;}
  else{if heap-next!=heap || tui-free()!=free || domain-count!=domains{panic("tui repeated resource lifetime");}}
  cycle+=1;
 }
 let bytes=alloc(32);let count=fs-read-file("/tui.txt",bytes,32);
 serial-write-cstr(port,"tui: file ");serial-write-dec-wide(port,count);serial-put(port,32);
 let i=0;while i<count && i<32{serial-put(port,load8(bytes+i));i+=1;}serial-nl(port);
 serial-write-cstr(port,"tui: probe cleanup PASS");serial-nl(port);
 heap-end=prior-end;outb(0xf4,0x10);while true{hlt();}return;
}
'''.replace('APP_SIZE', str(app['size_bytes'])).replace('APP_FNV', str(signed_fnv)).replace('CYCLES',str(a.repeat+1))
    keys = b'gg0iSpaceTUI42\x1b:wq\r'
    setup = 'let input=-1;'
    reset = ''
    fixture_calls=''
    if a.batch_ex:
        document=a.out/'batch-reference.txt';document.write_bytes(b'original\n')
        commands=['-c%s/original/SpaceTUI42original/\nwq','-c%s/SpaceTUI42original/Reopened42/\nwq']
        for command in commands:
            reference=subprocess.run(['/vi',command,str(document)],executable=str(a.app.resolve()),
                input=b'',capture_output=True,timeout=10,env={'LC_ALL':'C','HOME':'/'})
            assert reference.returncode==0, reference.stderr
        assert document.read_bytes()==b'Reopened42\n'
        report['host_batch_edit_reopen_oracle']='passed'
        reset='if fs-write-file("/tui.txt","original\\n",9)!=0{panic("vi reset");}'
        source=source.replace('"/busybox","vi","/tui.txt"',json.dumps('/vi')+','+json.dumps(commands[0])+',"/tui.txt"')
        reopen='''if result!=0{panic("vi EX edit failed");}
 let verify=linux-process-file-buffer;let size=fs-read-file("/tui.txt",verify,32);
 if size!=19{panic("vi first saved size");}
 let index=0;while index<19{if load8(verify+index)!=load8("SpaceTUI42original\\n"+index){panic("vi first saved bytes");}index+=1;}
 let reopened=linux-process-run-counted-input(0x10000000,APP_SIZE,"/vi",REOPEN_COMMAND,"/tui.txt",authority,-1,3);
 serial-write-cstr(port,"tui: reopen ");serial-write-dec-wide(port,cycle);serial-put(port,32);serial-write-dec-wide(port,reopened);serial-nl(port);
 if reopened!=0{panic("vi separate reopen failed");}
 size=fs-read-file("/tui.txt",verify,32);if size!=11{panic("vi reopened size");}
 index=0;while index<11{if load8(verify+index)!=load8("Reopened42\\n"+index){panic("vi reopened bytes");}index+=1;}
'''.replace('APP_SIZE',str(app['size_bytes'])).replace('REOPEN_COMMAND',json.dumps(commands[1]))
        source=source.replace('BATCH_REOPEN',reopen)
    else:
        source=source.replace('BATCH_REOPEN','')
    if a.scripted_input:
        setup = f'let keys=alloc({len(keys)});'+''.join(
            f'store8(keys+{i},{value});' for i, value in enumerate(keys))
        setup += f'if fs-write-file("/vi-keys",keys,{len(keys)})!=0{{panic("vi keys seed");}}'
        setup += 'let input=vfs-open-borrowed-path("/vi-keys",VFS-O-RDONLY);if input<3{panic("vi keys open");}'
        reset = 'if vfs-lseek(input,0,0)!=0 || fs-write-file("/tui.txt","original\\n",9)!=0{panic("vi input reset");}'
    if a.scripted_input or a.batch_ex:
        fixture_calls='''let poll-cycle=0;let poll-heap=0;let poll-free=0;let poll-domains=0;
 while poll-cycle<FIXTURE_CYCLES{
  let result=linux-process-run-counted-input(0x12000000,FIXTURE_SIZE,"/poll-fixture","/tui.txt",0,authority,-1,2);
  if result!=42{serial-write-cstr(port,"poll-fixture: unexpected ");serial-write-dec-wide(port,result);serial-nl(port);panic("poll ABI fixture");}
  if tui-fds()!=original-fds{panic("poll fixture descriptor leak");}
  if poll-cycle==0{poll-heap=heap-next;poll-free=tui-free();poll-domains=domain-count;}
  else{if heap-next!=poll-heap || tui-free()!=poll-free || domain-count!=poll-domains{panic("poll fixture resource lifetime");}}
  poll-cycle+=1;
 }
 serial-write-cstr(port,"poll-fixture: protected entries FIXTURE_CYCLES PASS");serial-nl(port);
'''.replace('FIXTURE_CYCLES',str(a.repeat+1)).replace('FIXTURE_SIZE',str(fixture.stat().st_size))
    source = source.replace('INPUT_SETUP', setup).replace('INPUT_RESET', reset).replace('INPUT_FD', 'input').replace('POLL_FIXTURE',fixture_calls)
    persistence=''
    if a.nvme:
        format_call='sparkfs-format()'
        bind=''
        if a.utc:
            persistence+='let clock=cap-mint(root-realm,cap-timer());if clock<0{panic("vi clock authority");}'
            format_call='fs-metadata-format-utc(8192,256,authority,clock)'
            bind='if fs-metadata-bind-clock(authority,clock)!=0{panic("vi clock bind");}'
        persistence+='''if sf-disk-ready==0{if FORMAT!=0{panic("vi explicit format");}}
 else{BIND
  let verify=alloc(32);let count=fs-read-file("/tui.txt",verify,32);
  if count!=11{panic("vi reboot saved size");}
  let expected="Reopened42\\n";let i=0;while i<11{if load8(verify+i)!=load8(expected+i){panic("vi reboot saved bytes");}i+=1;}
  serial-write-cstr(port,"tui: persisted bytes verified before reset PASS");serial-nl(port);
 }
'''.replace('FORMAT',format_call).replace('BIND',bind)
    source=source.replace('PERSISTENCE_SETUP',persistence)
    private_checks='let private-table=alloc(48);let prior-boot=load64(0x40d0);'
    private_checks+='store64(private-table,BOOT-IMAGE-TABLE-MAGIC);store64(private-table+8,1);store64(private-table+16,254);store64(private-table+40,0);'
    for index,item in enumerate(private):
        address=0x2d0000+index*0x10000
        private_checks+='''{
 if dyn-kernel-exportable(NAME)!=0 || dyn-resolve-idx(NAME)!=-1{panic("private provider exported");}
 store64(0x13000000,0);store64(private-table+24,ADDRESS);store64(private-table+32,SIZE);store64(0x40d0,private-table);
 let heap=heap-next;let free=free-list;let caps=cap-count;let domains=domain-count;let live=runtime-instance-live;
 if sci-load-runtime-component(port,ADDRESS,"private-file-control",1,1,0)!=-1{panic("private SCI import accepted");}
 if load64(0x13000000)!=0 || heap-next!=heap || free-list!=free || cap-count!=caps || domain-count!=domains || runtime-instance-live!=live{panic("private SCI refusal mutated resources or entered");}
 store64(0x40d0,prior-boot);
}
'''.replace('NAME',json.dumps(item['name'])).replace('ADDRESS',str(address)).replace('SIZE',str(item['size']))
    private_checks+='serial-write-cstr(port,"tui: three actual private SCI imports refused before entry PASS");serial-nl(port);'
    source=source.replace('PRIVATE_IMPORTS',private_checks)
    entry = a.out/'probe.in'; entry.write_text(source)
    trampoline = a.out/'trampoline.bin'
    subprocess.run(['nasm', '-f', 'bin', str(snapshot/'boot/multiboot.asm'), '-o', str(trampoline)], check=True)
    kernel = a.out/'kernel.bin'
    command = [str(a.compiler.resolve()), 'compile', '--path', str(entry), '--entry', 'kernel-entry',
        '--emit', 'boot', '--trampoline', str(trampoline), '--target', 'native',
        '--target-triple', 'x86_64-unknown-none', '--linkage', 'static-lib', '--out', str(kernel)]
    with (a.out/'compile.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    assert kernel.stat().st_size+0x100000<=0x2d0000, 'kernel overlaps private SCI staging slots'
    assert all(item['size']<=0x10000 for item in private)
    boots=2 if a.nvme else 1
    if a.nvme:
        disk=a.out/'nvme.raw'
        with disk.open('wb') as output: output.truncate(64*1024*1024)
    report['boots']=[];serial=''
    for boot in range(boots):
        serial_path=a.out/('serial.log' if boots==1 else f'boot-{boot+1}-serial.log')
        command = ['qemu-system-x86_64', '-cpu', 'max', '-kernel', str(kernel), '-m', '512M', '-display', 'none',
            '-no-reboot', '-serial', 'file:'+str(serial_path),
            '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
            '-device', 'loader,file='+str(a.app.resolve())+',addr=0x10000000,force-raw=on']
        if a.scripted_input or a.batch_ex:
            command+=['-device','loader,file='+str(fixture)+',addr=0x12000000,force-raw=on']
        for index,item in enumerate(private):
            command+=['-device','loader,file='+item['path']+',addr='+str(0x2d0000+index*0x10000)+',force-raw=on']
        if a.nvme:
            command+=['-drive',f'file={disk},format=raw,if=none,id=owned,cache=writethrough',
                      '-device','nvme,drive=owned,serial=space-vi','-rtc',f'base=2026-10-{24+boot}T00:00:00,clock=vm']
        with (a.out/f'qemu-{boot+1}.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        output=serial_path.read_text(errors='replace');serial+=output
        assert result.returncode==33 and 'tui: probe cleanup PASS\n' in output, output[-3000:]
        assert 'tui: three actual private SCI imports refused before entry PASS\n' in output
        record={'qemu_command':command,'serial_sha256':sha(serial_path)}
        if a.nvme:
            if boot: assert 'tui: persisted bytes verified before reset PASS\n' in output
            raw=disk.read_bytes();u32=lambda at:struct.unpack_from('<I',raw,at)[0];u64=lambda at:struct.unpack_from('<Q',raw,at)[0]
            assert (u32(0),u32(4),u32(8))==(0x53504146,2 if a.utc else 1,4096)
            table=u64(40)*4096;root=table+u32(56)*256;block=u64(root+64)*4096
            found=[]
            for offset in range(0,u64(root+16),32):
                inode=u32(block+offset);length=raw[block+offset+4]
                if inode and raw[block+offset+8:block+offset+8+length]==b'tui.txt':found.append(inode)
            assert len(found)==1
            inode=table+found[0]*256
            assert u32(inode)==1 and u32(inode+176)==1 and u64(inode+16)==11
            assert raw[inode+64:inode+75]==b'Reopened42\n'
            assert raw[inode+75:inode+160]==bytes(85), 'retired inline bytes leaked after shrink'
            if a.utc:
                import datetime
                base=int(datetime.datetime(2026,10,24+boot,tzinfo=datetime.timezone.utc).timestamp())
                assert base<=u64(inode+40)<base+86400, 'mtime did not use the bound UTC clock'
            record.update(disk_sha256=sha(disk),raw_inode_sha256=hashlib.sha256(raw[inode:inode+256]).hexdigest(),
                raw_saved_bytes='Reopened42\n',raw_retired_tail_zero=True)
        report['boots'].append(record)
    entries = re.findall(r'tui: end (\d+) (-?\d+) (\d+)', serial)
    report['execution_started'] = any(int(calls)>0 for _, _, calls in entries)
    assert len(entries) == (a.repeat+1)*boots, serial[-3000:]
    assert sha(a.compiler) == report['compiler_sha256'] and sha(a.app) == report['application_sha256']
    assert all(sha(ROOT/name)==digest for name, digest in inventory.items())
    report.update(application_status='blocked', probe_status='passed', entries=entries,
        kernel_sha256=sha(kernel), qemu_command=command, source_integrity='passed',
        required_scenario='type/edit/save/reopen through focused native terminal',
        scenario_passed=False)
    if a.scripted_input:
        assert f'poll-fixture: protected entries {a.repeat+1} PASS\n' in serial
        assert all(int(status)==0 and int(calls)>0 for _, status, calls in entries), entries
        assert 'tui: file 19 SpaceTUI42original\n\n' in serial, serial[-1000:]
        report.update(application_status='passed-scripted', scenario_passed=True,
            original_vi_activations=len(entries), own_poll_fixture_activations=a.repeat+1,
            required_scenario='scripted original vi edit/save via owned VFS stdin; interactive terminal remains OPEN')
    if a.batch_ex:
        assert f'poll-fixture: protected entries {a.repeat+1} PASS\n' in serial
        assert all(int(status)==0 and int(calls)>0 for _, status, calls in entries), entries
        assert 'tui: file 11 Reopened42\n\n' in serial
        reopened=re.findall(r'tui: reopen (\d+) 0',serial)
        assert len(reopened)==len(entries)
        report.update(application_status='passed-batch-ex',scenario_passed=True,
            original_vi_activations=len(entries)*2, own_poll_fixture_activations=(a.repeat+1)*boots,
            actual_nvme_boots=boots if a.nvme else 0, filesystem_version=2 if a.utc else 1,
            private_sci_preentry_refusals=3*boots,
            required_scenario='original vi EX edit/save plus separate-process reopen/edit/save; interactive terminal remains OPEN')
except Exception as error:
    report['application_status']='scenario-mismatch' if report.get('probe_status')=='passed' else 'test-error'
    report['error'] = str(error)
finally:
    (a.out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(report['application_status'].upper()+': real vi attempt; '+str(a.out/'report.json'))
raise SystemExit(0 if report['application_status'] in ('passed-scripted','passed-batch-ex') else 1)
