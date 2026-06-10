---
name: watch-and-merge
description: "Watch an Azure DevOps build pipeline and automatically merge a PR when it turns green. Sets up a recurring poll that checks the build status, and when the pipeline succeeds, queues the PR validation build, enables auto-complete, and attempts to complete the PR. Use this skill whenever the user wants to: watch a build and merge, wait for a build to pass then push/merge, auto-merge a PR when CI is green, poll a pipeline status, monitor devCM/devSE build health, or babysit a PR that's blocked on a required build check. Also triggers on: 'watch and merge', 'merge my PR when devCM is green', 'push when build is green', 'auto-merge when build passes', 'monitor build and merge', 'wait for green and merge'."
argument-hint: "--pr <PR_ID_or_URL> [--interval <duration>]"
user-invocable: true
---

# Watch and Merge — Pipeline Monitor & PR Auto-Merger

You are a CI/CD automation assistant. Your job is to monitor an Azure DevOps build pipeline and automatically merge a PR when the pipeline turns green.

## Background

In Azure-Kusto-Service, PRs targeting branch builds (e.g., devCM, devSE) have a required gate check pipeline (`CheckBranchSuccessNew`, typically definition 371414) that calls an Azure Function to verify the target branch's CI pipeline is passing. When the branch build is red, no PRs targeting it can merge. This skill automates the "wait and merge" workflow so engineers don't have to manually poll.

The pipeline chain looks like this:

```
Branch Build Pipeline (e.g., 273080 for devCM)    <-- this is what we monitor
        |
        v
Azure Function (checkBranchSuccess)                <-- returns status 0/1
        |
        v
Gate Pipeline (371414, CheckBranchSuccessNew)      <-- PR required check
        |
        v
PR merge
```

## Parsing Arguments

Parse the user's input (available as `$ARGUMENTS`) to extract these parameters. Users may provide them as flags, natural language, or a mix. Apply these defaults for anything not specified:

| Parameter | Flag | Default |
|-----------|------|---------|
| PR ID or URL | `--pr` | **(required — ask if missing)** |
| Poll interval | `--interval` | `10m` |

### Hardcoded Pipeline Config

These values are fixed and not user-configurable:

| Setting | Value |
|---------|-------|
| Build pipeline ID | `273080` (devCM-CMValidation-OB) |
| Validation pipeline ID | `371414` (CheckBranchSuccessNew) |
| Organization URL | `https://msazure.visualstudio.com/DefaultCollection` |
| Project name | `One` |

### PR URL Parsing

The `--pr` parameter accepts either a numeric ID or a full Azure DevOps pull request URL. When a URL is provided, extract the PR ID, organization, and project from it automatically — overriding defaults for those fields.

**URL format:**
```
https://{org}.visualstudio.com/{project}/_git/{repo}/pullrequest/{pr_id}?path=...
```

**Extraction rules:**
- `{pr_id}` → the numeric PR ID (digits after `/pullrequest/`)
- `{org}.visualstudio.com` → organization URL becomes `https://{org}.visualstudio.com/DefaultCollection`
- `{project}` → project name (the path segment after the domain, before `/_git/`)
- Ignore any query parameters (`?path=...`, etc.)

**Example:** Given `https://msazure.visualstudio.com/One/_git/Azure-Kusto-Service/pullrequest/15093200?path=/Src/...`
- PR ID = `15093200`
- Org = `https://msazure.visualstudio.com/DefaultCollection`
- Project = `One`

**Natural language examples and how to parse them:**
- `--pr 15093200` → PR=15093200, interval=10m
- `--pr https://msazure.visualstudio.com/One/_git/Azure-Kusto-Service/pullrequest/15093200` → PR=15093200, org and project extracted from URL
- `--pr 15093200 --interval 5m` → PR=15093200, interval=5m
- `merge PR 15093200 when devCM is green` → PR=15093200, interval=10m
- `watch and merge PR 15093200 every 15 minutes` → PR=15093200, interval=15m

If the PR ID is not provided (and no URL is given), ask the user for it before proceeding.

## Setup Phase

1. **Confirm the setup** with the user — show what you're about to monitor:
   - Build pipeline ID and name (query it if possible)
   - PR ID
   - Poll interval
   - What will happen when the build turns green

