<#
.SYNOPSIS
    Watch an Azure DevOps build pipeline and automatically merge a PR when it turns green.

.DESCRIPTION
    Polls a build pipeline at a configurable interval. When the build succeeds:
    1. Enables auto-complete on the PR (safety net)
    2. Re-queues the validation policy evaluation
    3. Tracks validation status
    4. Attempts direct PR completion
    5. Verifies the merge

    The script auto-exits after a configurable maximum lifetime (default: 24 hours).

.PARAMETER PR
    PR ID or full Azure DevOps PR URL.
    Example: 15218949
    Example: https://msazure.visualstudio.com/One/_git/Azure-Kusto-Service/pullrequest/15218949

.PARAMETER Interval
    Poll interval in minutes. Default: 10.

.PARAMETER MaxHours
    Maximum lifetime in hours before auto-exit. Default: 24.

.PARAMETER BuildPipeline
    Build pipeline definition ID to monitor. Default: 273080 (devCM-CMValidation-OB).

.PARAMETER ValidationPipeline
    Validation pipeline definition ID. Default: 371414 (CheckBranchSuccessNew).

.EXAMPLE
    .\watch-and-merge.ps1 -PR 15218949 -Interval 5
    .\watch-and-merge.ps1 -PR https://msazure.visualstudio.com/One/_git/Azure-Kusto-Service/pullrequest/15218949 -Interval 10
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$PR,

    [int]$Interval = 10,
    [int]$MaxHours = 24,
    [int]$BuildPipeline = 273080,
    [int]$ValidationPipeline = 371414
)

# --- Parse PR URL or ID ---
$org = "https://msazure.visualstudio.com/DefaultCollection"
$project = "One"

if ($PR -match "https?://([^/]+)\.visualstudio\.com/([^/]+)/_git/[^/]+/pullrequest/(\d+)") {
    $org = "https://$($Matches[1]).visualstudio.com/DefaultCollection"
    $project = $Matches[2]
    $prId = $Matches[3]
} elseif ($PR -match "^\d+$") {
    $prId = $PR
} else {
    Write-Host "ERROR: Invalid PR parameter. Provide a numeric PR ID or a full Azure DevOps PR URL."
    exit 1
}

# --- Config ---
$intervalSeconds = $Interval * 60
$startTime = Get-Date
$maxEndTime = $startTime.AddHours($MaxHours)

Write-Host "============================================"
Write-Host " Watch-and-Merge Monitor"
Write-Host "============================================"
Write-Host "PR:                  $prId"
Write-Host "Organization:        $org"
Write-Host "Project:             $project"
Write-Host "Build Pipeline:      $BuildPipeline"
Write-Host "Validation Pipeline: $ValidationPipeline"
Write-Host "Poll Interval:       ${Interval}m"
Write-Host "Max Lifetime:        ${MaxHours}h (auto-exit at $($maxEndTime.ToString('yyyy-MM-dd HH:mm:ss')))"
Write-Host "Started at:          $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "============================================"
Write-Host ""

