#!/usr/bin/env python3
"""Execute pinned unmodified static Linux applications in private Space processes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--in', dest='compiler', required=True)
parser.add_argument('--app', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--application', choices=['jq','lua','busybox','sqlite','quickjs','sed'], default='jq')
parser.add_argument('--manifest', type=Path, help='explicit pinned application profile manifest (recorded separately)')
parser.add_argument('--case-config', type=Path, help='explicit bounded argument-vector application corpus JSON')
parser.add_argument('--filter','--expression', dest='filter')
parser.add_argument('--expected')
parser.add_argument('--expected-exit', type=int, default=0)
parser.add_argument('--trace', action='store_true')
parser.add_argument('--expect-deadline-wait',action='store_true',help='Require actual stopped-CPU native IRQ waits, not a timer busy loop')
parser.add_argument('--no-hpet',action='store_true',help='Actual PC boot without the HPET monotonic source')
parser.add_argument('--timer-grant',action='store_true',help='Explicitly grant native clock/counter access to tested processes')
parser.add_argument('--suite', action='store_true', help='also exercise application arithmetic, text, memory and errors')
parser.add_argument('--root', choices=['standard','minimal'], default='standard', help='kernel service root under test')
parser.add_argument('--input-suite', action='store_true', help='also exercise real VFS stdin and file I/O')
parser.add_argument('--budget-ticks', type=int, default=100, help='actual guest PIT interrupt budget per activation')
parser.add_argument('--repeat', type=int, default=21, help='repeated original app launches after warm-up')
parser.add_argument('--wall-timeout', type=int, help='external QEMU wall-clock seconds (1..3600); does not alter actual guest IRQ budget')
args = parser.parse_args()
args.out = args.out.resolve(); args.app = args.app.resolve()
if not 1 <= args.budget_ticks <= 10000: parser.error('--budget-ticks must be 1..10000')
if not 1 <= args.repeat <= 100: parser.error('--repeat must be 1..100')
if args.wall_timeout is not None and not 1 <= args.wall_timeout <= 3600: parser.error('--wall-timeout must be 1..3600')
if args.out.exists() and any(args.out.iterdir()):
    parser.error('--out must be new or empty')
version={'jq':'jq-1.8.1','lua':'lua-5.4.7','busybox':'busybox-1.36.1','sqlite':'sqlite-3.46.1','quickjs':'quickjs-2024-01-13','sed':'sed-4.9'}[args.application]
config_bytes=args.case_config.read_bytes() if args.case_config else None
manifest_bytes=args.manifest.read_bytes() if args.manifest else None
# Compile a recorded source snapshot: simultaneous repository work must not
# change dependency bytes halfway through a build or its provenance report.
live_root=ROOT
args.out.mkdir(parents=True,exist_ok=True)
source_files=[]
for directory in ['components','kernel','protocol','services','fixtures']:
    source_files += list((live_root/directory).rglob('*.in'))
source_files += list((live_root/'fixtures/applications').glob('*.json'))
source_files += list((live_root/'fixtures/linux-process').glob('*.asm'))
source_files += list((live_root/'fixtures/linux-vm').rglob('*.asm'))
source_files += [live_root/'fixtures/linux-process/int-width-host.py']
source_files += [live_root/'boot/multiboot.asm',Path(__file__).resolve(),live_root/'scripts/check-linux-real-app.py']
for attempt in range(3):
    captured={path.relative_to(live_root):path.read_bytes() for path in source_files}
    if all(path.read_bytes()==captured[path.relative_to(live_root)] for path in source_files): break
else:
    raise RuntimeError('repository dependencies changed while taking the test snapshot')
ROOT=args.out/'source'
receipt={}
for relative, data in captured.items():
    target=ROOT/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o444)
    receipt[str(relative)]=hashlib.sha256(data).hexdigest()
(ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if manifest_bytes is not None:
    (args.out/'application-manifest.json').write_bytes(manifest_bytes)
else:
    manifest_bytes=(ROOT/f'fixtures/applications/{version}.json').read_bytes()
manifest = json.loads(manifest_bytes)
width_host=subprocess.run([sys.executable,str(ROOT/'fixtures/linux-process/int-width-host.py')],capture_output=True,text=True,check=True,timeout=15)
(args.out/'int-width-host.json').write_text(width_host.stdout)
guest_name='/'+args.application
expression_flag='-nc' if args.application=='jq' else '-e'
infinite_query='recurse(.;true) | empty' if args.application=='jq' else 'while true do end'
args.filter=args.filter or ('[range(10)] | add' if args.application=='jq' else 'print(6*7)')
if args.expected is None: args.expected='45\n' if args.application=='jq' else '42\n'
app = next(row for row in manifest['apps'] if row['personality']=='linux')
assert hashlib.sha256(args.app.read_bytes()).hexdigest()==app['sha256'], 'application checksum mismatch'
args.out.mkdir(parents=True, exist_ok=True)
# Reference execution is explicit and separate from the Space result.
cases = [{'filter': args.filter, 'stdout': args.expected, 'exit': args.expected_exit}]
if args.suite and args.application=='jq':
    for query in ['[range(2000)] | map(. * .) | add',
                  '{answer:([range(100)]|add), sorted:([3,1,2]|sort)}',
                  '["a","b","c"] | map(ascii_upcase) | join("-")',
                  '"abc123def" | capture("(?<digits>[0-9]+)").digits',
                  '[recurse(.+1; .<8)] | add', '[955,128578] | implode',
                  'error("space-test")', '"deliberate" | halt_error(7)']:
        cases.append({'filter': query})
if args.input_suite and args.application=='jq':
    cases += [
        {'filter':'.items | add','input':'{"items":[1,2,3],"message":"from Space VFS"}\n'},
        {'filter':'.message','input':'{"items":[1,2,3],"message":"from Space VFS"}\n'},
        {'filter':'.x * 2','input':'{"x":3}\n{"x":7}\n'},
        {'filter':'.items | add','input':json.dumps({'items':list(range(2000))})+'\n'},
        {'filter':'.items | add','file':'{"items":[1,2,3],"message":"from Space VFS"}\n'},
        {'filter':'.items | length','file':json.dumps({'items':list(range(2000))})+'\n'},
    ]
if args.suite and args.application=='lua':
    cases += [{'filter': query} for query in [
        'print(math.sqrt(81),math.floor(3.9),math.abs(-7))',
        'local t={3,1,2};table.sort(t);print(table.concat(t,","))',
        'print(string.upper("Space")..":"..string.format("%04d",7))',
        'print(utf8.char(955,128578))',
        'local t={};for i=1,5000 do t[i]=i end;collectgarbage("collect");print(#t,t[5000])',
        'local t={};for i=1,100000 do t[i]=i end;print(#t,t[100000]);t=nil;collectgarbage("collect")',
        'local co=coroutine.create(function()coroutine.yield(7);return 9 end);local a,b=coroutine.resume(co);local c,d=coroutine.resume(co);print(a,b,c,d)',
        'local ok,e=pcall(function()error("caught")end);print(ok,e:match("caught")~=nil)',
        'print(os.getenv("LC_ALL"))', 'print(os.getenv("HOME"))', 'error("space-test")', 'os.exit(7)',
    ]]
if args.input_suite and args.application=='lua':
    cases += [
        {'filter':'local s=io.read("*a");print(#s)','input':'{"items":[1,2,3],"message":"from Space VFS"}\n'},
        {'filter':'local n=0;for line in io.lines() do n=n+assert(tonumber(line)) end;print(n)','input':'1\n2\n3\n'},
        {'filter':'local s=io.read("*a");print(#s)','input':'x'*10902},
        {'filter':'local f=assert(io.open(@FILE@,"r"));local s=f:read("*a");f:close();print(#s)','file':'{"items":[1,2,3],"message":"from Space VFS"}\n'},
        {'filter':'local f=assert(io.open(@FILE@,"r"));local s=f:read("*a");f:close();print(#s)','file':'x'*10902},
        {'filter':'local f=assert(io.open(@FILE@,"r+"));assert(f:write("FILE"));assert(f:seek("set",0)==0);print(f:read(4));f:close()','file':'original file content\n'},
        {'filter':'local f=assert(io.open(@FILE@,"r+"));assert(f:seek("set",4090)==4090);assert(f:write("CROSS-BLOCK"));assert(f:seek("set",4090)==4090);print(f:read(11));f:close()','file':'x'*10902},
        {'filter':'local f=assert(io.open(@FILE@,"w"));assert(f:write("created in Space"));f:close();local g=assert(io.open(@FILE@,"r"));print(g:read("*a"));g:close()','file':'','create':True},
        {'filter':'local f=assert(io.open(@FILE@,"w"));assert(f:write(string.rep("z",9000)));f:close();local g=assert(io.open(@FILE@,"r"));print(#g:read("*a"));g:close()','file':'this old content must be truncated'},
        {'filter':'local f=assert(io.open(@FILE@,"a"));assert(f:seek("set",0)==0);assert(f:write("B"));f:close();local g=assert(io.open(@FILE@,"r"));print(g:read("*a"));g:close()','file':'A','reset_each':True},
        {'filter':'local f=assert(io.open(@FILE@,"r+"));assert(f:seek("set",4096)==4096);assert(f:write("Z"));f:close();local g=assert(io.open(@FILE@,"r"));assert(g:seek("set",4095)==4095);local s=g:read(2);print(string.byte(s,1,2));g:close()','file':'A','reset_each':True},
    ]
if args.application in ['busybox','sqlite'] or config_bytes is not None:
    if config_bytes is None:
        config_bytes=(ROOT/f'fixtures/applications/{version}-cases.json').read_bytes()
    (args.out/'case-config.json').write_bytes(config_bytes)
    config=json.loads(config_bytes)
    cases=[]
    bound_file_slots=set()
    for item in config['cases']:
        if not args.input_suite and ('stdin' in item or 'file' in item): continue
        case={'filter':item['name'],'argv':item['argv'],
              'stdout':item['expected_stdout'],'exit':item.get('expected_exit',0),
              'expected_stderr':item.get('expected_stderr',''),
              **{key:item[key] for key in ['file','create','repeat','reset_each','file_slot'] if key in item}}
        if 'file_slot' in case:
            assert type(case['file_slot']) is int and 0<=case['file_slot']<=99
        if 'file' in case:
            slot=case.get('file_slot',len(cases))
            if slot in bound_file_slots:
                assert case.get('create'), 'shared-file follow-up must preserve the existing file'
            bound_file_slots.add(slot)
        if 'stdin' in item: case['input']=item['stdin']
        assert 1<=len(case['argv'])<=16 and all(isinstance(word,str) and len(word.encode())<=511 for word in case['argv']), 'bounded launch vector requires 1..16 strings of at most511 bytes'
        cases.append(case)
    if not args.suite:
        cases=cases[:1]+([case for case in cases[1:] if 'input' in case or 'file' in case] if args.input_suite else [])
    assert cases and 'input' not in cases[0] and 'file' not in cases[0], 'first case must be a finite command independent of stdin/files'

def application_argv(case, file_path=None):
    if 'argv' in case:
        return [word.replace('@FILE@',file_path) if file_path else word for word in case['argv']]
    if args.application=='jq':
        return [guest_name,case['filter'],file_path] if file_path else [guest_name,'-c' if 'input' in case else '-nc',case['filter']]
    expression=case['filter'].replace('@FILE@',json.dumps(file_path)) if file_path else case['filter']
    return [guest_name,'-e',expression]

def guest_file_path(index):
    index=cases[index].get('file_slot',index)
    # SQLite appends '-journal'; leave room within native directory name24.
    if args.application=='sqlite': return f'/sq-{index}.db'
    return f'/linux-{args.application[:3]}-input-{index}.json'

for index, case in enumerate(cases):
    reference_path=None
    if 'file' in case:
        reference_path=args.out/Path(guest_file_path(index)).name
        if not case.get('create'): reference_path.write_text(case['file'])
    command=application_argv(case,str(reference_path) if reference_path else None)
    case['reference_command']=command
    reference = subprocess.run(command, executable=str(args.app), input=case.get('input'), env={'LC_ALL':'C','HOME':'/'}, cwd='/', umask=0o22, capture_output=True, text=True, timeout=15)
    if 'stdout' in case:
        declared_stdout=case['stdout'].replace('@FILE@',str(reference_path)) if reference_path else case['stdout']
        assert reference.returncode == case['exit'] and reference.stdout == declared_stdout
        if 'expected_stderr' in case: assert reference.stderr==case['expected_stderr']
    case.update(stdout=reference.stdout, stderr=reference.stderr, exit=reference.returncode)
    if reference_path and 'argv' in case:
        case['space_expected_stdout']=reference.stdout.replace(str(reference_path),guest_file_path(index))
infinite_argv=config.get('infinite_argv',['/ash','-c','while :; do :; done']) if args.application in ['busybox','sqlite'] or config_bytes is not None else [guest_name,expression_flag,infinite_query]
try:
    subprocess.run(infinite_argv,executable=str(args.app),input=config.get('infinite_stdin') if config_bytes is not None else None,text=True,env={'LC_ALL':'C','HOME':'/'},cwd='/',umask=0o22,capture_output=True,timeout=.25,check=True)
except subprocess.TimeoutExpired:
    infinite_reference='host infinite computation timed out as expected'
else:
    raise AssertionError('host infinite query unexpectedly terminated')
source = (ROOT/('kernel/kernel-root-minimal.in' if args.root=='minimal' else 'kernel/kernel-root.in')).read_text()
source = re.sub(r'import "\.\./([^"]+)"', lambda m: 'import '+json.dumps(str(ROOT/m.group(1))), source)
source = 'import '+json.dumps(str(ROOT/'components/linux-process.in'))+'\nimport '+json.dumps(str(ROOT/'fixtures/linux-process/checks.in'))+'\n'+source
assert source.count('  shell(port)')==1
source=source.replace('  shell(port)', '  linux-real-app-test(port)\n  shell(port)')
source+='''
fn linux-real-argv-store(vector:Int,index:Int,text:Int)->void{store64(vector+index*8,text);}
fn linux-real-app-test(port:Int)->void{
 let image=0x10000000;let size=APP_SIZE;
 let deadline-waits-before=execution-clock-interrupt-waits;
 let fixture=alloc(4096);let frame=alloc(128);
 // Reuse the already owned fixture page for bounded native loader staging;
 // direct adapter negatives must not lazily allocate a new test-only cache.
 linux-fixture-buffer=fixture;
 let witness-domain=domain-create-user();let witness-frame=frame-alloc();
 if witness-domain<=0{panic("Linux isolation witness domain");}
 store64(witness-frame,0x0654321ABCDEF123);
 domain-map-user-data(witness-domain,0x400000,witness-frame);
 let witness-flags=domain-page-flags(witness-domain,0x400000);
 let authority=cap-mint(root-realm,cap-memory()|cap-serial()|cap-storage());
 if authority<0{panic("Linux test storage grant");}
 let revocable=cap-mint(load64(cap-table-base+current-cap*16),cap-memory()|cap-serial()|cap-storage());
 if revocable<0{panic("Linux test capability allocation");}
 linux-process-trace=TRACE;
 linux-process-budget-ticks=BUDGET;
 SEED_FILES
 let caller-fs=rdmsr(0xC0000100);
 let caller-gs=rdmsr(0xC0000101);
 wrmsr64(0xC0000100,0x400000);
 wrmsr64(0xC0000101,0x400000);
 CASE_CALLS
 if true { WARM_INPUT }
 fs-range-init();
 linux-check(0,fs-write-file("/linux-service-warm","",0));
 linux-check(0,fs-delete("/linux-service-warm"));
 serial-write-cstr(port,"linux-real-app: regression begins");serial-nl(port);
 linux-process-trace=0;
 let heap=heap-next;let free=linux-check-free-count();let domains=domain-count;
 let storage=linux-check-fs-used();
 let leases=fs-range-count;
 let owned=domain-user-owned;let fs=rdmsr(0xC0000100);let gs=rdmsr(0xC0000101);
 let started=ticks;
 linux-check(124,INFINITE_CALL);
 if ticks - started<BUDGET{panic("Linux budget did not consume guest IRQ ticks");}
 linux-check(0,user-budget-active);
 linux-check(heap,heap-next);linux-check(free,linux-check-free-count());
 linux-check(domains,domain-count);linux-check(owned,domain-user-owned);
 linux-check(leases,fs-range-count);
 linux-check(fs,rdmsr(0xC0000100));linux-check(0,domain-user-syscall-hook);
 linux-check(gs,rdmsr(0xC0000101));
 serial-write-cstr(port,"linux-real-app: actual guest IRQ cancellation passed");serial-nl(port);
 let i=0;
 while i<REPEAT{
  let status=PRIMARY_CALL;
  linux-check(EXPECTED_EXIT,status);
  linux-check(heap,heap-next);linux-check(free,linux-check-free-count());
  linux-check(domains,domain-count);linux-check(owned,domain-user-owned);
  linux-check(storage,linux-check-fs-used());
  linux-check(leases,fs-range-count);
  linux-check(0x0654321ABCDEF123,load64(witness-frame));
  linux-check(witness-flags,domain-page-flags(witness-domain,0x400000));
  linux-check(fs,rdmsr(0xC0000100));linux-check(0,domain-user-syscall-hook);
  linux-check(gs,rdmsr(0xC0000101));
  linux-check(0,linux-process-pages);linux-check(0,linux-process-active);
  INPUT_CYCLES
  linux-check-negative(image,size,fixture,frame,revocable,authority);
  if linux-check-file-path!=0{
   linux-check(42,linux-process-run(0x18000000,4096,"/int-width","--abi",linux-check-file-path,authority));
  }
  linux-check(fs,rdmsr(0xC0000100));
  linux-check(gs,rdmsr(0xC0000101));
  linux-check(heap,heap-next);linux-check(free,linux-check-free-count());
  linux-check(domains,domain-count);linux-check(owned,domain-user-owned);
  linux-check(storage,linux-check-fs-used());
  linux-check(leases,fs-range-count);
  linux-check(0x0654321ABCDEF123,load64(witness-frame));
  linux-check(witness-flags,domain-page-flags(witness-domain,0x400000));
  i=i+1;
 }
 linux-check(0x0654321ABCDEF123,load64(witness-frame));
 linux-check(witness-flags,domain-page-flags(witness-domain,0x400000));
 linux-check(0,domain-destroy-user(witness-domain));frame-free(witness-frame);
 linux-check(fs,rdmsr(0xC0000100));wrmsr64(0xC0000100,caller-fs);
 linux-check(gs,rdmsr(0xC0000101));wrmsr64(0xC0000101,caller-gs);
 let waited=execution-clock-interrupt-waits - deadline-waits-before;
 if EXPECT_DEADLINE_WAIT && waited<=0{panic("Native deadline IRQ wait not observed");}
 serial-write-cstr(port,"linux-real-app: native deadline waits ");serial-write-dec-wide(port,waited);serial-nl(port);
 serial-write-cstr(port,"linux-real-app: other domain same-VA sentinel passed");serial-nl(port);
 serial-write-cstr(port,"linux-real-app: regression passed ");serial-write-dec-wide(port,i);serial-nl(port);
}
'''.replace('EXPECT_DEADLINE_WAIT','true' if args.expect_deadline_wait else 'false').replace('cap-memory()|cap-serial()|cap-storage()','cap-memory()|cap-serial()|cap-storage()|cap-timer()' if args.timer_grant else 'cap-memory()|cap-serial()|cap-storage()').replace('PRIMARY_ARGV',','.join(json.dumps(word,ensure_ascii=False) for word in application_argv(cases[0]))).replace('INFINITE_ARGV',','.join(json.dumps(word,ensure_ascii=False) for word in infinite_argv)).replace('APP_SIZE',str(args.app.stat().st_size)).replace('BUDGET',str(args.budget_ticks)).replace('TRACE','1' if args.trace else '0').replace('REPEAT',str(args.repeat)).replace('EXPECTED_EXIT',str(cases[0]['exit'])).replace('FILTER',json.dumps(args.filter))
launch_vector_count=0
def space_call(argv, input_index=None):
    global launch_vector_count
    words=','.join(json.dumps(word,ensure_ascii=False) for word in argv)
    if len(argv)!=3:
        assert 1<=len(argv)<=16
        name='launchargv'+str(launch_vector_count);launch_vector_count+=1
        seed_files.append('let '+name+'=alloc('+str(len(argv)*8)+');'+''.join('linux-real-argv-store('+name+','+str(i)+','+json.dumps(word,ensure_ascii=False)+');' for i,word in enumerate(argv)))
        fd='input'+str(input_index) if input_index is not None else '-1'
        return f'linux-process-run-vector-input(image,size,{name},{len(argv)},authority,{fd})'
    if input_index is not None: return f'linux-process-run-input(image,size,{words},authority,input{input_index})'
    return f'linux-process-run(image,size,{words},authority)'

case_calls=[]
seed_files=[]
input_repeat=[]
if config_bytes is not None and 'infinite_stdin' in config:
    content=config['infinite_stdin']
    assert isinstance(content,str) and 0<len(content.encode())<=65536
    seed_files.append('linux-check(0,fs-write-file("/linux-infinite-input",'+json.dumps(content)+','+str(len(content.encode()))+'));let input_infinite=vfs-open-borrowed-path("/linux-infinite-input",VFS-O-RDONLY);if input_infinite<3{panic("Infinite input open");}')
    words=','.join(json.dumps(word,ensure_ascii=False) for word in infinite_argv)
if any('input' in case or 'file' in case for case in cases):
    witness='{"items":[1,2,3],"message":"from Space VFS"}\n'
    seed_files.append(f'linux-check(0,fs-write-file("/linux-check-data.json",{json.dumps(witness)},45));linux-check-file-path="/linux-check-data.json";')
for index, case in enumerate(cases):
    if 'input' in case or 'file' in case:
        content=case.get('input',case.get('file'))
        data=json.dumps(content, ensure_ascii=False)
        logical_path=guest_file_path(index)
        path=json.dumps(logical_path)
        if not case.get('create'): seed_files.append(f'linux-check(0,fs-write-file({path},{data},{len(content.encode())}));')
        if 'input' in case:
            seed_files.append(f'let input{index}=vfs-open-borrowed-path({path},VFS-O-RDONLY);\n if input{index}<3{{panic("Linux VFS input open");}}')
            call=space_call(application_argv(case),index)
            if not input_repeat or case.get('repeat'):
                input_repeat.append(f'linux-check(0,vfs-lseek(input{index},0,0));\n linux-check({case["exit"]},{call});\n linux-check(1,vfs-fd-valid(input{index}));\n linux-check({len(content.encode())},vfs-fd-offset(input{index}));')
        else:
            call=space_call(application_argv(case,logical_path))
            if len(input_repeat)==1 or case.get('repeat') or (args.application=='lua' and 'f:write' in case['filter']):
                if case.get('reset_each'): input_repeat.append(f'linux-check(0,fs-write-file({path},{data},{len(content.encode())}));')
                input_repeat.append(f'let available{index}=vfs-fd-alloc();\n linux-check({case["exit"]},{call});\n linux-check(available{index},vfs-fd-alloc());')
    else:
        call=space_call(application_argv(case))
        if case.get('repeat'):input_repeat.append(f'linux-check({case["exit"]},{call});')
    case_calls.append(f'''serial-write-cstr(port,"linux-real-app: case {index} begins");serial-nl(port);
 let result{index}={call};
 serial-write-cstr(port,"linux-real-app: case {index} exit ");serial-write-dec-wide(port,result{index});serial-nl(port);''')
source=source.replace('PRIMARY_CALL',space_call(application_argv(cases[0]))).replace('INFINITE_CALL',space_call(infinite_argv,'_infinite' if config_bytes is not None and 'infinite_stdin' in config else None))
source=source.replace('CASE_CALLS','\n'.join(case_calls)).replace('SEED_FILES','\n'.join(seed_files)).replace('INPUT_CYCLES','\n'.join(input_repeat)).replace('WARM_INPUT','\n'.join(input_repeat))
(args.out/'kernel.in').write_text(source)
compiler_sha256=hashlib.sha256(Path(args.compiler).read_bytes()).hexdigest()
commands=[
    ['nasm','-f','bin',str(ROOT/'boot/multiboot.asm'),'-o',str(args.out/'trampoline.bin')],
    ['nasm','-f','bin',str(ROOT/'fixtures/linux-process/int-width.asm'),'-o',str(args.out/'int-width.elf')],
    [args.compiler,'compile','--path',str(args.out/'kernel.in'),'--entry','kernel-entry','--emit','boot','--trampoline',str(args.out/'trampoline.bin'),'--target','native','--target-triple','x86_64-unknown-none','--linkage','static-lib','--out',str(args.out/'kernel.bin')],
]
with (args.out/'compile.log').open('w') as log:
    for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
qcommand=['qemu-system-x86_64','-cpu','max','-kernel',str(args.out/'kernel.bin'),'-m','512M','-display','none','-no-reboot','-serial','file:'+str(args.out/'serial.log'),'-device',f'loader,file={args.app},addr=0x10000000,force-raw=on','-device',f'loader,file={args.out / "int-width.elf"},addr=0x18000000,force-raw=on']
if args.no_hpet:qcommand+=['-machine','pc,hpet=off']
with (args.out/'qemu.log').open('w') as log:
    qemu=subprocess.Popen(qcommand,stdout=log,stderr=subprocess.STDOUT)
    try:
        wall_timeout = args.wall_timeout if args.wall_timeout is not None else max(90, args.repeat * 8)
        qemu_started = time.monotonic()
        deadline = qemu_started + wall_timeout
        while time.monotonic()<deadline:
            data=(args.out/'serial.log').read_bytes() if (args.out/'serial.log').exists() else b''
            if b'linux-real-app: regression passed ' in data or b'PANIC' in data or b'nanokernel fault handler halting' in data:break
            if qemu.poll() is not None:break
            time.sleep(.05)
        text=(args.out/'serial.log').read_text(errors='replace')
        results=[]
        for index, case in enumerate(cases):
            body=text.split(f'linux-real-app: case {index} begins\n',1)[1]
            before_exit=body.split(f'linux-real-app: case {index} exit ',1)[0]
            if args.trace:
                before_exit=re.sub(r'linux-process: (?:(?:syscall|result|suspended) -?\d+|completed \d+ \d+ -?\d+)\n','',before_exit)
            match=re.search(rf'linux-real-app: case {index} exit (-?\d+)',body)
            assert match is not None,text
            status=int(match.group(1))
            results.append({'filter':case['filter'],'combined_serial_output':before_exit,'exit':status,
                            'passed':status==case['exit'] and before_exit==case.get('space_expected_stdout',case['stdout'])+case['stderr']})
        regression=f'linux-real-app: regression passed {args.repeat}\n' in text
        qemu_elapsed = time.monotonic() - qemu_started
        wall_timeout_hit = not regression and qemu_elapsed >= wall_timeout and qemu.poll() is None
        warmup_activations=sum('linux-process-run' in item for item in input_repeat)
        actual_activations=len(cases)+warmup_activations+args.repeat*(1+warmup_activations)+1
        report={'space_status':'passed' if all(case['passed'] for case in results) and regression else 'failed',
                'environment':{'LC_ALL':'C','HOME':'/'},'working_directory':'/','umask':'022','source_receipt':str(ROOT/'receipt.json'),'source_receipt_sha256':hashlib.sha256((ROOT/'receipt.json').read_bytes()).hexdigest(),
                'root':args.root,'timer_granted':args.timer_grant,'hpet_available':not args.no_hpet,'native_deadline_idle_waits':int(re.search(r'linux-real-app: native deadline waits (\d+)',text)[1]) if re.search(r'linux-real-app: native deadline waits (\d+)',text) else None,'native_clock_provider_controls_per_cycle':True,'application':version+' unmodified static Linux ELF','application_sha256':app['sha256'],'application_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
                'reference':cases,'infinite_reference':infinite_reference, 'space':{'cases':results,'repeat_cleanup_and_denial_passed':regression,
                'repeat_count':args.repeat,'external_wall_timeout_seconds':wall_timeout,'external_wall_timeout_hit':wall_timeout_hit,'qemu_elapsed_seconds':qemu_elapsed,'actual_application_activations':actual_activations,'file_transition_warmup_activations':warmup_activations,'guest_budget_ticks':args.budget_ticks,'guest_irq_cancellation_passed':'linux-real-app: actual guest IRQ cancellation passed' in text,'other_domain_same_va_sentinel_passed':'linux-real-app: other domain same-VA sentinel passed' in text,'hardware_faults_per_cycle':7,'caller_fs_canary':4194304,'caller_gs_canary':4194304,'qemu_command':qcommand,'kernel_sha256':hashlib.sha256((args.out/'kernel.bin').read_bytes()).hexdigest()},
                'personality_sha256':hashlib.sha256((ROOT/'components/linux-process.in').read_bytes()).hexdigest(),
                'anonymous_memory_sha256':hashlib.sha256((ROOT/'components/linux-process-mmap.in').read_bytes()).hexdigest(),
                'file_adapter_sha256':hashlib.sha256((ROOT/'components/linux-process-files.in').read_bytes()).hexdigest(),
                'file_metadata_sha256':hashlib.sha256((ROOT/'components/linux-process-metadata.in').read_bytes()).hexdigest(),
                'checks_sha256':hashlib.sha256((ROOT/'fixtures/linux-process/checks.in').read_bytes()).hexdigest(),
                'int_width_probe':{'elf_sha256':hashlib.sha256((args.out/'int-width.elf').read_bytes()).hexdigest(),'activations':args.repeat if any('input' in case or 'file' in case for case in cases) else 0,'actual_linux_host_oracle':json.loads(width_host.stdout)},
                'compiler':args.compiler,'compiler_sha256':compiler_sha256}
        (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        assert report['space_status']=='passed',f'actual Linux execution failed; inspect {args.out}/report.json and serial.log'
        print(f'PASS: {version} executed {actual_activations} times inside Space (including guest IRQ cancellation); {args.repeat} fault/authority/pointer/cleanup cycles; {args.out}')
    finally:
        qemu.terminate()
        try:qemu.wait(timeout=3)
        except subprocess.TimeoutExpired:qemu.kill();qemu.wait()
