#!/usr/bin/env python3
"""Execute bounded SCI validation against malformed bytes and actual compiler artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--in',dest='compiler',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--artifacts',type=Path,nargs='*',default=[])
a=p.parse_args();a.out=a.out.resolve();a.compiler=a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):p.error('--out must be new or empty')
a.out.mkdir(parents=True,exist_ok=True)
source=(ROOT/'components/sci-validate.in').read_text().replace('package space.kernel','')
def put(data,offset,value):struct.pack_into('<Q',data,offset,value&0xffffffffffffffff)
def image():
 b=bytearray(144)
 for offset,value in enumerate([0x5343490000000002,20,0x48000040,len(b),1,80,1,96]):put(b,offset*8,value)
 b[64]=0xc3;b[72]=0xe8
 put(b,80,112);put(b,88,0);put(b,96,118);put(b,104,8)
 b[112:118]=b'entry\0';b[118:129]=b'serial-put\0'
 return b
cases=[]
def add(name,data,expected=0,available=None):cases.append((name,bytes(data),expected,len(data) if available is None else available))
add('valid-v2',image(),1)
v1=bytearray(40)
for offset,value in enumerate([0x5343490000000001,0,0x48000020,40]):put(v1,offset*8,value)
v1[32]=0xc3;add('valid-v1',v1,1)
for available in [0,7,31,32,63]:add('truncated-extent-'+str(available),image(),available=available)
for name,offset,value in [('magic',0,7),('size-negative',24,-1),('size-zero',24,0),('header-only',24,64),('size-past-extent',24,145),
 ('entry-negative',16,-1),('entry-unaligned',16,0x48000041),('export-count-negative',32,-1),('export-count-limit',32,4097),
 ('import-count-negative',48,-1),('import-count-limit',48,513),('export-table-negative',40,-1),('table-in-header',40,48),
 ('table-unaligned',40,81),('table-past-end',40,136),('overlapping-tables',56,80),('import-table-past-end',56,144),
 ('export-name-in-code',80,64),('export-name-past-end',80,144),('export-target-negative',88,-1),('export-target-in-metadata',88,16),
 ('import-name-in-table',96,96),('import-name-past-end',96,144),('import-site-negative',104,-1),('import-site-past-payload',104,12)]:
 b=image();put(b,offset,value);add(name,b)
b=image();b[112]=0;add('empty-export-name',b)
b=image();b[118:]=b'x'*(len(b)-118);add('unterminated-name',b)
b=image();b[72]=0xe9;add('not-call-rel32',b)
b=image()+bytes(5000-len(image()));put(b,24,len(b));put(b,16,0xfffff040);add('virtual-span-wrap',b)
for site in [8,9]:
 b=bytearray(160);b[:112]=image()[:112];put(b,24,len(b));put(b,48,2);put(b,80,128);put(b,96,134)
 put(b,112,134);put(b,120,site);b[64+site]=0xe8;b[128:134]=b'entry\0';b[134:145]=b'serial-put\0'
 add('duplicate-or-overlap-site-'+str(site),b)
for count,expected in [(255,1),(256,0)]:
 b=image()[:112]+b'x'*count+b'\0';put(b,24,len(b));put(b,48,0);put(b,56,96)
 add('name-length-'+str(count),b,expected)
# Empty tables can use zero offsets without causing a header-relative table read.
b=bytearray(72)
for offset,value in enumerate([0x5343490000000002,0,0x48000040,72,0,0,0,0]):put(b,offset*8,value)
b[64]=0xc3;add('valid-zero-tables',b,1)
artifacts=[]
for path in a.artifacts:
 data=path.read_bytes();add('compiler-'+path.name,data,1)
 artifacts.append({'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
source+='\nvar model-case:Int=0;var model-extent:Int=0;var model-bad-read:Int=0;var model-reads:Int=0;\n'
for i,(_,data,_,_) in enumerate(cases):source+='var model-image-'+str(i)+':[Int]=['+','.join(map(str,data))+'];\n'
source+='''fn load8(address:Int)->Int {
 model-reads+=1;
 if address<16 || address-16>=model-extent {model-bad-read+=1;return 0;}
'''.replace('address-16','address - 16')
for i in range(len(cases)):source+=f'if model-case=={i} {{return model-image-{i}[address - 16];}}\n'
source+='return 0;}\nfn load64(address:Int)->Int {let n=0;let i=0;while i<8{n=n|(load8(address+i)<<(i*8));i=i+1;}return n;}\n'
source+='fn main()->Int {\n'
for i,(name,data,expected,available) in enumerate(cases):
 source+=f'model-case={i};model-extent={available};model-bad-read=0;model-reads=0;\n'
 source+=f'if runtime-instance-image-valid(16,{available})!={expected} {{return {1000+i};}}\n'
 source+=f'if model-bad-read!=0 {{return {2000+i};}}\n'
source+='''model-bad-read=0;model-reads=0;
 if runtime-instance-image-valid(0,144)!=0 || runtime-instance-image-valid(0x100000000,144)!=0 || runtime-instance-image-valid(16,-1)!=0 || runtime-instance-image-valid(16,0x200001)!=0 || model-reads!=0{return 3000;}
 return 42;}
'''
fixture=a.out/'validation.in';fixture.write_text(source)
report={'source_sha256':hashlib.sha256((ROOT/'components/sci-validate.in').read_bytes()).hexdigest(),'compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'cases':[{'name':n,'expected':e,'available':v,'actual_bytes':len(d)} for n,d,e,v in cases],'artifacts':artifacts,'profiles':[]}
for profile in ['default','lean','harden']:
 command=[str(a.compiler),'compile','--path',str(fixture),'--target','jit','--profile',profile,'--out',str(a.out/profile),'--json']
 result=subprocess.run(command,capture_output=True,text=True,timeout=120)
 (a.out/(profile+'.json')).write_text(result.stdout)
 data=json.loads(result.stdout);passed=result.returncode==0 and data.get('eval_result')=={'Int':42}
 report['profiles'].append({'profile':profile,'passed':passed,'result':data.get('eval_result'),'command':command})
 (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 if not passed:raise SystemExit('FAIL '+profile+': '+str(data.get('eval_result') or data.get('error')))
 print(f'PASS {profile}: {len(cases)} SCI cases; no reads outside trusted extent')
