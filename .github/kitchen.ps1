[CmdletBinding(PositionalBinding=$false)]
param(
    [ValidateSet('Tray','Oven')][string]$Mode='Tray',
    [long]$Batch=0,
    [int]$Try=1,
    [switch]$Fresh
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop';$env:GIT_TERMINAL_PROMPT='0'
$Shelf=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Bench=Split-Path -Parent $Shelf;$Mix=Join-Path $Bench 'mix';$Fill=Join-Path $Bench 'filling'
function Need([string]$Name){$v=[Environment]::GetEnvironmentVariable($Name);if([string]::IsNullOrWhiteSpace($v)){throw 'ingredient unavailable'};return $v.Trim()}
function Header([string]$Key,[string]$User='x-access-token'){$b=[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:$Key"));return "AUTHORIZATION: basic $b"}
function Lock([string]$Root,[string]$Key,[string]$User='x-access-token'){& git -C $Root config http.https://github.com/.extraheader (Header $Key $User);if($LASTEXITCODE){throw 'batch rejected'}}
function Pull([string]$Name,[string]$Slug,[string]$Key){
    $u="https://github.com/$Slug.git";$dst=Join-Path $Bench $Name;$owner=($Slug-split'/',2)[0];$users=@('x-access-token',$owner)|Select-Object -Unique;$last=''
    foreach($user in $users){
        $h=Header $Key $user;$err=Join-Path ([IO.Path]::GetTempPath()) ('crumb-'+[Guid]::NewGuid().ToString('N')+'.txt')
        try{& git -c "http.https://github.com/.extraheader=$h" clone --quiet --branch main $u $dst 1>$null 2>$err;$code=$LASTEXITCODE;$last=if(Test-Path $err){Get-Content -LiteralPath $err -Raw}else{''}}
        finally{Remove-Item -LiteralPath $err -Force -ErrorAction SilentlyContinue}
        if($code-eq0){Lock $dst $Key $user;return}
        Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue
    }
    if($last-match'(?i)(authentication|permission denied|403|401|could not read username)'){$script:Station+='-key'}
    elseif($last-match'(?i)(repository not found|not found)'){$script:Station+='-missing'}
    elseif($last-match'(?i)(failed to connect|could not resolve|timed out|timeout)'){$script:Station+='-net'}else{$script:Station+='-pull'}
    throw 'batch rejected'
}
$Station='counter'
try{
    $Station='shelf';Lock $Shelf (Need 'SHELF_KEY')
    $Station='flour';Pull 'mix' (Need 'MIX') (Need 'MIX_KEY')
    $Station='cream';Pull 'filling' (Need 'FILL') (Need 'FILL_KEY')
    $bake=Join-Path (Join-Path $Mix 'Tools') 'Bake.ps1'
    if($Mode-eq'Tray'){
        & $bake -Fill $Fill -Shelf $Shelf -Peek
        exit $LASTEXITCODE
    }
    $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $a=@('-Fill',$Fill,'-Shelf',$Shelf,'-Batch',[string]$Batch,'-Try',[string]$Try)
    if($Fresh){$a+='-Fresh'}
    & $ps -NoLogo -NoProfile -ExecutionPolicy Bypass -File $bake @a
    exit $LASTEXITCODE
}catch{
    Write-Host ('[Patisserie] batch=rejected station='+$Station)
    exit 1
}
