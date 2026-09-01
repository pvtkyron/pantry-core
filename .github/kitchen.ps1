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
function Need([string]$Name){$v=[Environment]::GetEnvironmentVariable($Name);if([string]::IsNullOrWhiteSpace($v)){throw 'ingredient unavailable'};return $v}
function Header([string]$Key){$b=[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$Key"));return "AUTHORIZATION: basic $b"}
function Lock([string]$Root,[string]$Key){& git -C $Root config http.https://github.com/.extraheader (Header $Key);if($LASTEXITCODE){throw 'batch rejected'}}
function Pull([string]$Name,[string]$Slug,[string]$Key){
    $h=Header $Key;$u="https://github.com/$Slug.git";$dst=Join-Path $Bench $Name
    & git -c "http.https://github.com/.extraheader=$h" clone --quiet --branch main $u $dst *> $null
    if($LASTEXITCODE){throw 'batch rejected'}
    Lock $dst $Key
    & git -C $dst lfs pull *> $null;if($LASTEXITCODE){throw 'batch rejected'}
}
try{
    Lock $Shelf (Need 'SHELF_KEY')
    Pull 'mix' (Need 'MIX') (Need 'MIX_KEY')
    Pull 'filling' (Need 'FILL') (Need 'FILL_KEY')
    $bake=Join-Path $Mix 'Tools\Bake.ps1'
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
    Write-Host '[Patisserie] batch=rejected station=table'
    exit 1
}
