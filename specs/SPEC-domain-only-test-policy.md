# Domain-only automated test policy

Status: Approved

## Purpose

Record the delivered repository guidance that automated tests belong only to
deterministic domain source logic.

## Requested behavior

- Tests of every kind are restricted to domain source logic.
- Infrastructure, Docker, GitHub Actions and other CI/CD, deployment,
  configuration, packaging, tooling, presentation, orchestration, and other
  non-domain code must not receive automated tests.

## Scope

- Root `AGENTS.md` contributor guidance.
- This completed-work spec and its matching plan.

## Out of scope

- Production-code changes.
- Adding, changing, or deleting existing test implementations.
- Runtime, deployment, or CI changes.

## Definition

`Domain source logic` means deterministic project business rules implemented in
the repository's domain source layer, independent of infrastructure, framework,
transport, presentation, orchestration, configuration, and operational code.

## Inputs and constraints

- Preserve unrelated local work.
- Deliver from the newest fetched remote default branch.
- Use short documentation validation only under the requested `$super-agent`
  workflow.

## Deterministic behavior delivered

- `AGENTS.md` restricts all automated tests to domain source logic.
- `AGENTS.md` enumerates representative non-domain areas where tests are
  prohibited.
- `AGENTS.md` directs contributors to non-test validation for those areas.
- Projects without domain source logic mark automated testing and test-first
  work as not applicable.

## Assumptions and impact

- Existing non-domain tests are not removed by this documentation-only change.
- Future contributors must apply the stricter domain-only policy even when
  older general test instructions remain elsewhere in repository history.

## Validation performed

- Inspected the documentation diff.
- Ran `git diff --check` for the delivered paths.

## Validation skipped

- Builds and test suites were skipped because production behavior did not
  change and the direct workflow permits only short validation.
- Independent QA and code review were skipped by the `$super-agent` workflow.

## Documentation changes

- Updated root `AGENTS.md`.
- Added this completed-work spec and its matching completed-work plan.
