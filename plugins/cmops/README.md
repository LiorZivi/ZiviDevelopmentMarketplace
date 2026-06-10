# CMOps

Azure DevOps CI/CD operations for the Kusto Cluster Management team.

## Problem

PRs targeting branch builds (e.g., `devCM`) have a required gate check that calls an Azure Function to verify the branch's CI pipeline is passing. When the branch build is red — which can persist for hours or days — no PRs targeting that branch can merge. Engineers end up manually polling the build status and racing to merge when it briefly turns green.

## Pipeline Chain (devCM example)

```
Pipeline 273080 (devCM-CMValidation-OB)       <-- actual branch build (this is what we monitor)
        |
        v  checked by
Azure Function (checkBranchSuccess)            <-- returns status 0 (green) or 1 (red)
        |
        v  called by
Pipeline 371414 (CheckBranchSuccessNew)        <-- PR required check (generic gate)
        |
        v  blocks/unblocks
PR merge
```

The gate pipeline (371414) is generic — it checks different branches depending on the PR's target branch (devCM, devSE, etc.). The Azure Function queries the actual branch build pipeline (e.g., 273080 for devCM) to determine status.

## Skills

### watch-and-merge

Watches a build pipeline and automatically merges a PR when it turns green.

**Usage:**
```
/cmops:watch-and-merge --pr <PR_ID_or_URL>
/cmops:watch-and-merge --pr <PR_ID_or_URL> --interval 5m
```

The `--pr` parameter accepts a numeric ID or a full Azure DevOps PR URL. When a URL is provided, the PR ID, organization, and project are extracted automatically.

```
/cmops:watch-and-merge --pr https://msazure.visualstudio.com/One/_git/Azure-Kusto-Service/pullrequest/15093200
```

**Parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--pr` | PR ID or full Azure DevOps PR URL | (required) |
| `--interval` | Poll interval | `10m` |

**Behavior:**

1. **Poll Phase** — Queries the latest build via `az pipelines build list`. If `failed` or `inProgress`, reports status and waits. If `succeeded` or `partiallySucceeded`, proceeds to action phase.
2. **Action Phase** — Notifies the user, queues the PR validation build, enables auto-complete, and attempts to merge. If completion fails due to policies, reports that auto-complete is set and the PR will merge once validation passes.

**Cron Setup:** The skill converts the interval to a cron expression (`5m` → `*/5 * * * *`) and runs each tick as a self-contained poll-and-act cycle.

## Prerequisites

- Azure CLI with the DevOps extension (`az devops`)
- Authenticated to the Azure DevOps organization

## Future Skills (potential)

- `check-build` — one-shot build status check (no polling)
- `investigate-build` — fetch and analyze build failure logs
- `queue-build` — manually trigger a build pipeline

## Plugin Structure

```
cmops/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── watch-and-merge/
│       └── SKILL.md
└── README.md
```
