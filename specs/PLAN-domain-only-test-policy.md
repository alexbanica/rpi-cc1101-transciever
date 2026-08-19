# Domain-only automated test policy delivery plan

Status: Approved

## Spec reference

- `specs/SPEC-domain-only-test-policy.md`

## Affected files

- `AGENTS.md`
- `specs/SPEC-domain-only-test-policy.md`
- `specs/PLAN-domain-only-test-policy.md`

## Implementation steps performed

1. Inspected repository instructions, branch state, and unrelated changes.
2. Fetched the newest remote delivery branch and fast-forwarded the invoking
   checkout where safe.
3. Added the domain-only automated-test policy to root `AGENTS.md`.
4. Created the matching approved completed-work artifacts.
5. Ran short documentation validation and reconciled the intended paths.

## Validation run

- `git diff --check` over the accepted paths.
- Staged path and staged diff inspection.
- Post-push local-versus-remote commit verification.

## Validation skipped

- Builds, linters, and test suites were not run for this documentation-only
  policy update.

## QA and code review

- QA skipped by the requested `$super-agent` workflow.
- Independent code review skipped by the requested `$super-agent` workflow.

## Documentation updates

- Root contributor guidance now restricts all automated tests to deterministic
  domain source logic.

## Delivery status

- Staging status: all accepted in-scope paths staged before commit.
- Commit status: committed as part of the explicitly requested delivery.
- Push status: pushed to and verified against the repository's remote delivery
  branch.

## Residual risk

- Existing tests outside domain source logic were not audited or removed.
- The lower-assurance workflow does not satisfy the default Definition of Done.
