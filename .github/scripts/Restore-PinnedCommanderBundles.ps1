[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedRepository
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS-ne'true'-or$env:GITHUB_REPOSITORY-ne'pvtkyron/pantry-core'-or$env:GITHUB_REF-ne'refs/heads/main'){throw 'Pinned tool restore requires canonical hosted execution'}
$SourceRoot=(Resolve-Path -LiteralPath $SourceRoot).Path
if($ExpectedRepository-notmatch'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'){throw 'Pinned tool repository rejected'}
$origin=(& git -C $SourceRoot remote get-url origin).Trim()
if($LASTEXITCODE-or$origin-notmatch('^https://github\.com/'+[regex]::Escape($ExpectedRepository)+'(?:\.git)?$')){throw 'Pinned tool origin rejected'}
$head=(& git -C $SourceRoot rev-parse HEAD).Trim()
if($LASTEXITCODE-or$head-cnotmatch'^[0-9a-f]{40}$'){throw 'Pinned tool source identity unavailable'}
$lock=Get-Content -LiteralPath (Join-Path $SourceRoot 'etc/build/toolchains.lock.json') -Raw|ConvertFrom-Json
$objectPin=([string]$lock.commanders.delivery_commit).Trim()
if($objectPin-cnotmatch'^[0-9a-f]{40}$'){throw 'Pinned Commander object unavailable'}
$owner=Get-Content -LiteralPath (Join-Path $SourceRoot 'Launcher/jni/runtime/client/managed/KyronControl.Services/RuntimeToolBootstrapper.cs') -Raw
$pinRows=[regex]::Matches($owner,'new\s*\(\s*"client/tools/commanders/(?<name>[^"]+)"\s*,\s*"(?<sha>[0-9a-fA-F]{64})"\s*\)')
if($pinRows.Count-ne4){throw 'Canonical Commander pin set incomplete'}
$expected=@{};$paths=@()
foreach($row in $pinRows){
    $name=$row.Groups['name'].Value
    if($name-cnotmatch'^(?:desktop-commander|ai-commander)-[0-9]+\.[0-9]+\.[0-9]+\.part[12]$'-or$expected.ContainsKey($name)){throw 'Canonical Commander name rejected'}
    $expected[$name]=$row.Groups['sha'].Value.ToLowerInvariant()
    $paths+='Distribution/client/tools/commanders/'+$name
}
$stage=Join-Path $env:RUNNER_TEMP ('pinned-commanders-'+[Guid]::NewGuid().ToString('N'))
$archive=$stage+'.zip';$complete=$false
try{
    & git -C $SourceRoot fetch --quiet --filter=blob:none --no-tags --depth=1 origin $objectPin
    if($LASTEXITCODE){throw 'Pinned Commander object fetch failed'}
    $entries=@(& git -C $SourceRoot ls-tree -r $objectPin -- @paths)
    if($LASTEXITCODE-or$entries.Count-ne4-or@($entries|Where-Object{$_-notmatch'^100644 blob [0-9a-f]{40}\s+Distribution/client/tools/commanders/'}).Count){throw 'Pinned Commander object layout rejected'}
    & git -C $SourceRoot archive --format=zip --output=$archive $objectPin -- @paths
    if($LASTEXITCODE){throw 'Pinned Commander archive failed'}
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try{
        $fileCount=0
        foreach($entry in $zip.Entries){
            if($entry.FullName.EndsWith('/')){if($entry.FullName-notin@('Distribution/','Distribution/client/','Distribution/client/tools/','Distribution/client/tools/commanders/')){throw 'Unexpected Commander directory'};continue}
            if($entry.FullName-cnotin$paths-or$entry.Length-le0-or$entry.Length-gt104857600){throw 'Unexpected Commander archive entry'}
            $fileCount++
        }
        if($fileCount-ne4){throw 'Commander archive is incomplete'}
    }finally{$zip.Dispose()}
    Expand-Archive -LiteralPath $archive -DestinationPath $stage
    $bundleRoot=Join-Path $stage 'Distribution/client/tools/commanders'
    foreach($name in $expected.Keys){
        $path=Join-Path $bundleRoot $name
        if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()-cne$expected[$name]){throw 'Canonical Commander digest rejected'}
    }
    $after=(& git -C $SourceRoot rev-parse HEAD).Trim()
    if($LASTEXITCODE-or$after-cne$head){throw 'Pinned tool restore moved the source checkout'}
    $env:KYRON_COMMANDER_TOOL_ROOT=$bundleRoot
    [IO.File]::AppendAllText($env:GITHUB_ENV,"KYRON_COMMANDER_TOOL_ROOT=$bundleRoot"+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
    $complete=$true
    Write-Host '[HOSTED/COMMANDERS][OK] four immutable bundles match canonical runtime pins'
}finally{
    if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive -Force}
    if(!$complete-and(Test-Path -LiteralPath $stage)){Remove-Item -LiteralPath $stage -Recurse -Force}
}
