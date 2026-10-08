[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('pack','unpack')][string]$Mode,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Lane,
    [Parameter(Mandatory=$true)][string]$PantryRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$WorkspaceSha,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$PantrySha,
    [Parameter(Mandatory=$true)][string]$Secret,
    [string]$SourceRoot='',
    [string[]]$Paths=@(),
    [string]$OutputRoot='',
    [string]$InputPath='',
    [string]$Python=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$WorkspaceSha=$WorkspaceSha.ToLowerInvariant();$PantrySha=$PantrySha.ToLowerInvariant()
if([string]::IsNullOrWhiteSpace($Secret)){throw 'Workspace handoff key is unavailable.'}
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Utf8([string]$s){[Text.Encoding]::UTF8.GetBytes($s)}
function Derive([string]$s){$sha=[Security.Cryptography.SHA512]::Create();try{return $sha.ComputeHash((Utf8 ("kyron-ci-handoff-v1`0"+$s)))}finally{$sha.Dispose()}}
function FixedEq([byte[]]$a,[byte[]]$b){if($a.Length-ne$b.Length){return $false};$d=0;for($i=0;$i-lt$a.Length;$i++){$d=$d-bor($a[$i]-bxor$b[$i])};return $d-eq0}
function Append-Output([string]$name,[string]$value){if($env:GITHUB_OUTPUT){[IO.File]::AppendAllText($env:GITHUB_OUTPUT,"$name=$value`n",[Text.UTF8Encoding]::new($false))}}
function Resolve-Python {
    if($Python-and(Test-Path -LiteralPath $Python -PathType Leaf)){return [IO.Path]::GetFullPath($Python)}
    foreach($name in @('python.exe','python')){$cmd=Get-Command $name -ErrorAction SilentlyContinue|Select-Object -First 1;if($cmd){return $cmd.Source}}
    throw 'Python is unavailable for canonical Pantry opaque routing.'
}
function Opaque-Route([string]$logical){
    $module=Join-Path $PantryRoot 'tools\opaque_paths.py';if(!(Test-Path -LiteralPath $module -PathType Leaf)){throw "Pantry opaque route owner missing: $module"}
    $code="import importlib.util,sys; s=importlib.util.spec_from_file_location('kyron_opaque',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.opaque_path(sys.argv[2]))"
    $route=(& (Resolve-Python) -c $code $module $logical|Select-Object -Last 1).Trim();if($LASTEXITCODE-ne0-or$route-notmatch'^kyron/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{28}\.bin$'){throw "Canonical Pantry opaque route rejected: $route"};return $route
}
function Protect-Bytes([byte[]]$plain){
    $material=Derive $Secret;[byte[]]$encKey=$material[0..31];[byte[]]$macKey=$material[32..63]
    $aes=[Security.Cryptography.Aes]::Create();$aes.KeySize=256;$aes.Mode=[Security.Cryptography.CipherMode]::CBC;$aes.Padding=[Security.Cryptography.PaddingMode]::PKCS7;$aes.Key=$encKey;$aes.GenerateIV()
    try{$e=$aes.CreateEncryptor();try{$cipher=$e.TransformFinalBlock($plain,0,$plain.Length)}finally{$e.Dispose()};$header=[Text.Encoding]::ASCII.GetBytes('KYRONCI1');$body=New-Object byte[] ($header.Length+$aes.IV.Length+$cipher.Length);[Array]::Copy($header,0,$body,0,$header.Length);[Array]::Copy($aes.IV,0,$body,$header.Length,$aes.IV.Length);[Array]::Copy($cipher,0,$body,$header.Length+$aes.IV.Length,$cipher.Length);$h=[Security.Cryptography.HMACSHA256]::new($macKey);try{$mac=$h.ComputeHash($body)}finally{$h.Dispose()};$out=New-Object byte[] ($body.Length+$mac.Length);[Array]::Copy($body,0,$out,0,$body.Length);[Array]::Copy($mac,0,$out,$body.Length,$mac.Length);return $out}finally{$aes.Dispose();[Array]::Clear($material,0,$material.Length);[Array]::Clear($encKey,0,$encKey.Length);[Array]::Clear($macKey,0,$macKey.Length)}
}
function Unprotect-Bytes([byte[]]$blob){
    if($blob.Length-lt72){throw 'Encrypted Workspace handoff is truncated.'};$header=[Text.Encoding]::ASCII.GetString($blob,0,8);if($header-ne'KYRONCI1'){throw 'Encrypted Workspace handoff magic mismatch.'}
    $bodyLen=$blob.Length-32;[byte[]]$body=$blob[0..($bodyLen-1)];[byte[]]$actual=$blob[$bodyLen..($blob.Length-1)];$material=Derive $Secret;[byte[]]$encKey=$material[0..31];[byte[]]$macKey=$material[32..63]
    $h=[Security.Cryptography.HMACSHA256]::new($macKey);try{$expected=$h.ComputeHash($body)}finally{$h.Dispose()};if(!(FixedEq $actual $expected)){throw 'Encrypted Workspace handoff MAC mismatch.'}
    [byte[]]$iv=$body[8..23];[byte[]]$cipher=$body[24..($body.Length-1)];$aes=[Security.Cryptography.Aes]::Create();$aes.KeySize=256;$aes.Mode=[Security.Cryptography.CipherMode]::CBC;$aes.Padding=[Security.Cryptography.PaddingMode]::PKCS7;$aes.Key=$encKey;$aes.IV=$iv
    try{$d=$aes.CreateDecryptor();try{return $d.TransformFinalBlock($cipher,0,$cipher.Length)}finally{$d.Dispose()}}finally{$aes.Dispose();[Array]::Clear($material,0,$material.Length);[Array]::Clear($encKey,0,$encKey.Length);[Array]::Clear($macKey,0,$macKey.Length)}
}
if($Mode-eq'pack'){
    if([string]::IsNullOrWhiteSpace($SourceRoot)-or[string]::IsNullOrWhiteSpace($OutputRoot)){throw 'Pack mode requires SourceRoot and OutputRoot.'};$SourceRoot=[IO.Path]::GetFullPath($SourceRoot).TrimEnd('\');$OutputRoot=[IO.Path]::GetFullPath($OutputRoot)
    $work=Join-Path $env:RUNNER_TEMP ("kyron-handoff-$Lane-"+[Guid]::NewGuid().ToString('N'));$payload=Join-Path $work 'payload';New-Item -ItemType Directory -Force -Path (Join-Path $payload 'source'),$OutputRoot|Out-Null
    try{
        foreach($item in $Paths){$full=[IO.Path]::GetFullPath((Join-Path $SourceRoot $item));$prefix=$SourceRoot+'\';if(!$full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw "Handoff path escaped Workspace: $item"};if(!(Test-Path -LiteralPath $full)){throw "Handoff input missing: $item"};$rel=$full.Substring($prefix.Length);$dst=Join-Path (Join-Path $payload 'source') $rel;if(Test-Path -LiteralPath $full -PathType Container){New-Item -ItemType Directory -Force -Path $dst|Out-Null;Get-ChildItem -LiteralPath $full -Force|Copy-Item -Destination $dst -Recurse -Force}else{New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent)|Out-Null;Copy-Item -LiteralPath $full -Destination $dst -Force}}
        $files=@(Get-ChildItem -LiteralPath (Join-Path $payload 'source') -Recurse -File|Sort-Object FullName|ForEach-Object{$r=$_.FullName.Substring($payload.Length+1).Replace('\','/');[ordered]@{path=$r;size=[int64]$_.Length;sha256=Sha $_.FullName}})
        $manifest=[ordered]@{schema=1;lane=$Lane;workspace_sha=$WorkspaceSha;pantry_sha=$PantrySha;files=$files};[IO.File]::WriteAllText((Join-Path $payload 'handoff.json'),(($manifest|ConvertTo-Json -Depth 8 -Compress)+"`n"),[Text.UTF8Encoding]::new($false))
        $zip=Join-Path $work 'payload.zip';[IO.Compression.ZipFile]::CreateFromDirectory($payload,$zip,[IO.Compression.CompressionLevel]::Optimal,$false);$plain=[IO.File]::ReadAllBytes($zip);try{$sealed=Protect-Bytes $plain}finally{[Array]::Clear($plain,0,$plain.Length)}
        $logical="ci/workspace/$Lane/$WorkspaceSha/$PantrySha";$route=Opaque-Route $logical;$dest=Join-Path $OutputRoot $route.Replace('/','\');New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent)|Out-Null;[IO.File]::WriteAllBytes($dest,$sealed);[Array]::Clear($sealed,0,$sealed.Length)
        Append-Output 'root' $OutputRoot;Append-Output 'file' $dest;Append-Output 'route' $route;Append-Output 'sha256' (Sha $dest);Write-Host "[WORKSPACE/HANDOFF][PACK/OK] lane=$Lane route=$route files=$($files.Count)"
    }finally{Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue}
    return
}
if([string]::IsNullOrWhiteSpace($InputPath)-or[string]::IsNullOrWhiteSpace($OutputRoot)){throw 'Unpack mode requires InputPath and OutputRoot.'};$InputPath=[IO.Path]::GetFullPath($InputPath);$OutputRoot=[IO.Path]::GetFullPath($OutputRoot);if(!(Test-Path -LiteralPath $InputPath -PathType Leaf)){throw "Encrypted Workspace handoff missing: $InputPath"};New-Item -ItemType Directory -Force -Path $OutputRoot|Out-Null
$blob=[IO.File]::ReadAllBytes($InputPath);try{$plain=Unprotect-Bytes $blob}finally{[Array]::Clear($blob,0,$blob.Length)};$zip=Join-Path $env:RUNNER_TEMP ("kyron-handoff-open-"+[Guid]::NewGuid().ToString('N')+'.zip')
try{[IO.File]::WriteAllBytes($zip,$plain);[Array]::Clear($plain,0,$plain.Length);[IO.Compression.ZipFile]::ExtractToDirectory($zip,$OutputRoot);$manifestPath=Join-Path $OutputRoot 'handoff.json';if(!(Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'Workspace handoff manifest missing.'};$m=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json;if([int]$m.schema-ne1-or[string]$m.lane-ne$Lane-or([string]$m.workspace_sha).ToLowerInvariant()-ne$WorkspaceSha-or([string]$m.pantry_sha).ToLowerInvariant()-ne$PantrySha){throw 'Workspace handoff provenance mismatch.'};foreach($f in @($m.files)){$p=Join-Path $OutputRoot ([string]$f.path).Replace('/','\');if(!(Test-Path -LiteralPath $p -PathType Leaf)-or[int64](Get-Item -LiteralPath $p).Length-ne[int64]$f.size-or(Sha $p)-ne([string]$f.sha256).ToLowerInvariant()){throw "Workspace handoff file verification failed: $($f.path)"}};Append-Output 'manifest' $manifestPath;Write-Host "[WORKSPACE/HANDOFF][UNPACK/OK] lane=$Lane files=$(@($m.files).Count)"}finally{Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue}
