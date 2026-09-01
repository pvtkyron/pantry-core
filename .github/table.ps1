[CmdletBinding()]
param([switch]$Shelf)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$env:GIT_TERMINAL_PROMPT='0'
function Need([string]$Name){
    $v=[Environment]::GetEnvironmentVariable($Name)
    if([string]::IsNullOrWhiteSpace($v)){throw 'ingredient unavailable'}
    return $v.Trim()
}
function Mask([string]$Value){if($Value){Write-Host "::add-mask::$Value"}}
function Lock([string]$Dir,[string]$Key){
    $raw=[Text.Encoding]::ASCII.GetBytes("x-access-token:$Key")
    $h='AUTHORIZATION: basic '+[Convert]::ToBase64String($raw)
    & git -C $Dir config http.https://github.com/.extraheader $h 1>$null 2>$null
    if($LASTEXITCODE-ne0){throw 'counter rejected'}
}
function Pull([string]$Slug,[string]$Dir,[string]$Key){
    Mask $Slug;$old=$env:GH_TOKEN;$env:GH_TOKEN=$Key
    try{& gh repo clone $Slug $Dir -- --quiet --depth=1 1>$null 2>$null;if($LASTEXITCODE-ne0){throw 'counter rejected'}}
    finally{$env:GH_TOKEN=$old}
    Lock $Dir $Key
}
$mix=Need 'MIX';$fill=Need 'FILL';$mixKey=Need 'MIX_KEY';$fillKey=Need 'FILL_KEY'
if($Shelf){
    $repo=Need 'SHELF';$key=Need 'SHELF_KEY';Pull $repo 'shelf' $key
}
Pull $mix 'mix' $mixKey
Pull $fill 'filling' $fillKey
Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
Write-Host '[Patisserie] table=ready'
