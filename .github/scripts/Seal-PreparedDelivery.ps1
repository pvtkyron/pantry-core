[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SourceRoot,[Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Assert-PreparedLauncherIdentity {
    [CmdletBinding()]param([object]$Receipt,[object]$Metadata,[string]$HeadRevision,[string]$PlanRevision,[string]$ExecutableSha256,[string]$VerifiedCompiledSource='')
    foreach($revision in @($HeadRevision,$PlanRevision)){if($revision-cnotmatch'^[0-9a-f]{40}$'){throw 'Prepared delivery source revision invalid'}}
    $compiled=[string]$Receipt.workspace_sha
    if($VerifiedCompiledSource-and$VerifiedCompiledSource-cnotmatch'^[0-9a-f]{40}$'){throw 'Verified original Launcher compiler identity malformed'}
    if($Receipt.schema-ne1-or!$Receipt.runtime_externalized-or$compiled-cnotmatch'^[0-9a-f]{40}$'-or($compiled-cnotin@($HeadRevision,$PlanRevision)-and$compiled-cne$VerifiedCompiledSource)){throw 'Prepared delivery Launcher receipt differs from its compiled source'}
    if(([string]$Metadata.workspace_commit)-cne$compiled.Substring(0,12)){throw 'Prepared delivery Launcher metadata differs from original compiled receipt'}
    if($ExecutableSha256-cnotmatch'^[0-9a-f]{64}$'-or([string]$Metadata.exe_sha256)-cne$ExecutableSha256-or([string]$Receipt.launcher.exe_sha256)-cne$ExecutableSha256){throw 'Prepared delivery Launcher digest differs from original signed bytes'}
    if(([string]$Metadata.build_id)-cnotmatch'^[0-9a-f]{32}$'-or([string]$Metadata.build_id)-cne([string]$Receipt.launcher.build_id)){throw 'Prepared delivery Launcher build identity differs'}
    return $compiled
}
$SourceRoot=(Resolve-Path -LiteralPath $SourceRoot).Path
$pantry=Join-Path $SourceRoot 'Distribution'
$sha=(& git -C $SourceRoot rev-parse HEAD).Trim().ToLowerInvariant()
if($LASTEXITCODE-or$sha-cnotmatch'^[0-9a-f]{40}$'){throw 'Prepared delivery source identity unavailable'}
$receipt=Get-Content -LiteralPath (Join-Path $pantry 'release/launcher-lane-v1.json') -Raw|ConvertFrom-Json
$launcherSha=([string]$receipt.workspace_sha).Trim().ToLowerInvariant()
if($receipt.schema-ne1-or$launcherSha-cnotmatch'^[0-9a-f]{40}$'-or!$receipt.runtime_externalized){throw 'Prepared delivery Launcher receipt invalid'}
$verifiedCompilerSource=''
if($launcherSha-cne$sha){
    . (Join-Path $SourceRoot 'etc/build/workspace-common.ps1')
    $expected=(Get-WorkspacePlanRevision $SourceRoot launcher HEAD).Trim().ToLowerInvariant()
    & git -C $SourceRoot merge-base --is-ancestor $launcherSha $sha
    if($LASTEXITCODE-ne0){throw 'Prepared delivery Launcher source is not an ancestor of pinned source'}
    $legacyProof=$false
    if($launcherSha-ceq$expected){
        $protected=@(Get-WorkspaceReleasePlanPathspecs launcher)
        if(!$protected.Count){throw 'Prepared delivery Launcher protected input scope missing'}
        & git -C $SourceRoot diff --quiet --no-renames $launcherSha $sha -- @protected
        if($LASTEXITCODE-gt1){throw 'Prepared delivery Launcher protected input comparison unavailable'}
        $legacyProof=$LASTEXITCODE-eq0
    }
    if(!$legacyProof){
        if($env:GITHUB_ACTIONS-cne'true'-or$env:GITHUB_REPOSITORY-cne'pvtkyron/pantry-core'-or$env:GITHUB_REF-cne'refs/heads/main'){throw 'Hosted signed compiler proof required for cross-source Launcher'}
        $proof=Join-Path $env:GITHUB_WORKSPACE 'recipe/.github/scripts/workspace_lane_source.py'
        if(!(Test-Path -LiteralPath $proof -PathType Leaf)){throw 'Pinned compiler input verifier missing'}
        & python $proof --workspace $SourceRoot --original $launcherSha --current $sha --lane exe
        if($LASTEXITCODE-ne0){throw 'Prepared delivery original Launcher compiler inputs changed'}
        $verifiedCompilerSource=$launcherSha
        Write-Host "[HOSTED/DELIVERY][COMPILER-PARITY/OK] original=$launcherSha current=$sha signed_identity_preserved"
    }else{Write-Host "[HOSTED/DELIVERY][SOURCE-PARITY/OK] source_plan=$launcherSha pinned_head=$sha input_tree=unchanged"}
}
$planForIdentity=if($launcherSha-cne$sha){$expected}else{$sha}
$metadata=Get-Content -LiteralPath (Join-Path $pantry 'client/Launcher.build.json') -Raw|ConvertFrom-Json
$executableSha=(Get-FileHash -LiteralPath (Join-Path $pantry 'client/Launcher.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
$originalLauncherSource=Assert-PreparedLauncherIdentity -Receipt $receipt -Metadata $metadata -HeadRevision $sha -PlanRevision $planForIdentity -ExecutableSha256 $executableSha -VerifiedCompiledSource $verifiedCompilerSource
Write-Host "[HOSTED/DELIVERY][IDENTITY/OK] original_launcher=$originalLauncherSource executable_and_build=verified"
$proof=Join-Path $env:GITHUB_WORKSPACE 'recipe/.github/scripts/verify_precompiled_dex.py'
if(!(Test-Path -LiteralPath $proof -PathType Leaf)){throw 'Java compiler output verifier missing from canonical recipe'}
& python $proof --source $SourceRoot --current $sha --require
if($LASTEXITCODE-ne0){throw 'Java compiler output differs from signed original input proof'}
$paths=[Collections.Generic.List[string]]::new()
foreach($leaf in @('dist/InputHost.dex','dist/InputHost.verified.json','client/Launcher.exe','client/Launcher.build.json','release/launcher-lane-v1.json','release/runtime-lane-v1.json','release/delivery-provenance-v1.json')){$paths.Add('Distribution/'+$leaf)}
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
