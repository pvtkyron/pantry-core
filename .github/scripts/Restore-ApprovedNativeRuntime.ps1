[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedRepository,
    [switch]$CheckOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS-ne'true'-or$env:GITHUB_REPOSITORY-ne'pvtkyron/pantry-core'-or$env:GITHUB_REF-ne'refs/heads/main'){throw 'Approved runtime restore requires canonical hosted execution'}
$SourceRoot=(Resolve-Path -LiteralPath $SourceRoot).Path
if($ExpectedRepository-notmatch'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'){throw 'Approved runtime repository rejected'}
$origin=(& git -C $SourceRoot remote get-url origin).Trim()
if($LASTEXITCODE-or$origin-notmatch('^https://github\.com/'+[regex]::Escape($ExpectedRepository)+'(?:\.git)?$')){throw 'Approved runtime origin rejected'}
$head=(& git -C $SourceRoot rev-parse HEAD).Trim()
if($LASTEXITCODE-or$head-cnotmatch'^[0-9a-f]{40}$'){throw 'Approved runtime source identity unavailable'}
$contract=[IO.File]::ReadAllText((Join-Path $SourceRoot 'Distribution/SrcVersion.ini'))
$digests=@{}
foreach($bits in @('32','64')){
    foreach($channel in @('release','insider')){
        $key=$channel+'_lib_sha256_'+$bits
        $rows=[regex]::Matches($contract,'(?m)^'+$key+'=([0-9a-f]{64})\s*$')
        if($rows.Count-ne1){throw 'Approved runtime contract pin missing or ambiguous'}
        $digest=$rows[0].Groups[1].Value
        if($digests.ContainsKey($bits)-and$digests[$bits]-cne$digest){throw 'Separate approved Release/Insider pairs require a dedicated delivery'}
        $digests[$bits]=$digest
    }
}
$checkoutHeaders=@(& git -C $SourceRoot config --includes --get-all http.https://github.com/.extraheader)
if($LASTEXITCODE-or$checkoutHeaders.Count-ne1){throw 'Authenticated runtime checkout header unavailable'}
$authorizationMatch=[regex]::Match([string]$checkoutHeaders[0],'(?i)^AUTHORIZATION:\s*(?<value>basic [A-Za-z0-9+/=]+)$')
if(!$authorizationMatch.Success){throw 'Authenticated runtime checkout header rejected'}
$authorization=$authorizationMatch.Groups['value'].Value
Write-Host "::add-mask::$authorization"
$headers=@{Authorization=$authorization;Accept='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
$base='https://api.github.com/repos/'+$ExpectedRepository
$response=Invoke-RestMethod -Uri ($base+'/releases?per_page=100') -Headers $headers
if($response -isnot [array]){throw 'Approved runtime release catalog must be a JSON array'}
$releases=@($response.GetEnumerator())
$names=@('runtime-lane-v1.json')
foreach($abi in @('armeabi-v7a','arm64-v8a')){
    $names+=@(('libkyron-{0}.so' -f $abi),('libkyron-{0}.release.json' -f $abi),('libkyron-{0}.so.kyron-finalized' -f $abi))
}
if($names.Count-ne7-or@($names|Select-Object -Unique).Count-ne7){throw 'Approved runtime asset name contract is invalid'}
$candidates=@($releases|Where-Object{
    $assets=@($_.assets)
    $complete=$true
    foreach($name in $names){if(@($assets|Where-Object name -CEQ $name).Count-ne1){$complete=$false}}
    $a32=@($assets|Where-Object name -CEQ 'libkyron-armeabi-v7a.so')
    $a64=@($assets|Where-Object name -CEQ 'libkyron-arm64-v8a.so')
    $complete-and$a32.Count-eq1-and$a64.Count-eq1-and$a32[0].digest-ceq('sha256:'+$digests['32'])-and$a64[0].digest-ceq('sha256:'+$digests['64'])
}|Sort-Object created_at -Descending)
if(!$candidates.Count){
    if($env:GITHUB_OUTPUT){'pending=true' >> $env:GITHUB_OUTPUT}
    Write-Host '[HOSTED/RUNTIME][WAIT] approved native delivery is not available yet; publication remains skipped'
    return
}
$release=$candidates[0]
$target=([string]$release.target_commitish).Trim()
if($target-cnotmatch'^[0-9a-f]{40}$'){throw 'Approved runtime release target must be an immutable source commit'}
# Approval of old hashes never approves changed compiler inputs. This gate is
# shared by CheckOnly admission and the actual restore, including manual Full.
$gitApplication=(Get-Command git -CommandType Application -ErrorAction Stop|Select-Object -First 1).Source
& $gitApplication -C $SourceRoot fetch --quiet --filter=blob:none --no-tags origin $target
if($LASTEXITCODE){throw 'Approved native input source fetch failed'}
$shallow=(& $gitApplication -C $SourceRoot rev-parse --is-shallow-repository).Trim()
if($LASTEXITCODE){throw 'Approved native input history inspection failed'}
if($shallow-eq'true'){
    & $gitApplication -C $SourceRoot fetch --quiet --filter=blob:none --no-tags --unshallow origin main
    if($LASTEXITCODE){throw 'Approved native input history materialization failed'}
}
& $gitApplication -C $SourceRoot merge-base --is-ancestor $target $head
$ancestryCode=$LASTEXITCODE
if($ancestryCode-gt1){throw 'Approved native input ancestry inspection failed'}
. (Join-Path $SourceRoot 'etc/build/workspace-common.ps1')
$nativeSpecs=@(Get-WorkspaceNativeReleasePathspecs)
if(!$nativeSpecs.Count){throw 'Canonical Native input scope missing'}
& $gitApplication -C $SourceRoot diff --quiet --no-renames $target $head -- @nativeSpecs
$inputCode=$LASTEXITCODE
if($inputCode-gt1){throw 'Approved native compiler input comparison failed'}
if($ancestryCode-ne0-or$inputCode-ne0){
    if($env:GITHUB_OUTPUT){'pending=true' >> $env:GITHUB_OUTPUT}
    Write-Host '[HOSTED/RUNTIME][WAIT] Native inputs changed after the approved delivery; build one signed candidate, then await explicit approval'
    $global:LASTEXITCODE=0
    return
}
if($env:GITHUB_OUTPUT){'pending=false' >> $env:GITHUB_OUTPUT}
if($CheckOnly){Write-Host '[HOSTED/RUNTIME][READY] approved Native bytes and unchanged canonical source inputs available';return}
$stage=Join-Path $env:RUNNER_TEMP ('approved-runtime-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($stage)
$priorSigner=$env:KYRON_CANONICAL_SIGNER_META
try{
    $downloadHeaders=@{Authorization=$authorization;Accept='application/octet-stream';'X-GitHub-Api-Version'='2022-11-28'}
    foreach($name in $names){
        $asset=@($release.assets|Where-Object name -CEQ $name)[0]
        $limit=if($name.EndsWith('.so')){16777216}else{131072}
        if($asset.state-cne'uploaded'-or[int64]$asset.size-le0-or[int64]$asset.size-gt$limit-or$asset.digest-cnotmatch'^sha256:[0-9a-f]{64}$'){throw 'Approved runtime asset metadata rejected'}
        $path=Join-Path $stage $name
        Invoke-WebRequest -Uri ($base+'/releases/assets/'+$asset.id) -Headers $downloadHeaders -OutFile $path
        $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if((Get-Item -LiteralPath $path).Length-ne[int64]$asset.size-or('sha256:'+$actual)-cne$asset.digest){throw 'Approved runtime download digest mismatch'}
    }
    $lane=Get-Content -LiteralPath (Join-Path $stage 'runtime-lane-v1.json') -Raw|ConvertFrom-Json
    if($lane.schema-ne1-or$lane.mode-cne'all'){throw 'Approved runtime receipt schema/mode rejected'}
    $nativeSource=([string]$lane.source_workspace_sha).Trim()
    if($nativeSource-cnotmatch'^[0-9a-f]{40}$'-or$lane.workspace_sha-cne$nativeSource){throw 'Approved runtime original source receipt rejected'}
    foreach($ref in @($target,$nativeSource)){
        Write-Host "::add-mask::$ref"
        & git -C $SourceRoot fetch --quiet --filter=blob:none --no-tags --depth=1 origin $ref
        if($LASTEXITCODE){throw 'Approved runtime source fetch failed'}
    }
    # Restore full ancestry for proof without moving the pinned checkout.
    $shallow=(& git -C $SourceRoot rev-parse --is-shallow-repository).Trim()
    if($LASTEXITCODE){throw 'Approved runtime history inspection failed'}
    if($shallow-eq'true'){
        & git -C $SourceRoot fetch --quiet --filter=blob:none --no-tags --unshallow origin main
        if($LASTEXITCODE){throw 'Approved runtime ancestry materialization failed'}
    }
    & git -C $SourceRoot merge-base --is-ancestor $nativeSource $target
    if($LASTEXITCODE){throw 'Approved runtime source is not an ancestor of its delivery'}
    & git -C $SourceRoot merge-base --is-ancestor $target $head
    if($LASTEXITCODE){throw 'Approved runtime delivery is not an ancestor of pinned source'}
    $properties=@($lane.runtime.PSObject.Properties)
    if($properties.Count-ne4){throw 'Approved runtime lane must contain exactly four channel aliases'}
    foreach($abi in @('armeabi-v7a','arm64-v8a')){
        $bits=if($abi-ceq'armeabi-v7a'){'32'}else{'64'}
        $digest=$digests[$bits]
        $expectedAliases=if($bits-ceq'32'){@('libkyron-','libkyroni-')}else{@('libkyron64-','libkyroni64-')}
        foreach($prefix in $expectedAliases){
            $alias=$prefix+$digest.Substring(0,24)+'.so'
            $property=$lane.runtime.PSObject.Properties[$alias]
            if(!$property-or$property.Value.abi-cne$abi-or$property.Value.sha256-cne$digest){throw 'Approved runtime alias provenance mismatch'}
        }
        $dir=Join-Path $stage $abi
        [void][IO.Directory]::CreateDirectory($dir)
        foreach($leaf in @('libkyron.so','libkyron.release.json','libkyron.so.kyron-finalized')){
            $name=$leaf.Replace('libkyron','libkyron-'+$abi)
            Move-Item -LiteralPath (Join-Path $stage $name) -Destination (Join-Path $dir $leaf)
        }
    }
    $hostPath=Join-Path $SourceRoot 'VeraInternal/lib/host/AndroidReleaseHost.exe'
    if(!(Test-Path -LiteralPath $hostPath -PathType Leaf)){
        & (Join-Path $SourceRoot 'VeraInternal/jni/Tools/BuildAndroidHostTools.cmd')
        if($LASTEXITCODE){throw 'Approved runtime verifier build failed'}
    }
    $env:KYRON_CANONICAL_SIGNER_META=Join-Path $SourceRoot 'etc/security/signing/canonical-signer.json'
    & $hostPath verify --root $stage --abis 'armeabi-v7a,arm64-v8a' --require-finalized
    if($LASTEXITCODE){throw 'Approved runtime RSA/finalizer verification failed'}
    # The unchanged dual-ABI release still needs the legacy runtime marker.
    # Reconstruct only its deterministic metadata from the RSA-verified pair,
    # never substitute a new ELF, receipt, signature, or source identity.
    if($lane.lib_policy-cne'current-release'-or$lane.source_workspace_sha-cne$nativeSource){
        throw 'Approved native marker must preserve signed source identity and current-release policy'
    }
    $marker=@('KYRON_PRIMARY_RUNTIME_V10=1','source=pubgm-release','mode=all','lib_policy=current-release',("workspace_sha="+$nativeSource))
    $aliasRows=@(
        @('libkyron-',  '32','armeabi-v7a','release_channel'),
        @('libkyron64-','64','arm64-v8a', 'release_channel'),
        @('libkyroni-', '32','armeabi-v7a','insider_channel'),
        @('libkyroni64-','64','arm64-v8a', 'insider_channel')
    )
    foreach($row in $aliasRows){
        $digest=$digests[$row[1]]
        $alias=$row[0]+$digest.Substring(0,24)+'.so'
        $item=$lane.runtime.PSObject.Properties[$alias]
        $channel=[string]$lane.contract.($row[3])
        if(!$item-or$item.Value.abi-cne$row[2]-or$item.Value.channel-cne$channel-or$item.Value.sha256-cne$digest-or!$channel){
            throw 'Approved native marker provenance/ABI/channel validation failed'
        }
        $marker+=("$alias=$digest;abi=$($row[2]);channel=$channel")
    }
    $markerPath=Join-Path $stage 'primary-runtime-v10.marker'
    [IO.File]::WriteAllLines($markerPath,[string[]]$marker,[Text.Encoding]::ASCII)
    $copies=[Collections.Generic.List[object]]::new()
    $copies.Add(@($markerPath,'Distribution/release/primary-runtime-v10.marker'))
    $copies.Add(@((Join-Path $stage 'runtime-lane-v1.json'),'Distribution/release/runtime-lane-v1.json'))
    foreach($abi in @('armeabi-v7a','arm64-v8a')){
        $logical=if($abi-ceq'armeabi-v7a'){@('libkyron.so','libkyroni.so')}else{@('libkyron64.so','libkyroni64.so')}
        $binary=Join-Path (Join-Path $stage $abi) 'libkyron.so'
        foreach($leaf in $logical){$copies.Add(@($binary,('Distribution/lib/'+$leaf)))}
        foreach($leaf in @('libkyron.release.json','libkyron.so.kyron-finalized')){$copies.Add(@((Join-Path (Join-Path $stage $abi) $leaf),('Distribution/release/native-attestations/'+$abi+'/'+$leaf)))}
    }
    foreach($row in $copies){
        $destination=Join-Path $SourceRoot $row[1]
        & git -C $SourceRoot check-ignore --quiet -- $row[1]
        if($LASTEXITCODE){throw 'Approved runtime restore target must be an ignored generated file'}
        if(Test-Path -LiteralPath $destination){
            if((Get-FileHash -LiteralPath $destination).Hash-cne(Get-FileHash -LiteralPath $row[0]).Hash){throw 'Approved runtime destination already contains different data'}
        }else{
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination))
            Copy-Item -LiteralPath $row[0] -Destination $destination
        }
    }
    if((& git -C $SourceRoot rev-parse HEAD).Trim()-cne$head){throw 'Pinned source moved during approved runtime restore'}
    Write-Host '[HOSTED/RUNTIME][OK] approved native pair restored; original source receipt and RSA finalizers verified'
}finally{
    $env:KYRON_CANONICAL_SIGNER_META=$priorSigner
    if(Test-Path -LiteralPath $stage){Remove-Item -LiteralPath $stage -Recurse -Force}
}
