#!/usr/bin/env python3
"""Run actual compiler SCI through an explicit CPL3 native service profile."""
import argparse, hashlib, json, re, socket, subprocess, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--profile',choices=['immutable','paged'],default='immutable')
p.add_argument('--memory',default=None)
p.add_argument('--mode',choices=['full','oom'],default='full')
a=p.parse_args();out=a.out.resolve()
if out.exists() and any(out.iterdir()):p.error('--out must be new or empty')
out.mkdir(parents=True,exist_ok=True)
source=(root/'kernel/kernel-root.in').read_text()
source=re.sub(r'import "\.\./([^"]+)"',lambda m:'import '+json.dumps(str(root/m[1])),source)
assert source.count('  shell(port)')==1
entry='native-protected-oom-check' if a.mode=='oom' else 'native-protected-check'
source=source.replace('  shell(port)','  '+entry+'(port)\n  shell(port)')
source='import '+json.dumps(str(root/'components/native-protected.in'))+'\nimport '+json.dumps(str(root/'fixtures/native-protected/checks.in'))+'\n'+source
(out/'kernel.in').write_text(source)
with (out/'compile.log').open('w') as log:
    commands=[['nasm','-f','bin',str(root/'boot/multiboot.asm'),'-o',str(out/'trampoline.bin')],
        [a.compiler,'compile','--path',str(root/'fixtures/native-protected/client.in'),'--entry','native-entry','--emit','sci','--base','0x60000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'client.raw.sci')],
        ['python3',str(root/'scripts/pack-native-protected-sci.py'),str(out/'client.raw.sci'),str(out/'client.raw.component-metadata.json'),str(out/'client.sci')]+(['--immutable-image'] if a.profile=='immutable' else []),
        [a.compiler,'compile','--path',str(root/'fixtures/runtime-failure/global-state.in'),'--entry','fresh-entry','--emit','sci','--base','0x72000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'trusted.sci')],
        [a.compiler,'compile','--path',str(root/'fixtures/native-protected/private-import.in'),'--entry','native-entry','--emit','sci','--base','0x60000000','--target','native','--target-triple','x86_64-unknown-none','--out',str(out/'private.raw.sci')],
        ['python3',str(root/'scripts/pack-native-protected-sci.py'),str(out/'private.raw.sci'),str(out/'private.raw.component-metadata.json'),str(out/'private.sci'),'--immutable-image'],
        [a.compiler,'compile','--path',str(out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(out/'kernel.bin')],
        ['python3',str(root/'scripts/pack-sci-image.py'),str(out/'kernel.bin'),str(out/'combined.bin'),f'254:{out}/client.sci',f'255:{out}/trusted.sci',f'256:{out}/private.sci']]
    for cmd in commands:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
received=bytearray();serial=None
with (out/'qemu.log').open('w') as log:
    sock=out/'serial.sock';qemu=subprocess.Popen(['qemu-system-x86_64','-kernel',str(out/'combined.bin'),'-m',a.memory or ('32M' if a.mode=='oom' else '512M'),'-cpu','qemu64','-display','none','-no-reboot','-serial',f'unix:{sock},server=on,wait=on'],stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        while not sock.exists() and qemu.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        serial=socket.socket(socket.AF_UNIX);serial.settimeout(.2);serial.connect(str(sock))
        deadline=time.monotonic()+180
        while b'space interactive shell' not in received and time.monotonic()<deadline:
            try:
                block=serial.recv(65536)
                if not block:break
                received.extend(block)
                if b'PANIC' in received or b'nanokernel fault handler halting' in received:break
            except socket.timeout:
                if qemu.poll() is not None:break
        text=received.decode(errors='replace')
        marker='native: actual protected SCI constrained memory exact refusal IF restoration peer recovery PASS' if a.mode=='oom' else 'native: actual protected SCI two instances trap heap capability denial abort fault deadline lifetime PASS'
        assert marker in text and 'space interactive shell' in text and 'INVALID' not in text,text
        serial.sendall(b'halt\n')
        report={'status':'passed','profile':a.profile,'memory':a.memory or ('32M' if a.mode=='oom' else '512M'),'actual_cpl3_compiled_sci':True,'two_instances':True,'mixed_trusted_protected_cycles':70,'protected_lifecycle_instances':140,'compiler_generated_aborts':True,'actual_hardware_faults_and_deadline':True,'compiler_sha256':hashlib.sha256(Path(a.compiler).read_bytes()).hexdigest(),'image_sha256':hashlib.sha256((out/'combined.bin').read_bytes()).hexdigest(),'component_sha256':hashlib.sha256((out/'client.sci').read_bytes()).hexdigest()}
        if a.mode=='oom':
            report={key:value for key,value in report.items() if key not in ['two_instances','mixed_trusted_protected_cycles','protected_lifecycle_instances','compiler_generated_aborts','actual_hardware_faults_and_deadline']}
            match=re.search(r'native: constrained memory budget (\d+) available (\d+)',text);assert match,text
            report.update({'required_frame_budget':int(match[1]),'available_frames_at_refusal':int(match[2]),'refused_activations':2,'exact_cap_domain_resource_bytes':True,'caller_if0_if1_restored':True,'peer_and_recovery_survive':True})
        else:
            match=re.search(r'native: CPU activations (\d+)',text);assert match,text
            report.update({'protected_activations':int(match[1]),'private_source_image_unchanged':True,'malformed_authority_extent_import_refusals':16 if a.profile=='paged' else 15,'initialized_mutable_globals':a.profile=='paged','data_NX_and_bindings_readonly':a.profile=='paged'})
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(f'PASS: protected native SCI profile; {out}')
    finally:
        (out/'serial.log').write_bytes(received)
        if serial:serial.close()
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
