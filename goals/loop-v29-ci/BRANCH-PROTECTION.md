# Branch-protection recommendation

This is a documentation-only recommendation. It does not change repository
settings, add reviewers, or alter any workflow.

## Required status checks

After each new workflow has completed at least once, require these exact check
names for pull requests into the protected integration branch:

| Workflow | Required check |
| --- | --- |
| `CI Backend` | `CI Backend / Backend checks` |
| `CI Frontend` | `CI Frontend / Frontend checks` |
| `CI E2E` | `CI E2E / Local-stack Playwright` |

Confirm the displayed names from a completed run before selecting them in the
repository settings. GitHub exposes a workflow/job check name only after its
first run, and requiring a guessed name creates a rule that cannot be met.

## Recommended rule behavior

- Require a pull request before merging.
- Require the three checks above to pass; do not substitute deployment or
  uptime workflows for these product gates.
- Require the branch to be current before merging, so the checks cover the
  merge result rather than only an earlier head revision.
- Dismiss stale approvals when new commits arrive and require one approving
  review from someone other than the latest pusher.
- Restrict direct pushes to protected integration branches.

## Activation note

The E2E workflow deliberately fails when its local-stack browser gate fails
and uploads its HTML report only for that failure. At the time of this
recommendation, the workflow contract is verified but the application E2E
baseline has recorded accessibility failures. Resolve that application gate in
its owned UI lane before expecting the E2E check to permit a merge.

## Out of scope

Applying or changing branch-protection settings is an administrator action and
is intentionally outside Loop V29. This document is the handoff for that
separate action.
