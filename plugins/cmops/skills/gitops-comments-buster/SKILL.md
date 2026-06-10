---
name: gitops-comments-buster
description: >-
  Use this skill to evaluate, challenge, or dismiss AI-generated code review
  comments posted by the GitOps (Git LowPriv) automated bot on an Azure DevOps
  pull request. Trigger when the user questions whether bot feedback is valid,
  wants to bulk-clear AI review noise, or uses phrases like 'challenge gitops
  comments', 'bust gitops feedback', 'dismiss AI review', or expresses
  frustration that the automated reviewer flagged something incorrectly. This
  skill is specifically for the AI bot auto-commenting on ADO PRs — not for
  human code reviewer feedback, setting up GitOps CI/CD workflows
  (ArgoCD/Flux), configuring the AI reviewer, PR policy check failures, general
  code audits, or abandoning a PR. The PR must be in Azure DevOps, not GitHub.
argument-hint: "[PR ID or URL]"
user-invocable: true
---

# GitOps Comments Buster

Analyze AI code review comments on an Azure DevOps pull request — from GitOps (Git LowPriv), MerlinBot, or any AI reviewer — challenge irrelevant or incorrect suggestions, and help the user dismiss noise or fix real issues.

## Workflow

1. Gather PR context
2. Detect available tooling (MCP vs az CLI)
3. Fetch active AI code review threads
4. Read the actual code for each comment
5. Classify: **Valid** / **Questionable** / **Irrelevant**
6. Present analysis, then act on user's choice

---

## Step 1: Gather PR Context

Parse from `$ARGUMENTS` if provided — accept a PR URL or a numeric ID.

**From a PR URL:**
```
https://{org}.visualstudio.com/{project}/_git/{repo}/pullrequest/{pr-id}
```
Extract: PR ID, org URL (`https://{org}.visualstudio.com/DefaultCollection`), project name.

**From a PR ID only:** infer org and project from the git remote:
```bash
git remote get-url origin
```

**If nothing is specified:** detect the current branch and find its open PR:
```bash
git branch --show-current
az repos pr list --organization "<org>" \
  --query "[?sourceRefName=='refs/heads/<branch>'] | [0]" -o json
```

If the remote is not an Azure DevOps URL (e.g. GitHub), tell the user clearly and ask for an ADO PR URL or ID. Do not search GitHub for AI code review comments.

If you still can't resolve a PR, ask the user for the PR ID or URL before proceeding.

---

## Step 2: Detect Available Tooling

Check whether MCP repo tools are available in your current toolset by looking for `repo_list_pull_request_threads`. This determines which path to use throughout the rest of the skill.

- **Option A (MCP available):** use the `repo_*` MCP tool calls shown below
- **Option B (MCP not available):** use the `az repos` CLI or REST API fallback shown below

---

## Step 3: Fetch Active AI Code Review Threads

AI code review threads in Azure DevOps come from different bot accounts depending on the organization:
- `GitOps (Git LowPriv)` — used in the msazure/One org
- `MerlinBot` — common in other ADO orgs
- Other AI reviewer accounts

### Option A — MCP

Try fetching with a specific author filter first. If it returns no results, fetch all and filter client-side.

```
repo_list_pull_request_threads(
  repositoryId="<repo-id>",
  pullRequestId=<pr-id>,
  authorDisplayName="GitOps"   # try this first; then "MerlinBot" if empty
)
```

Filter client-side for any thread where:
- `comments[0].author.displayName` contains "gitops", "merlin", or "git lowpriv" (case-insensitive), **or**
- The comment text contains "AI Code Review" (the badge header used by the PR Assistant)

### Option B — az CLI / REST API

First try az CLI:
```bash
az repos pr thread list --id <pr-id> --organization "<org>" --output json
```

If the `thread` subcommand is unavailable (older az CLI versions), fall back to the REST API:
```bash
TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://dev.azure.com/<org>/<project>/_apis/git/repositories/<repo>/pullRequests/<pr-id>/threads?api-version=7.1"
```

Filter the result client-side using the same two criteria as Option A (author name OR "AI Code Review" in comment text).

**Process only Active threads.** Skip already-resolved threads unless the user explicitly asks otherwise.

For each qualifying thread, capture: thread ID, file path, line range, and comment text.

---

## Step 4: Read the Actual Code

For each active AI code review thread that references a file:

1. Read the file with the Read tool, focusing on the cited lines plus enough surrounding context to understand scope (enclosing function, class, relevant imports).
2. Check what changed in the PR for that file:
   ```bash
   git diff origin/<target-branch>...HEAD -- <file-path>
   ```

