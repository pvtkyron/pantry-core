[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Script,
    [string]$SourceRoot='source'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$recordPath=Join-Path $env:RUNNER_TEMP ('kyron-source-supersession-'+[guid]::NewGuid().ToString('N')+'.json')
$savedRecord=$env:KYRON_HOSTED_SUPERSESSION_RECORD
$env:KYRON_HOSTED_SUPERSESSION_RECORD=$recordPath
$failure=$null
$stepExit=0
try {
    $global:LASTEXITCODE=0
    try {
        & $Script
        $stepExit=$LASTEXITCODE
    } catch {
        $failure=$_
        $stepExit=1
    }
    if(Test-Path -LiteralPath $recordPath) {
        $item=Get-Item -LiteralPath $recordPath -ErrorAction Stop
        if($item.PSIsContainer-or($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-or$item.Length-gt4096){
            throw 'Hosted source supersession record rejected'
        }
        try {$record=Get-Content -LiteralPath $recordPath -Raw|ConvertFrom-Json}
        catch {throw 'Hosted source supersession record rejected'}
        if($env:GITHUB_ACTIONS-cne'true'-or$env:GITHUB_REPOSITORY-cne'pvtkyron/pantry-core'-or
           $env:GITHUB_REF-cne'refs/heads/main'-or$env:GITHUB_RUN_ID-cnotmatch'^[1-9][0-9]*$'-or
           $env:GITHUB_RUN_ATTEMPT-cnotmatch'^[1-9][0-9]*$'-or$env:GITHUB_SHA-cnotmatch'^[0-9a-f]{40}$'-or
           [string]::IsNullOrWhiteSpace($env:GITHUB_JOB)){
            throw 'Hosted source supersession context rejected'
        }
        $required=@('schema','kind','run_id','run_attempt','job_id','workflow_repository','workflow_sha','source_sha','main_sha','scope')
        foreach($name in $required){if($null-eq$record.PSObject.Properties[$name]){throw 'Hosted source supersession record incomplete'}}
        if($record.schema-ne1-or$record.kind-cne'workspace-source-superseded'-or
           [string]$record.run_id-cne$env:GITHUB_RUN_ID-or[string]$record.run_attempt-cne$env:GITHUB_RUN_ATTEMPT-or
           $record.job_id-cne$env:GITHUB_JOB-or$record.workflow_repository-cne$env:GITHUB_REPOSITORY-or
           $record.workflow_sha-cne$env:GITHUB_SHA-or$record.source_sha-cnotmatch'^[0-9a-f]{40}$'-or
           $record.main_sha-cnotmatch'^[0-9a-f]{40}$'-or$record.main_sha-ceq$record.source_sha-or
           $record.scope-cnotin@('Launcher','Windows','Both','Lib','Bootstrap','KyronLink','RevTranslator','All')){
            throw 'Hosted source supersession identity rejected'
        }
        $source=[IO.Path]::GetFullPath($SourceRoot)
        $actual=@(& git -C $source rev-parse HEAD 2>$null)
        if($LASTEXITCODE-ne0-or$actual.Count-ne1-or$actual[0].Trim()-cne$record.source_sha){
            throw 'Hosted source supersession checkout changed'
        }
        $origin=@(& git -C $source remote get-url origin 2>$null)
        if($LASTEXITCODE-ne0-or$origin.Count-ne1-or$origin[0]-notmatch'(?i)^(?:https://github\.com/|git@github\.com:)pvtkyron/Workspace(?:\.git)?$'){
            throw 'Hosted source supersession origin rejected'
        }
        & git -C $source merge-base --is-ancestor $record.source_sha $record.main_sha 2>$null
        if($LASTEXITCODE-ne0){throw 'Hosted source supersession ancestry rejected'}
        if([string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)-or[string]::IsNullOrWhiteSpace($env:GITHUB_OUTPUT)){
            throw 'Hosted supersession cancellation binding unavailable'
        }
        # Set the explicit continuation guard before asking GitHub to cancel;
        # cancellation is asynchronous, so later upload/publish steps also skip.
        [IO.File]::AppendAllText($env:GITHUB_OUTPUT,"superseded=true`n",[Text.UTF8Encoding]::new($false))
        $runUri=$env:GITHUB_API_URL.TrimEnd('/')+'/repos/'+$env:GITHUB_REPOSITORY+'/actions/runs/'+$env:GITHUB_RUN_ID
        $headers=@{Authorization='Bearer '+$env:GITHUB_TOKEN;Accept='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
        $run=Invoke-RestMethod -UseBasicParsing -Method Get -Uri $runUri -Headers $headers -TimeoutSec 30
        if([string]$run.id-cne$env:GITHUB_RUN_ID-or[string]$run.run_attempt-cne$env:GITHUB_RUN_ATTEMPT-or$run.head_sha-cne$env:GITHUB_SHA){
            throw 'Hosted supersession run attempt changed; cancellation rejected'
        }
        # Do not turn a real sibling-job failure into a cancelled workflow.
        for($pageNumber=1;$pageNumber-le20;$pageNumber++){
            $page=Invoke-RestMethod -UseBasicParsing -Method Get -Uri ($runUri+'/jobs?filter=latest&per_page=100&page='+$pageNumber) -Headers $headers -TimeoutSec 30
            if($null-eq$page.PSObject.Properties['jobs']-or$null-eq$page.PSObject.Properties['total_count']){throw 'Hosted supersession job state unavailable'}
            if(@($page.jobs|Where-Object{$_.conclusion-in@('failure','timed_out','action_required')}).Count){
                throw 'Another job failed; its workflow failure must remain visible'
            }
            if([int]$page.total_count-le$pageNumber*100){break}
            if($pageNumber-eq20){throw 'Hosted supersession job-state verification limit exceeded'}
        }
        $response=Invoke-WebRequest -UseBasicParsing -Method Post -Uri ($runUri+'/cancel') -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 30
        if([int]$response.StatusCode-ne202){throw 'Hosted supersession cancellation was not accepted'}
        Write-Host '[HOSTED/SOURCE][SKIP] Newer source superseded this run.'
        exit 0
    }
    if($failure){throw $failure}
    exit $stepExit
} finally {
    $env:KYRON_HOSTED_SUPERSESSION_RECORD=$savedRecord
    if(Test-Path -LiteralPath $recordPath -PathType Leaf){Remove-Item -LiteralPath $recordPath -Force}
}
