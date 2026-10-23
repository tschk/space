#!/usr/bin/env python3
"""Execute the real RTC service with independent calendar and update-cycle oracles."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--in', dest='compiler', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--source', type=Path, default=ROOT / 'components/time.in', help='Owning source; supports retained negative controls')
p.add_argument('--probe', choices=('all', 'uip'), default='all')
a = p.parse_args()
a.out = a.out.resolve()
a.compiler = a.compiler.resolve()
if a.out.exists() and any(a.out.iterdir()):
    p.error('--out must be new or empty')
a.out.mkdir(parents=True, exist_ok=True)
text = a.source.read_text()
functions = []
for match in re.finditer(r'^fn (time-component-[\w-]+)\(', text, re.MULTILINE):
    if match[1] in ('time-component-rtc-read', 'time-component-entry'):
        continue
    start = text.index('{', match.start())
    end = start + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    functions.append(text[match.start():end])
globals = '\n'.join(line for line in text.splitlines() if line.startswith('var time-component-'))
source = '''var model-registers:[Int]=[''' + ','.join(['0'] * 256) + '''];
var model-mode:Int=0;var model-reads:Int=0;var model-status-reads:Int=0;var model-seconds:Int=0;
fn time-component-rtc-read(reg:Int)->Int {
 model-reads+=1;
 if reg==10 {model-status-reads+=1;if model-mode==1 || (model-mode==2 && model-status-reads==2){return 128;}return 0;}
 if reg==0 {
  model-seconds+=1;
  if model-mode==3 {return model-seconds%2;}
  if model-mode==4 && model-seconds>=2 {model-registers[0]=0;model-registers[2]=0;model-registers[4]=0;model-registers[7]=1;model-registers[8]=1;model-registers[9]=0x27;}
 }
 if reg==11 && model-mode==5 {return 2+4*(model-reads%2);}
 return model-registers[reg];
}
fn model-reset()->void {model-mode=0;model-reads=0;model-status-reads=0;model-seconds=0;time-component-ts=4242;time-component-y=1;time-component-mo=2;time-component-d=3;time-component-h=4;time-component-mi=5;time-component-s=6;return;}
fn model-preserved()->Int {if time-component-ts!=4242 || time-component-y!=1 || time-component-mo!=2 || time-component-d!=3 || time-component-h!=4 || time-component-mi!=5 || time-component-s!=6{return 0;}return 1;}
''' + globals + '\n' + '\n'.join(functions)
cases = []
def bcd(n):
    return n // 10 * 16 + n % 10

def registers(year=2026, month=10, day=24, hour=12, minute=34, second=56, binary=False, twelve=False, century=True):
    h = hour
    if twelve:
        h = hour % 12 or 12
    encode = (lambda n: n) if binary else bcd
    values = {0: encode(second), 2: encode(minute), 4: encode(h) | (128 if twelve and hour >= 12 else 0),
              7: encode(day), 8: encode(month), 9: encode(year % 100), 50: encode(year // 100) if century else 0,
              11: (4 if binary else 0) | (0 if twelve else 2)}
    return values

for date in [(1970,1,1,0,0,0), (1999,12,31,23,59,59), (2000,2,29,12,0,0),
             (2026,10,24,12,34,56), (2100,3,1,0,0,1), (2400,2,29,23,59,59), (9999,12,31,23,59,59)]:
    for binary in (False, True):
        for twelve in (False, True):
            values = registers(*date, binary=binary, twelve=twelve)
            expected = int(datetime(*date, tzinfo=timezone.utc).timestamp())
            cases.append((str(date) + (' binary' if binary else ' BCD') + ('12h' if twelve else '24h'), values, expected, date))
for year in (1980, 1999, 2000, 2079):
    for absent in (0, 255):
        values = registers(year=year, century=False)
        values[50] = absent
        date = (year,10,24,12,34,56)
        cases.append((f'absent-century-{year}-{absent}', values, int(datetime(*date,tzinfo=timezone.utc).timestamp()), date))
for name, field, bad in [('bad-BCD-seconds',0,0x5a),('seconds60',0,0x60),('minutes60',2,0x60),
                         ('hour24',4,0x24),('24h-PM-bit',4,0x92),('day0',7,0),('month0',8,0),
                         ('month13',8,0x13),('bad-year-BCD',9,0xab),('bad-century',50,0x1a),('frozen-SET',11,0x82)]:
    values = registers();values[field] = bad
    cases.append((name,values,-1,None))
for date in [(2100,2,29,12,0,0),(2026,4,31,12,0,0),(1969,12,31,23,59,59)]:
    cases.append(('invalid-date-'+str(date),registers(*date),-1,None))
for bad in (0,0x13,0x80):
    values=registers(twelve=True);values[4]=bad
    cases.append(('invalid-12h-'+str(bad),values,-1,None))
if a.probe == 'uip':
    cases = []
body=['fn main()->Int {']
for index,(name,values,expected,date) in enumerate(cases):
    body.append('model-reset();')
    body.extend(f'model-registers[{k}]={v};' for k,v in values.items())
    body.append(f'if time-component-wallclock()!={expected} {{return {1000+index};}}')
    if date:
        for field,value in zip(('y','mo','d','h','mi','s'),date):
            body.append(f'if time-component-{field}!={value} {{return {2000+index};}}')
        body.append(f'if time-component-ts!={expected} || model-reads!=19 {{return {3000+index};}}')
    else:
        body.append(f'if model-preserved()!=1 {{return {4000+index};}}')
# Retry after UIP starts during first sample; require a whole fresh pair.
cycle_cases = [(1,256,256)] if a.probe == 'uip' else [(1,256,256),(2,29,5),(3,4864,768),(5,4864,768)]
for mode,reads,status in cycle_cases:
    body.append('model-reset();')
    body.extend(f'model-registers[{k}]={v};' for k,v in registers().items())
    body.append(f'model-mode={mode};')
    expected = int(datetime(2026,10,24,12,34,56,tzinfo=timezone.utc).timestamp()) if mode==2 else -1
    body.append(f'if time-component-wallclock()!={expected} || model-reads!={reads} || model-status-reads!={status} {{return {5000+mode};}}')
    if mode!=2:body.append(f'if model-preserved()!=1 {{return {5100+mode};}}')
if a.probe == 'all':
    body.append('model-reset();')
    body.extend(f'model-registers[{k}]={v};' for k,v in registers(2026,12,31,23,59,59).items())
    body.append('model-mode=4;')
    expected=int(datetime(2027,1,1,tzinfo=timezone.utc).timestamp())
    body.append(f'if time-component-wallclock()!={expected} || model-reads!=38 || time-component-y!=2027 || time-component-mo!=1 || time-component-d!=1 {{return 5200;}}')
body.append('return 42;}')
source += '\n' + '\n'.join(body)
fixture=a.out/'time.in';fixture.write_text(source)
report={'source':str(a.source),'probe':a.probe,'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'compiler_sha256':hashlib.sha256(a.compiler.read_bytes()).hexdigest(),'calendar_cases':len(cases),'cycle_cases':len(cycle_cases)+(a.probe=='all'),'profiles':[]}
for profile in ('default','lean','harden'):
    command=[str(a.compiler),'compile','--path',str(fixture),'--target','jit','--profile',profile,'--out',str(a.out/profile),'--json']
    result=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (a.out/(profile+'.json')).write_text(result.stdout)
    result_data=json.loads(result.stdout)
    passed=result.returncode==0 and result_data.get('eval_result')=={'Int':42}
    report['profiles'].append({'profile':profile,'passed':passed,'result':result_data.get('eval_result'),'command':command})
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not passed:raise SystemExit(f'FAIL {profile}: {result_data.get("eval_result") or result_data.get("error")}')
    print(f'PASS {profile}: {len(cases)} independent UTC calendar cases and bounded UIP/rollover/mode controls')