This step is essential. AI reviewers see files in isolation — they miss:
- Error handling that exists in a calling scope
- Cleanup logic in a lifecycle hook or destructor
- Project-wide patterns that make a suggestion wrong for this codebase

---

## Step 5: Classify Each Comment

### Valid
A real issue that should be fixed:
- Actual bug or logic error visible in the code
- Security vulnerability
- Likely runtime failure (unhandled null, missing error path that matters)
- Verifiable violation of an established project convention

### Questionable
Has some merit but may not need action:
- Style preference with no clear precedent in the codebase
- Theoretical risk unlikely to occur given usage context
- Useful improvement, not a correctness problem

For questionable items, share your reasoning and let the user decide.

### Irrelevant
Does not apply to this code:
- Misunderstands what the code actually does
- Flags something intentional (e.g., deliberate exception suppression with an explanatory comment)
- Suggests an API, pattern, or type that doesn't exist in this language/framework/version
- Duplicate of another comment covering the same issue
- The code is correct as written

**Default posture:** AI reviewers lack full codebase context, so treat irrelevance as the prior. A comment needs a clear reason to be valid — not the other way around.

**Calibration check:** if you find yourself marking >80% of comments as Irrelevant, re-examine one or two to make sure you aren't being too dismissive. AI reviewers are noisy but not always wrong.

---

## Step 6: Present Analysis & Offer Actions

Output a summary table:

```
## AI Code Review Analysis — PR #<id>

| # | File | Bot Says | Verdict | Reasoning |
|---|------|----------|---------|-----------|
| 1 | `src/Foo.cs:45` | "Missing null check on response" | ✅ Valid | `data` can be undefined when the API returns 404 |
| 2 | `src/Bar.cs:12` | "Use async/await instead of .ContinueWith()" | ❌ Irrelevant | Codebase consistently uses .ContinueWith(); no convention to break |
| 3 | `src/Baz.cs:89` | "filterNamespace inconsistent with aksNamespace" | ⚠️ Questionable | Other methods use filterNamespace too — author's call |

**Valid: 1** · **Questionable: 1** · **Irrelevant: 1**
```

Then ask:

> What would you like to do?
> 1. **Fix valid issues** — I'll make the code changes
> 2. **Dismiss irrelevant** — I'll reply + close each irrelevant thread
> 3. **Fix valid + dismiss irrelevant** — both (recommended)
> 4. **Review individually** — walk through each one together
> 5. **No action** — keep the analysis only

---

## Dismissing Comments

Reply to the thread with a concise justification, then mark it as **Won't Fix**. When dismissing multiple threads, run all reply + status-update calls **in parallel** rather than one by one.

### Option A — MCP

```
repo_reply_to_comment(
  repositoryId="<repo-id>",
  pullRequestId=<pr-id>,
  threadId=<thread-id>,
  content="Not applicable — <brief reason>. Resolving."
)

repo_update_pull_request_thread(
  repositoryId="<repo-id>",
  pullRequestId=<pr-id>,
  threadId=<thread-id>,
  status="WontFix"
)
```

### Option B — az CLI

```bash
az repos pr comment create --id <pr-id> --thread-id <tid> \
  --text "Not applicable — <brief reason>. Resolving." \
  --organization "<org>"

az repos pr thread update --id <pr-id> --thread-id <tid> \
  --status wontFix --organization "<org>"
```

Keep dismissal replies concise — "Not applicable — handled in parent scope" beats a paragraph. Future reviewers may read resolved threads, so leave a clear trail.

---

## Fixing Valid Issues

1. Make the code change.
2. Reply to the thread confirming the fix.
3. Mark the thread as Fixed:

### Option A — MCP

```
repo_update_pull_request_thread(
  repositoryId="<repo-id>",
  pullRequestId=<pr-id>,
  threadId=<thread-id>,
  status="Fixed"
)
```

### Option B — az CLI

```bash
az repos pr thread update --id <pr-id> --thread-id <tid> \
  --status fixed --organization "<org>"
```

---

## Tips

- **Don't dismiss without reading the code.** Confirm irrelevance by looking at the actual lines, not just the comment text.
- **Check project patterns.** If the codebase consistently uses a pattern the AI flags, the comment is almost certainly irrelevant.
- **Fix valid concerns even if annoying.** The AI reviewer can be irritating and still occasionally be right.
- **Questionable items are yours to decide.** When in doubt between Questionable and Irrelevant, call it Questionable and explain your reasoning.
- **Already-resolved PRs:** If the PR is merged and all threads are already closed/fixed/wontFix, still show the analysis and describe what the dismissal plan would have been — this helps the user understand the rationale even after the fact.
