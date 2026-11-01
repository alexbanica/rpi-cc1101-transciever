# Resolve merge conflicts

Status: Approved

## Authority and purpose

The user requested: "$super-agent fix the merge conflicts in this repo. Use everything from the current branch". This records the directly authorized lower-assurance resolution on 2026-10-28.

## Delivered behavior and scope

Resolve the active merge conflicts in AGENTS.md and README.md by retaining each entire current-branch (Git index stage 2) file. Current branch is feature/cc1101-connection-test, HEAD 7ad91b794ad01e8695936acc7538ff731b5803a6; incoming merge head is 4523f3384c2187ce3d1df99f9a8af9d6752e7c3f. No runtime behavior or earlier specification is changed. Other files are outside scope.

## Constraints and assumptions

This is an ordinary merge, so stage 2 is the current branch. Preserve the pending merge and stage the resolution. Commit, push, deployment, and hardware validation are outside scope.

## Validation and documentation

Verify resolved files match HEAD, no unmerged entries remain, and working/staged diffs pass git diff --check. Only documentation and merge-index state change. This SPEC and its matching PLAN document the resolution. Automated tests are inapplicable to this documentation-only resolution. QA, independent review, runtime/hardware validation, and longer checks are skipped under super-agent.
