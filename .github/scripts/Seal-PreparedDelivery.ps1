[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SourceRoot,[Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$SourceRoot=(Resolve-Path -LiteralPath $SourceRoot).Path
$pantry=Join-Path $SourceRoot 'Distribution'
$sha=(& git -C $SourceRoot rev-parse HEAD).Trim().ToLowerInvariant()
if($LASTEXITCODE-or$sha-cnotmatch'^[0-9a-f]{40}$'){throw 'Prepared delivery source identity unavailable'}
$receipt=Get-Content -LiteralPath (Join-Path $pantry 'release/launcher-lane-v1.json') -Raw|ConvertFrom-Json
if($receipt.schema-ne1-or$receipt.workspace_sha-cne$sha-or!$receipt.runtime_externalized){throw 'Prepared delivery Launcher receipt differs from pinned source'}
$paths=[Collections.Generic.List[string]]::new()
foreach($leaf in @('client/Launcher.exe','client/Launcher.build.json','release/launcher-lane-v1.json','release/runtime-lane-v1.json','release/delivery-provenance-v1.json')){$paths.Add('Distribution/'+$leaf)}
foreach($property in $receipt.resources.PSObject.Properties){
    $logical=[string]$property.Name
    if($logical-cne'client/Kyron.release-set.json'-and$logical-cnotmatch'^client/(?:runtime/[0-9a-f]{32}/[A-Za-z0-9._/-]+|tools/(?:commanders|android|xray)/[A-Za-z0-9._/-]+)$'){throw 'Prepared delivery resource path rejected'}
    if($logical-match'(^|/)\.{1,2}(/|$)|//'){throw 'Prepared delivery resource traversal rejected'}
    $file=Join-Path $pantry $logical
    if((Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant()-cne$property.Value.sha256-or(Get-Item -LiteralPath $file).Length-ne[int64]$property.Value.size){throw 'Prepared delivery resource differs from signed lane receipt'}
    $paths.Add('Distribution/'+$logical)
}
foreach($leaf in @('libkyron.so','libkyron64.so','libkyroni.so','libkyroni64.so')){$paths.Add('Distribution/lib/'+$leaf)}
foreach($abi in @('armeabi-v7a','arm64-v8a')){foreach($leaf in @('libkyron.release.json','libkyron.so.kyron-finalized')){$paths.Add('Distribution/release/native-attestations/'+$abi+'/'+$leaf)}}
foreach($leaf in @('client/Bootstrap.exe','client/Bootstrap.release.json','release/bootstrap-v10.marker','release/bootstrap-delivery-v1.json')){if(Test-Path -LiteralPath (Join-Path $pantry $leaf) -PathType Leaf){$paths.Add('Distribution/'+$leaf)}}
$paths=@($paths|Sort-Object -Unique)
foreach($path in $paths){
    if(!(Test-Path -LiteralPath (Join-Path $SourceRoot $path) -PathType Leaf)){throw 'Prepared delivery generated input missing'}
    & git -C $SourceRoot check-ignore --quiet -- $path
    if($LASTEXITCODE){throw 'Prepared delivery may contain only ignored generated outputs'}
}
& (Join-Path $PSScriptRoot '../workflows/workspace-handoff.ps1') -Mode pack -Lane delivery -PantryRoot $pantry -WorkspaceSha $sha -PantrySha $sha -Secret $env:KYRON_HANDOFF_SECRET -SourceRoot $SourceRoot -Paths $paths -OutputRoot $OutputRoot
if(!$?){throw 'Prepared delivery sealing failed'}
Write-Host '[HOSTED/DELIVERY][SEALED] generated outputs only; original lane provenance retained'
