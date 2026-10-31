"""Parse the actual release step scripts with PowerShell before compiling."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import yaml

ROOT=Path(__file__).resolve().parents[2]
cases=[]
for filename in ('workspace-exe.yml','workspace-prepare.yml','workspace-native-approved.yml'):
    data=yaml.safe_load((ROOT/'.github/workflows'/filename).read_text())
    for job in data['jobs'].values():
        for step in job.get('steps',[]):
            if 'run' in step and re.search(r'^(pwsh|powershell)(?:\s|$)',step.get('shell','')):
                cases.append({'name':filename+':'+step.get('name','step'),
                              'source':re.sub(r'\$\{\{.*?\}\}','GHA_VALUE',step['run'],flags=re.S)})
cases.append({'name':'Restore-ApprovedNativeRuntime.ps1','source':(ROOT/'.github/scripts/Restore-ApprovedNativeRuntime.ps1').read_text()})
pwsh=shutil.which('pwsh') or shutil.which('powershell')
if not pwsh:raise SystemExit('PowerShell is required for actual release script parsing')
with tempfile.TemporaryDirectory(prefix='release-ps-parser-') as raw:
    root=Path(raw);data=root/'scripts.json';data.write_text(json.dumps(cases))
    worker=root/'parse.ps1';worker.write_text('''param([string]$InputJson)
$ErrorActionPreference='Stop'
$cases=Get-Content -LiteralPath $InputJson -Raw|ConvertFrom-Json
foreach($case in $cases){
  $tokens=$null;$errors=$null
  [void][Management.Automation.Language.Parser]::ParseInput([string]$case.source,[ref]$tokens,[ref]$errors)
  if($errors.Count){throw ($case.name+': '+(($errors|ForEach-Object{$_.Message})-join'; '))}
}
Write-Host ('[RELEASE/POWERSHELL][PASS] actual step scripts='+$cases.Count)
''')
    subprocess.run([pwsh,'-NoLogo','-NoProfile','-NonInteractive','-File',str(worker),str(data)],check=True)
