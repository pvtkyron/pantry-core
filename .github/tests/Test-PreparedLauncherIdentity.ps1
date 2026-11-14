[CmdletBinding()]param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$owner=Join-Path $PSScriptRoot '../scripts/Seal-PreparedDelivery.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($owner,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Actual prepared delivery owner parser rejected'}
$definitions=@($ast.FindAll({param($node)$node-is[Management.Automation.Language.FunctionDefinitionAst]-and$node.Name-ceq'Assert-PreparedLauncherIdentity'},$true))
if($definitions.Count-ne1){throw 'Prepared Launcher identity owner missing'}
. ([scriptblock]::Create($definitions[0].Extent.Text))
$head='a'*40;$plan='b'*40;$hash='c'*64;$id='d'*32
function Receipt([string]$Source){return [pscustomobject]@{schema=1;workspace_sha=$Source;runtime_externalized=$true;launcher=[pscustomobject]@{exe_sha256=$hash;build_id=$id}}}
function Metadata([string]$Source){return [pscustomobject]@{workspace_commit=$Source.Substring(0,12);exe_sha256=$hash;build_id=$id}}
$checks=0
foreach($original in @($head,$plan)){
    $r=Receipt $original;$m=Metadata $original
    $beforeR=$r|ConvertTo-Json -Depth 5 -Compress;$beforeM=$m|ConvertTo-Json -Compress
    $accepted=Assert-PreparedLauncherIdentity -Receipt $r -Metadata $m -HeadRevision $head -PlanRevision $plan -ExecutableSha256 $hash
    if($accepted-cne$original-or($r|ConvertTo-Json -Depth 5 -Compress)-cne$beforeR-or($m|ConvertTo-Json -Compress)-cne$beforeM){throw 'Original compiled identity was relabeled'}
    $checks++
}
$verified='f'*40
$r=Receipt $verified;$m=Metadata $verified;$beforeR=$r|ConvertTo-Json -Depth 5 -Compress;$beforeM=$m|ConvertTo-Json -Compress
$accepted=Assert-PreparedLauncherIdentity -Receipt $r -Metadata $m -HeadRevision $head -PlanRevision $plan -ExecutableSha256 $hash -VerifiedCompiledSource $verified
if($accepted-cne$verified-or($r|ConvertTo-Json -Depth 5 -Compress)-cne$beforeR-or($m|ConvertTo-Json -Compress)-cne$beforeM){throw 'Verified original compiled identity was modified'}
$checks++
foreach($scenario in @('missing-proof','wrong-proof','tampered-metadata','tampered-receipt','wrong-digest','bad-proof-shape')){
    $r=Receipt $verified;$m=Metadata $verified;$trusted=$verified;$digest=$hash
    switch($scenario){
      missing-proof {$trusted=''}
      wrong-proof {$trusted='e'*40}
      tampered-metadata {$m.workspace_commit='e'*12}
      tampered-receipt {$r.workspace_sha='e'*40}
      wrong-digest {$digest='e'*64}
      bad-proof-shape {$trusted='main'}
    }
    $blocked=$false
    try{Assert-PreparedLauncherIdentity -Receipt $r -Metadata $m -HeadRevision $head -PlanRevision $plan -ExecutableSha256 $digest -VerifiedCompiledSource $trusted|Out-Null}catch{$blocked=$true}
    if(!$blocked){throw ('Unverified cross-source Launcher admitted: '+$scenario)}
    $checks++
}
foreach($case in @('stale','relabel','digest','receipt-digest','build','not-external','schema','invalid-head')){
    $r=Receipt $plan;$m=Metadata $plan;$current=$head
    switch($case){
        stale {$r.workspace_sha='e'*40;$m.workspace_commit='e'*12}
        relabel {$r.workspace_sha=$head}
        digest {$m.exe_sha256='e'*64}
        receipt-digest {$r.launcher.exe_sha256='e'*64}
        build {$r.launcher.build_id='e'*32}
        not-external {$r.runtime_externalized=$false}
        schema {$r.schema=2}
        invalid-head {$current='main'}
    }
    $blocked=$false
    try{Assert-PreparedLauncherIdentity -Receipt $r -Metadata $m -HeadRevision $current -PlanRevision $plan -ExecutableSha256 $hash|Out-Null}catch{$blocked=$true}
    if(!$blocked){throw ("Invalid compiled Launcher identity accepted: "+$case)}
    $checks++
}
Write-Host ("[PREPARED/LAUNCHER/IDENTITY][PASS] cases="+$checks+"; original plan/HEAD retained, stale/tampered metadata rejected")