# --- Poll Loop ---
while ($true) {
    # Safety: check max lifetime
    if ((Get-Date) -ge $maxEndTime) {
        Write-Host ""
        Write-Host "=== SAFETY LIMIT: ${MaxHours}-hour maximum lifetime reached. Exiting. ==="
        Write-Host "The build pipeline ($BuildPipeline) never turned green during the monitoring period."
        Write-Host "Re-run the script to resume monitoring."
        break
    }

    # Query latest build
    $buildJson = az pipelines build list `
        --definition-ids $BuildPipeline --top 1 `
        --organization $org --project $project `
        --query "[0].{id:id, status:status, result:result, buildNumber:buildNumber, finishTime:finishTime, sourceBranch:sourceBranch}" `
        -o json 2>$null
    $build = $buildJson | ConvertFrom-Json

    if ($build.result -eq "succeeded" -or $build.result -eq "partiallySucceeded") {
        Write-Host ""
        Write-Host "BUILD IS GREEN! Build $($build.buildNumber) - result: $($build.result)"
        Write-Host "$(Get-Date -Format 'HH:mm:ss') - Proceeding with merge workflow..."

        # --- Action Phase ---

        # Step 1: Enable auto-complete
        Write-Host "  [1/6] Enabling auto-complete on PR $prId..."
        az repos pr update --id $prId --auto-complete true --organization $org 2>$null | Out-Null

        # Step 2: Find validation evaluation ID
        Write-Host "  [2/6] Finding validation pipeline evaluation ID..."
        $evalId = az repos pr policy list --id $prId --organization $org `
            --query "[?configuration.settings.buildDefinitionId==``$ValidationPipeline``].evaluationId | [0]" `
            -o tsv 2>$null

        if (-not $evalId -or $evalId -eq "None") {
            Write-Host "  WARNING: Could not find evaluation ID for validation pipeline $ValidationPipeline"
            Write-Host "  Auto-complete is enabled as fallback. Stopping."
            break
        }

        # Step 3: Re-queue validation
        Write-Host "  [3/6] Re-queuing validation policy evaluation (ID: $evalId)..."
        az repos pr policy queue --id $prId --evaluation-id $evalId --organization $org 2>$null | Out-Null

        # Step 4: Track validation - poll every 30s for up to 10 min
        Write-Host "  [4/6] Tracking validation policy status..."
        $maxWait = 600
        $elapsed = 0
        $valStatus = "running"
        while ($elapsed -lt $maxWait) {
            Start-Sleep -Seconds 30
            $elapsed += 30
            $valStatus = az repos pr policy list --id $prId --organization $org `
                --query "[?evaluationId=='$evalId'].status | [0]" -o tsv 2>$null
            Write-Host "         $(Get-Date -Format 'HH:mm:ss') - Validation: $valStatus ($elapsed`s elapsed)"

            if ($valStatus -eq "approved") { break }
            if ($valStatus -eq "rejected") {
                Write-Host "  Validation REJECTED. Resuming build pipeline polling..."
                break
            }
        }

        if ($valStatus -eq "rejected") {
            Start-Sleep -Seconds $intervalSeconds
            continue
        }

        if ($valStatus -ne "approved") {
            Write-Host "  Validation still in progress after 10 min. Auto-complete is set as fallback. Stopping."
            break
        }

        # Step 5: Check all blocking policies
        Write-Host "  [5/6] Checking all blocking policies..."
        $blockingJson = az repos pr policy list --id $prId --organization $org `
            --query "[?configuration.isBlocking && status != 'approved'].{status:status,name:configuration.type.displayName}" `
            -o json 2>$null
        $blocking = $blockingJson | ConvertFrom-Json

        if ($blocking -and $blocking.Count -gt 0) {
            Write-Host "  WARNING: Unsatisfied blocking policies:"
            foreach ($p in $blocking) { Write-Host "    - $($p.name) (status: $($p.status))" }
            Write-Host "  Auto-complete is enabled as fallback. Stopping."
            break
        }

        # Step 6: Direct complete
        Write-Host "  [6/6] All policies satisfied! Completing PR $prId..."
        az repos pr update --id $prId --status completed --organization $org 2>$null | Out-Null

        # Verify
        $verifyElapsed = 0
        $prStatus = $null
        while ($verifyElapsed -lt 60) {
            Start-Sleep -Seconds 10
            $verifyElapsed += 10
            $prStatusJson = az repos pr show --id $prId --organization $org `
                --query "{status:status,mergeStatus:mergeStatus}" -o json 2>$null
            $prStatus = $prStatusJson | ConvertFrom-Json
            Write-Host "         PR status: $($prStatus.status), mergeStatus: $($prStatus.mergeStatus)"
            if ($prStatus.status -eq "completed") {
                Write-Host ""
                Write-Host "  PR $prId MERGED SUCCESSFULLY!"
                break
            }
        }

        if ($prStatus.status -ne "completed") {
            Write-Host "  PR not yet completed after 1 min. Auto-complete is enabled as fallback."
        }
        break
    } else {
        $remaining = $maxEndTime - (Get-Date)
        $remainingStr = "{0:hh\:mm}" -f $remaining
        Write-Host "$(Get-Date -Format 'HH:mm:ss') - Build $($build.buildNumber): $($build.result). Next check in ${Interval}m. ($remainingStr remaining)"
    }

    Start-Sleep -Seconds $intervalSeconds
}

Write-Host ""
Write-Host "=== Watch-and-Merge Finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
