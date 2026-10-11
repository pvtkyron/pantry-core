$ErrorActionPreference='Stop'
$script:Utf8=New-Object Text.UTF8Encoding($false)
function Emit([string]$Line){[IO.File]::AppendAllText($env:GITHUB_OUTPUT,$Line+[Environment]::NewLine,$script:Utf8)}
function FixedTimeEqual([byte[]]$A,[byte[]]$B){if($null-eq$A-or$null-eq$B-or$A.Length-ne$B.Length){return $false};[int]$diff=0;for($i=0;$i-lt$A.Length;$i++){$diff=$diff-bor(([int]$A[$i])-bxor([int]$B[$i]))};return $diff-eq0}
function Bytes([string]$Text){return [Text.Encoding]::UTF8.GetBytes($Text)}
function Sha([byte[]]$Data){$s=[Security.Cryptography.SHA256]::Create();try{return $s.ComputeHash($Data)}finally{$s.Dispose()}}
function Derive([byte[]]$Master,[string]$Label){$h=(New-Object Security.Cryptography.HMACSHA256(,$Master));try{return $h.ComputeHash((Bytes $Label))}finally{$h.Dispose()}}
function Copy2([byte[]]$A,[byte[]]$B){
  $o=New-Object byte[] ($A.Length+$B.Length)
  [Array]::Copy($A,0,$o,0,$A.Length);[Array]::Copy($B,0,$o,$A.Length,$B.Length)
  return $o
}
function Keys(){
  if([string]::IsNullOrWhiteSpace($env:CAPSULE_KEY)){throw 'private capsule key unavailable'}
  $master=Sha (Bytes ("kyron-private-capsule-v1`n"+$env:CAPSULE_KEY))
  return ,@((Derive $master 'enc'),(Derive $master 'mac'))
}
function Seal([string]$Payload){
  if([string]::IsNullOrWhiteSpace($Payload)){throw 'private capsule payload unavailable'}
  $keys=Keys;$aes=[Security.Cryptography.Aes]::Create()
  try{
    $aes.Key=$keys[0];$aes.Mode=[Security.Cryptography.CipherMode]::CBC;$aes.Padding=[Security.Cryptography.PaddingMode]::PKCS7;$aes.GenerateIV()
    $plain=Bytes $Payload;$enc=$aes.CreateEncryptor()
    try{$cipher=$enc.TransformFinalBlock($plain,0,$plain.Length)}finally{$enc.Dispose()}
    $body=Copy2 $aes.IV $cipher;$h=(New-Object Security.Cryptography.HMACSHA256(,$keys[1]))
    try{$mac=$h.ComputeHash($body)}finally{$h.Dispose()}
    return [Convert]::ToBase64String((Copy2 $aes.IV (Copy2 $mac $cipher)))
  }finally{$aes.Dispose()}
}
function Open([string]$Capsule){
  if([string]::IsNullOrWhiteSpace($Capsule)){throw 'private capsule unavailable'}
  try{$raw=[Convert]::FromBase64String($Capsule)}catch{throw 'private capsule encoding rejected'}
  if($raw.Length-lt65){throw 'private capsule length rejected'}
  [byte[]]$iv=$raw[0..15];[byte[]]$mac=$raw[16..47];[byte[]]$cipher=$raw[48..($raw.Length-1)]
  $keys=Keys;$body=Copy2 $iv $cipher;$h=(New-Object Security.Cryptography.HMACSHA256(,$keys[1]))
  try{$actual=$h.ComputeHash($body)}finally{$h.Dispose()}
  if(!(FixedTimeEqual $mac $actual)){throw 'private capsule authentication rejected'}
  $aes=[Security.Cryptography.Aes]::Create()
  try{
    $aes.Key=$keys[0];$aes.IV=$iv;$aes.Mode=[Security.Cryptography.CipherMode]::CBC;$aes.Padding=[Security.Cryptography.PaddingMode]::PKCS7
    $dec=$aes.CreateDecryptor()
    try{$plain=$dec.TransformFinalBlock($cipher,0,$cipher.Length)}finally{$dec.Dispose()}
  }catch{throw 'private capsule decryption rejected'}finally{$aes.Dispose()}
  try{return ([Text.Encoding]::UTF8.GetString($plain)|ConvertFrom-Json)}catch{throw 'private capsule payload rejected'}
}
function CheckState($State){
  if([int]$State.schema-ne1){throw 'private capsule schema rejected'}
  foreach($name in @('workspace','pantry','sdk','web')){
    $node=$State.$name
    if($null-eq$node-or([string]$node.repo)-notmatch'^[^/\s]+/[^/\s]+$'-or([string]$node.ref)-notmatch'^[0-9a-f]{40}$'){throw 'private capsule state rejected'}
  }
}
$mode=($env:CAPSULE_MODE+'').Trim().ToLowerInvariant()
if($mode-eq'seal'){
  try{$initial=$env:CAPSULE_PAYLOAD|ConvertFrom-Json}catch{throw 'private capsule payload rejected'}
  CheckState $initial
  $sealed=Seal $env:CAPSULE_PAYLOAD
  Emit ("capsule="+$sealed)
  Write-Host '[CAPSULE][SEALED]'
  exit 0
}
$state=Open $env:CAPSULE_VALUE;CheckState $state
if($mode-eq'advance'){
  $next=($env:CAPSULE_PANTRY_REF+'').Trim().ToLowerInvariant()
  if($next-notmatch'^[0-9a-f]{40}$'){throw 'private delivery ref rejected'}
  Write-Host "::add-mask::$next"
  $state.pantry.ref=$next
  $payload=$state|ConvertTo-Json -Compress -Depth 5
  Write-Host "::add-mask::$payload"
  Emit ("capsule="+(Seal $payload))
  Write-Host '[CAPSULE][ADVANCED]'
  exit 0
}
if($mode-ne'open'){throw 'private capsule mode rejected'}
foreach($name in @('workspace','pantry','sdk','web')){
  Write-Host "::add-mask::$([string]$state.$name.repo)"
  Write-Host "::add-mask::$([string]$state.$name.ref)"
}
$project=($env:CAPSULE_PROJECT+'').Trim().ToLowerInvariant()
if($project-notin@('workspace','sdk','web')){throw 'private capsule project rejected'}
Emit ("repo="+[string]$state.$project.repo)
Emit ("ref="+[string]$state.$project.ref)
foreach($name in @('workspace','pantry','sdk','web')){
  Emit (($name+'_repo=')+[string]$state.$name.repo)
  Emit (($name+'_ref=')+[string]$state.$name.ref)
}
Write-Host '[CAPSULE][OPENED]'