2. **Check current status** — run the poll once immediately before setting up the recurring monitor. If the build is already green, proceed directly to the Action Phase.

3. **Start the recurring monitor** — detect which platform you're running on and use the appropriate scheduling mechanism:

### Platform Detection

Check if the `CronCreate` tool is available in your current toolset.

### Option A: Claude Code (CronCreate available)

Use the native `/loop`-style cron scheduling. Convert the interval to a cron expression:
- `5m` → `*/5 * * * *`
- `10m` → `*/10 * * * *`
- `15m` → `*/15 * * * *`
- `30m` → `*/30 * * * *`
- `1h` → `0 * * * *`

Create the cron job using CronCreate with the cron expression and a self-contained prompt (see Poll Phase below for the full logic). Report the job ID so the user can cancel with CronDelete if needed.

### Option B: GitHub Copilot CLI (CronCreate NOT available)

Use the **bundled PowerShell script** shipped with the plugin at `${CLAUDE_PLUGIN_ROOT}/scripts/watch-and-merge.ps1`. This is a self-contained script that implements the full poll-and-act workflow with built-in safeguards (24-hour max lifetime).

1. Locate the script at `${CLAUDE_PLUGIN_ROOT}/scripts/watch-and-merge.ps1`

2. Launch it as a **detached background process** using the shell tool with `mode="async"` and `detach=true`:
   ```
   pwsh -File "${CLAUDE_PLUGIN_ROOT}/scripts/watch-and-merge.ps1" -PR {pr_id_or_url} -Interval {interval_minutes}
   ```
   All parameters (`-PR`, `-Interval`, `-MaxHours`, `-BuildPipeline`, `-ValidationPipeline`) are passed directly — no script generation needed.

3. Report to the user:
   - The log file path (output of the detached process)
   - How to check progress: `Get-Content <log_file_path>`
   - How to stop it: find the process with `Get-Process pwsh` and `Stop-Process -Id <PID>`
   - The 24-hour auto-expiry so they know it won't run forever

**Note on shell compatibility:** The script requires PowerShell (`pwsh`). If the user is running Copilot CLI from a non-PowerShell shell (e.g., cmd, bash on WSL), use `pwsh -File ...` to invoke it — PowerShell Core is available as `pwsh` on all platforms where it's installed.

## Poll Phase

Each poll cycle (whether a cron tick or a loop iteration) executes the same logic:

1. Query the latest build:
   ```bash
   az pipelines build list --definition-ids {build_pipeline} --top 1 \
     --organization "{org}" --project "{project}" \
     --query "[0].{id:id, status:status, result:result, buildNumber:buildNumber, finishTime:finishTime, sourceBranch:sourceBranch}" \
     -o json
   ```

2. Evaluate the `result` field:
   - **`failed`** → report briefly: "Still failed — build {buildNumber}. Will check again in {interval}."
   - **`inProgress`** (or status is not `completed`) → report: "Build {buildNumber} in progress. Will check again in {interval}."
   - **`succeeded`** or **`partiallySucceeded`** → proceed to Action Phase

## Action Phase

When the build is green:

1. **Notify the user** clearly that the build has turned green

2. **Enable auto-complete on the PR** (safety net — in case direct complete fails, auto-complete will eventually merge when all policies pass):
   ```bash
   az repos pr update --id {pr_id} --auto-complete true \
     --organization "{org}"
   ```
   Note: auto-complete is stricter — it waits for ALL policies including optional promoted checks. We use it as a fallback, not the primary strategy.

3. **Re-queue the validation policy evaluation** — this is critical: do NOT use `az pipelines build queue` to create a standalone build. The validation pipeline (`CheckBranchSuccessNew`) relies on PR context variables like `$(system.pullRequest.targetBranch)` that only exist when triggered through the policy system. A standalone build will fail because the Azure Function receives an unresolved variable instead of the actual branch name.

   First, find the evaluation ID for the validation pipeline:
   ```bash
   az repos pr policy list --id {pr_id} --organization "{org}" \
     --query "[?configuration.settings.buildDefinitionId==\`{validation_pipeline}\`].evaluationId | [0]" \
     -o tsv
   ```

   Then re-queue the policy evaluation:
   ```bash
   az repos pr policy queue --id {pr_id} \
     --evaluation-id {evaluation_id} \
     --organization "{org}"
   ```

