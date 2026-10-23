#!/usr/bin/env python3
"""Independently inspect pinned original PE imports against the declared union.

This is static dependency/disassembly evidence, never an original runtime trace.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--apps',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
out=a.out.resolve()
assert not out.exists() or not any(out.iterdir()),'--out must be new or empty'
out.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('pe_inspector',ROOT/'scripts/inspect-windows-application.py')
pe=importlib.util.module_from_spec(spec);spec.loader.exec_module(pe)
contract=json.loads((ROOT/'fixtures/windows-protected/composed-contract.json').read_text())
assert len(contract['api_ids'])==43 and set(contract['api_ids'].values())==set(range(43))
manifest=json.loads((ROOT/'fixtures/applications/windows-cli-2024.json').read_text())
apps=[]
for declared in manifest['apps']:
    path=(a.apps/declared['filename']).resolve();view=pe.inspect(path)
    assert view['sha256']==declared['sha256'] and view['size_bytes']==declared['size_bytes']
    supported=[];unknown=[]
    for dll,names in view['imports'].items():
        for slot,name in enumerate(names,1):
            row=dict(dll=dll,one_based_slot=slot,name=name)
            if dll.lower()=='kernel32.dll' and isinstance(name,str) and name in contract['api_ids']:
                supported.append(dict(row,api_id=contract['api_ids'][name]))
            else:unknown.append(row)
    accepted_dirs={1,12}
    # Existing general directory guard admits imports/IAT only in this mode;
    # an unused relocation table still needs separate validation/admission.
    mask=sum(1<<int(i) for i in view['directories'] if int(i) not in accepted_dirs)
    row=dict(artifact=view,executed=False,supported_imports=supported,unsupported_imports=unknown,import_slots=view['import_count'],execution_import_slot_limit=contract['execution_import_limit'],unsupported_directory_mask=hex(mask),preferred_base_policy='zero-slide only; no relocation execution admitted')
    if declared['name']=='sqlite3':
        assert len(supported)==42 and len(unknown)==115 and view['import_count']==157
        assert unknown[0]['one_based_slot']==3 and unknown[0]['name']=='SetCurrentDirectoryW'
        assert mask==0x46c and view['entry']=='0x140003a8a' and view['preferred_base']=='0x140000000'
        command=['objdump','-d','--start-address=0x140234e48','--stop-address=0x140234ee0',str(path)]
        disassembly=subprocess.check_output(command,text=True)
        for address in ['140234e74','140234e82','140234e8e','140234e9e']:assert address in disassembly
        (out/'sqlite-security-cookie.disassembly.txt').write_text(disassembly)
        row['static_startup_observation']=dict(command=command,security_cookie_calls=['GetSystemTimeAsFileTime','GetCurrentThreadId','GetCurrentProcessId','QueryPerformanceCounter'],source='Pinned original x64 disassembly, not Space runtime execution',disassembly_sha256=hashlib.sha256(disassembly.encode()).hexdigest())
    apps.append(row)
report=dict(status='passed',classification='Independent static dependency and disassembly evidence; original apps remain unexecuted',contract_sha256=hashlib.sha256((ROOT/'fixtures/windows-protected/composed-contract.json').read_bytes()).hexdigest(),apps=apps)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS pinned original Windows static union dependency barriers; no original execution')
