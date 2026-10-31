[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedRepository
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS-ne'true'-or$env:GITHUB_REPOSITORY-ne'pvtkyron/pantry-core'-or$env:GITHUB_REF-ne'refs/heads/main'){throw 'Frozen delivery restore requires canonical hosted execution'}
$SourceRoot=(Resolve-Path -LiteralPath $SourceRoot).Path
if($ExpectedRepository-notmatch'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'){throw 'Frozen delivery repository rejected'}
$origin=(& git -C $SourceRoot remote get-url origin).Trim()
if($LASTEXITCODE-or$origin-notmatch('^https://github\.com/'+[regex]::Escape($ExpectedRepository)+'(?:\.git)?$')){throw 'Frozen delivery origin rejected'}
$head=(& git -C $SourceRoot rev-parse HEAD).Trim()
if($LASTEXITCODE-or$head-notmatch'^[0-9a-f]{40}$'){throw 'Frozen delivery source pin unavailable'}
$manifest=Get-Content -LiteralPath (Join-Path $SourceRoot 'etc/security/signing/frozen-bootstrap.json') -Raw|ConvertFrom-Json
$deliveryCommit=([string]$manifest.delivery_commit).Trim()
if($deliveryCommit-cnotmatch'^[0-9a-f]{40}$'){throw 'Frozen delivery object pin unavailable'}
$paths=@('Distribution/client/Bootstrap.exe','Distribution/client/Bootstrap.release.json','Distribution/release/bootstrap-delivery-v1.json')
$stage=Join-Path $env:RUNNER_TEMP ('frozen-bootstrap-'+[Guid]::NewGuid().ToString('N'))
$archive=$stage+'.zip'
try{
    & git -C $SourceRoot fetch --quiet --filter=blob:none --no-tags --depth=1 origin $deliveryCommit
    if($LASTEXITCODE){throw 'Pinned frozen delivery fetch failed'}
    $entries=@(& git -C $SourceRoot ls-tree -r $deliveryCommit -- @paths)
    if($LASTEXITCODE-or$entries.Count-ne3-or@($entries|Where-Object{$_-notmatch'^100644 blob [0-9a-f]{40}\s+Distribution/'}).Count){throw 'Frozen delivery contains unsupported Git objects'}
    & git -C $SourceRoot archive --format=zip --output=$archive $deliveryCommit -- @paths
    if($LASTEXITCODE){throw 'Pinned frozen delivery archive failed'}
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try{
        foreach($entry in $zip.Entries){
            if($entry.FullName.EndsWith('/')){if($entry.FullName-notin@('Distribution/','Distribution/client/','Distribution/release/')){throw 'Unexpected frozen delivery directory'};continue}
            if($entry.FullName-notin$paths){throw 'Unexpected frozen delivery entry'}
            $limit=if($entry.FullName.EndsWith('.exe')){[int64]$manifest.signed_size}else{131072}
            if($entry.Length-le0-or$entry.Length-gt$limit){throw 'Frozen delivery size rejected'}
        }
    }finally{$zip.Dispose()}
    Expand-Archive -LiteralPath $archive -DestinationPath $stage
    # The existing gate checks the original frozen hash, certificate, signature,
    # source provenance, Bootstrap anchors and signer identity before staging.
    & (Join-Path $SourceRoot 'etc/publishing/Assert-FrozenBootstrap.ps1') -PantryPath (Join-Path $stage 'Distribution')
    if(!$?){throw 'Pinned frozen delivery verification failed'}
    foreach($relative in $paths){
        $inputFile=Join-Path $stage $relative
        $outputFile=Join-Path $SourceRoot $relative
        if(Test-Path -LiteralPath $outputFile){
            $item=Get-Item -LiteralPath $outputFile
            if($item.Attributes-band[IO.FileAttributes]::ReparsePoint-or$item.PSIsContainer){throw 'Existing frozen delivery path is redirected'}
            if((Get-FileHash -LiteralPath $outputFile).Hash-cne(Get-FileHash -LiteralPath $inputFile).Hash){throw 'Existing frozen delivery differs from its pinned object'}
            continue
        }
        $parent=Split-Path -Parent $outputFile
        New-Item -ItemType Directory -Force -Path $parent|Out-Null
        Copy-Item -LiteralPath $inputFile -Destination $outputFile
    }
    $after=(& git -C $SourceRoot rev-parse HEAD).Trim()
    if($LASTEXITCODE-or$after-cne$head){throw 'Frozen delivery restore moved the source checkout'}
    & (Join-Path $SourceRoot 'etc/publishing/Assert-FrozenBootstrap.ps1') -PantryPath (Join-Path $SourceRoot 'Distribution')
    if(!$?){throw 'Staged frozen delivery verification failed'}
    Write-Host '[HOSTED/FROZEN][OK] original signed delivery restored; source and trust pins preserved'
}finally{
    if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive -Force}
    if(Test-Path -LiteralPath $stage){Remove-Item -LiteralPath $stage -Recurse -Force}
}