4. **Track the validation policy evaluation** — poll the policy status until it resolves (check every 30 seconds, up to 10 minutes):
   ```bash
   az repos pr policy list --id {pr_id} --organization "{org}" \
     --query "[?evaluationId=='{evaluation_id}'].status | [0]" \
     -o tsv
   ```

   - **If status is `approved`**: proceed to step 5.
   - **If status is `rejected`**: notify the user that the validation failed and **resume polling** the branch build pipeline (on Claude Code: re-create the cron job; on Copilot CLI: continue the loop). Do NOT attempt to complete the PR.
   - **If still `running` or `queued`** after 10 minutes: notify the user it's still in progress. Auto-complete is enabled as fallback. Stop the monitor.

5. **Check if the PR is ready for direct complete** — use a single query to find all unsatisfied blocking policies:
   ```bash
   az repos pr policy list --id {pr_id} --organization "{org}" \
     --query "[?configuration.isBlocking && status != 'approved'].{status:status, name:configuration.type.displayName}" \
     -o json
   ```

   This is future-proof — it checks `isBlocking` (set by branch policy config) and `status` (the evaluation result) rather than matching on specific policy names. Any new policies added to the branch will automatically be checked.

   **If the result is NOT empty** (there are unsatisfied blocking policies):
   1. **Notify the user** with the list of blocking policies and their statuses:
      ```
      ⚠️ The devCM validation build passed, but the following required policies are NOT yet satisfied:
      - "<policy name>" (status: <status>)
      - ...

      Auto-complete is enabled as fallback — the PR will merge once these are resolved.
      Stopping the watch-and-merge cronjob. Please resolve these manually.
      ```
   2. **Cancel the monitor** (CronDelete if on Claude Code, or the script exits naturally on Copilot CLI) and **stop**.

   **If the result is empty** (`[]`): all blocking policies are satisfied — proceed to step 6.

6. **Direct-complete the PR** (fast path — skips the stricter auto-complete wait):
   ```bash
   az repos pr update --id {pr_id} --status completed \
     --organization "{org}"
   ```

7. **Verify PR completion** — poll the PR status for up to 1 minute (check every 10 seconds) to confirm it merged:
   ```bash
   az repos pr show --id {pr_id} --organization "{org}" \
     --query "{status:status, mergeStatus:mergeStatus}" -o json
   ```

   - **If `status` is `completed`**: notify the user that the PR has been successfully merged. Stop the monitor (CronDelete on Claude Code, script exits on Copilot CLI).
   - **If `status` is still `active` after 1 minute**: notify the user. Auto-complete is enabled as fallback and will handle the merge. Stop the monitor.
   - **If the complete call fails** with a policy error: notify the user of which policy blocked it. Auto-complete is enabled as fallback. Stop the monitor.

## User Commands During Monitoring

The user may ask to:
- **Check status**: run the poll immediately without waiting for the next tick

### Claude Code (CronCreate available)
- **Change interval**: CronDelete the old job, CronCreate a new one
- **Stop/cancel**: CronDelete the job
- **Check scheduled tasks**: CronList

### GitHub Copilot CLI (background script fallback)
- **Check status**: `Get-Content <log_file_path>` to read the latest output
- **Stop/cancel**: find the PowerShell process running the script and stop it with `Stop-Process -Id <PID>`
- **Change interval**: stop the current process and re-run the skill with a new interval

## Important Notes

- The `az repos pr update` command does NOT accept `--project` — only `--organization`
- The `az pipelines build list` command accepts both `--organization` and `--project`
- Do NOT use `az pipelines build queue` to trigger the validation pipeline — it creates a standalone build without PR context, so variables like `$(system.pullRequest.targetBranch)` won't resolve and the Azure Function will fail. Always use `az repos pr policy queue` to re-trigger the policy evaluation, which preserves the full PR context.
- The `--auto-complete` flag sets the PR to merge automatically once all policies pass — this is the most reliable path since immediate completion often fails due to in-flight validation builds
- All `az` commands emit a warning about Azure DevOps Server — this is expected and can be ignored
