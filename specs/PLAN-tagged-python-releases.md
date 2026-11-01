# Tagged Python package publication to Forgejo

Status: Approved
Date: 2026-11-01

Approval: The user explicitly replied "approve" to the complete PLAN approval presentation on 2026-11-01. Approval covers this complete plan and the incorporated plan-assurance dispositions. Implementation entry still requires a new session, cleared context, or explicit same-context consent under spec-plan.

## Authority and scope

Implement specs/SPEC-tagged-python-releases.md, complete effective revision A1, explicitly approved on 2026-11-01. The original Proposed document status is preserved; A1's approval record is authoritative. Earlier transceiver, receive and transmit SPEC/PLAN files remain immutable. Change packaging, release automation and associated documentation only; no RF testing or repair, deployment, image build, tag push, package upload, secret creation or remote reconfiguration during implementation.

## Workspace, base and delivery

- Invoking checkout: /home/alexbanica/workspace/rpi-cc1101-transciever, branch feature/cc1101-connection-test; preserve unrelated changes.
- Exact pinned source base: 9032aa8824c3502da37d96906cbabe705c23683f. Refresh origin/feature/cc1101-connection-test and require it still equals that base; mismatch requires amendment, never silently switch to main. Pin preserves the transceiver implementation being packaged.
- New delivery branch: feat/tagged-python-releases, destination origin/feat/tagged-python-releases. If that remote branch already exists, refresh it, reconcile prior authorized checkpoint ancestry and use it only for a verified resume; unexpected collision stops. New local branch must be absent and unattached before its first commit.
- Isolated worktree: /tmp/agent-worktrees/rpi-cc1101-transciever/tagged-python-releases, initially detached at the verified pinned base. Parent owns worktree/Git operations. Preserve invoking source state. Copy the approved pair byte-for-byte, retaining original content/index/HEAD state for verified restoration after delivery. Never discard concurrent edits.
- PLAN approval followed by valid implement entry authorizes accepted source/artifact commit and non-force push to the named feature branch, without routine continuation prompts. No main merge or actual tag/release publication follows. After verified push detach the clean retained worktree and restore only unchanged transferred artifacts in the invoking checkout. Missing/dirty/conflicting worktree states stop for safe DRAFT recovery; only exact registered-but-absent planned path may be non-forcibly deregistered and recreated.

## Implementation decisions

Use setuptools with pyproject.toml build-system metadata and existing setup.py. Add a small cc1101_transceiver/_version.py with the fallback 0.1.0 assignment, read as text by setup.py without importing runtime hardware. Build tagged releases in a temporary copied source tree; replace the version assignment there with the strictly parsed PEP 440 version. Include that file in sdist so rebuilding needs neither Git nor RELEASE_TAG. Never change the tracked version during release.

Keep distribution/import names and Python >=3.10. Add rpi-lgpio to package dependencies alongside cc1101==3.0.0 and spidev; declare cc1101-transceiver console entry point cc1101-transceiver = cc1101_transceiver.controllers.cli:main. Include README/license and explicit source inclusion; exclude credentials, Git/config directories, build output and unrelated project artifacts. Preserve standalone diagnostic and wrappers in the checkout; no new installed diagnostic command is required.

Create scripts/release_version.py for strict supported-tag parsing; scripts/package_artifacts.py for isolated tagged builds and artifact validation; scripts/publish_forgejo.py for credential-free publication preflight of only the validated pair. Only packaging code and helper scripts may change; no protocol/domain/runtime adapter logic changes. Helpers use stdlib plus build, packaging and twine from requirements-dev.txt; no bespoke HTTP upload implementation. Reject malformed tags, wrong name/version, extra/missing distributions and invalid metadata. Build/check subprocesses receive an environment with publication credentials removed. The workflow invokes the pinned twine CLI directly with credentials only in environment, a fixed HTTPS registry endpoint, no shell interpolation and no --skip-existing. Project helpers never execute while publication secrets are available. Failure is nonzero; no overwrite or automatic retry after partial upload. Report that partial registry publication may require operator reconciliation without deletion by the workflow.

Registry upload endpoint: https://forgejo.alexlab.nl/api/packages/public/pypi. Document the sibling consumption proxy https://pypi.alexlab.nl/simple/ and the direct Forgejo public index https://forgejo.alexlab.nl/api/packages/public/pypi/simple/ as alternatives; do not claim either was live-verified. Docker examples pin an exact version and obtain private project packages from the chosen private index separately from ordinary PyPI dependencies, avoiding private-package selection through an unordered --extra-index-url. Do not bake credentials into build arguments, URLs or image layers. Hardware execution remains separately configured by consumers.

## Units, ownership and sequence

| Unit | Role and exclusive owned paths | Prerequisite | Completion and validation |
| --- | --- | --- | --- |
| PKG-01 | developer: setup.py, pyproject.toml, MANIFEST.in, cc1101_transceiver/_version.py, requirements-dev.txt, scripts/release_version.py, scripts/package_artifacts.py, scripts/publish_forgejo.py, tests/test_release_packaging.py | Approved pair, prepared workspace, verified base | Build/version/publish behavior and meaningful offline tests of strict parsing, metadata validation, sdist rebuild, sanitized subprocess environments and duplicate-upload failure propagation |
| CI-01 | developer: .github/workflows/ci.yml, .github/workflows/publish.yml | PKG-01 integrated | CI on branch pushes/PRs; publish only on tag pushes and only after validated build, with isolated publication credentials |
| ASSURE-01 | independent code-reviewer, contract-reviewer, security-reviewer, then qa-agent; read-only entire integrated boundary | PKG-01 and CI-01 complete | Review correctness, packaging interface/version/dependencies, credential/artifact provenance and workflow trust; one consolidated correction batch and affected revalidation; final QA checks below |
| DOC-01 | documentation-writer: README.md | Final QA disposition and settled implementation | Tag-to-registry instructions, configuration secret names, asset/version examples, Docker installation and limitations match source |
| DELIVER-01 | parent only: approved pair, staged accepted paths and Git | All required checks, assurance, docs complete | Inspect staged diff; commit/push exact branch, verify remote SHA/upstream and workspace recovery |

Run developer units serially. At most three independent reviewers concurrently; no shared mutable environment or checks run concurrently. Every launched specialist has an ephemeral manifest, fixed ownership, supplied artifact hashes and a five-minute interruption limit; split bounded successors on timeout, never waive required review. Children never commit/push/worktree/deploy. Parent retains all remaining obligations after partial handoffs.

## Workflow shape and security

CI uses Python 3.10 and 3.13 on Ubuntu for repository checks and build/install smoke coverage. Release build uses Python 3.13, checks out the immutable github.sha from the tag-push event and verifies HEAD equals that event commit before building. Retain a credential-free provenance manifest containing event commit, original tag, normalized version and both artifact hashes; this manifest is a CI handoff artifact, not a third registry distribution. Pin actions to full commit SHAs verified from trusted upstream source at implementation; do not invent current versions. Disable persisted checkout credentials and set contents: read only. Use ordinary pull_request, never pull_request_target. Branch CI has no Forgejo secrets.

Tag filters cover stable, beta and optional v forms; strict helper validation is authoritative after broad GitHub glob matching. Pass tag via RELEASE_TAG environment rather than embedding expressions in shell source. Build job runs required checks and emits only validated wheel/sdist through workflow artifacts. Publish job depends on build, downloads only its own run's named artifact and provenance manifest, independently revalidates tag, metadata, hashes and event commit before the upload step, and receives FORGEJO_PACKAGE_USERNAME/TOKEN only on its direct twine upload step. The upload job does not install either distribution or execute project code with secrets. The credential-free preflight may check out the same event SHA to run the helper; it must finish before secrets enter scope. Serialize publication by tag with cancel-in-progress false. No workflow_dispatch publication or automatic tag creation. Publication trusts repository maintainers authorized to push eligible GitHub tags and their reviewed workflow content, matching the sibling model; step scoping alone is not protection against a malicious authorized workflow change. Document tag/branch protection and least-privilege package tokens as administrator prerequisites, without configuring remote rules or environments during this change. Do not claim those hosted controls were verified; repository credential administrators retain that trust decision. Exact dependency/action versions are implementation details verified before pinning; no new behavior or remote authority follows from that verification.

## Validation, assurance and recovery

Full assurance profile: executable CI, credentials, package supply chain and changed external installation interface trigger code, security and contract reviews plus final independent QA and documentation writer. Review frozen integrated diff against approved effective pair; reconcile supported findings once, apply consolidated accepted in-scope corrections and revalidate. Additional full cycles only for qualifying confirmed failures as defined by implement. No runtime RF QA is applicable.

Required local commands:

```sh
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

In a disposable tooling venv install requirements-dev.txt. Run python -m build and python -m twine check on the distributions. Exercise release helpers offline for representative stable, v-prefixed and beta tags plus invalid cases. Inspect wheel METADATA, sdist PKG-INFO, names and contents; rebuild extracted sdist outside Git and compare version. Install wheel with --no-deps into a fresh venv, from outside the checkout run cc1101-transceiver --help and python -m cc1101_transceiver --help. This does not verify native dependency installation; validate declared dependency metadata separately and disclose the distinction. Validate workflow YAML with an Actions-aware parser/actionlint when available and inspect job/secret/artifact boundaries. If actionlint unavailable use parsed YAML plus explicit structural checks and record the precise evidence limit rather than claim linter execution.

No upload to registry, live tag push, RF command or Docker deployment during validation. Hosted success, registry/proxy reachability, runner/secrets and native container hardware operation stay explicitly unverified, outside this implementation acceptance. Missing network access for required tooling/action verification, unavailable required roles or failed required checks are genuine blockers: finish safe independent work, retain evidence, deliver authorized DRAFT if possible, enumerate unmet criteria. Never invent successful publication. Missing publication secrets alone do not block local delivery because actual publication is excluded.

## Requirement-to-delivery trace

| Effective SPEC anchor | Units / paths | Evidence |
| --- | --- | --- |
| Release behavior 1–2 and A1 execution destination | PKG-01 helpers; CI-01 workflows | Tag parser tests, exact-ref checkout and no-publish CI inspection |
| Release behavior 3; A1 publication pair, duplicate handling | PKG-01 artifact/publish helpers; CI-01 publish job | One wheel/sdist, canonical metadata, mocked failure/duplicate behavior, no live upload |
| Release behavior 5 as replaced by A1 | CI-01 workflows; ASSURE-01 | No PR secrets/publication; step-scoped secrets, read-only permissions, isolated build and publisher |
| Installed package behavior, all bullets | PKG-01 packaging and version file | Metadata/dependencies, archive contents, sdist rebuild, out-of-tree console/module smoke |
| Documentation and Docker consumption as replaced by A1 | DOC-01 README.md | Pinned package install example, registry/index paths and prerequisites; no Docker build |
| Acceptance repository checks and tag/build/metadata criteria | PKG-01, CI-01, ASSURE-01 | Required commands, offline cases, metadata checks, install/rebuild |
| Acceptance workflow static checks and hosted boundary | CI-01, ASSURE-01, DOC-01 | Workflow inspection plus explicit hosted evidence exclusions |
| Prior-spec preservation, runtime invariants and no publication authority | All units; parent diff review | Unchanged old artifacts/runtime files; no live RF/tag/upload/remote edits |

## Plan assurance

Both required roles independently reviewed the complete initial PLAN (SHA-256 b74869a9629a7bc24cf77411c4b98c5788b254fa204fe56cbf4a137d9cef5e96) against approved effective SPEC A1 (SHA-256 094a508a8cdb558d92e9466ce70dd2fe8286f9da115284c3b6dbaef6014586ce) and current repository evidence at 9032aa8. Their findings are advisory, not approval.

- Explorer release-plan-explore: covered packaging/rebuild, CI, credentials, delivery base and artifact identity. Accepted provenance gap: pin checkout to github.sha, verify HEAD and bind artifact hashes/tag/version to the same event commit in the handoff manifest. Accepted trust-boundary concern: direct twine-only secret-bearing step, preflight without secrets, no execution of distributed/project code with credentials, and explicit maintainer-tag/workflow trust plus unverified administrator controls. No new remote security configuration is authorized.
- Architect release-plan-arch: covered architecture, interfaces, integration, ownership and compatibility. Corrected its supported entry-point finding to cc1101_transceiver.controllers.cli:main; retain out-of-tree smoke checks.
- Parent incorporated all supported findings into this final proposed PLAN. Static assurances do not establish hosted secrets, protection rules, registry behavior or publication success.

## Definition of Done and terminal evidence

Complete approved implementation, independent reviews and accepted fixes, required checks, final QA and documentation. Parent verifies scope, artifact bytes and final staged content; commits accepted source plus approved pair and pushes origin/feat/tagged-python-releases. Verify actual remote commit equality and upstream destination, clean delivery worktree/detachment, and invoking checkout recovery while preserving unrelated work. Summarize local acceptance separately from unperformed hosted publication. Intermediate handoffs/checkpoints are not completion or continuation gates. End only with complete authorized lifecycle or evidenced blocked DRAFT with exact remaining work.

## Execution amendment A1 — 2026-11-01

Authorization: the originating implementation request explicitly instructs “use the same invoking checkout and commit and push against the same branch”. This supersedes only the planned workspace and Git destination. Execute in /home/alexbanica/workspace/rpi-cc1101-transciever on feature/cc1101-connection-test; commit and non-force push accepted paths to origin/feature/cc1101-connection-test. Do not create a worktree, branch or PR, detach, remove the invoking checkout, or restore its approved artifacts. The pinned base 9032aa8824c3502da37d96906cbabe705c23683f was verified equal to HEAD and the refreshed remote branch. Existing untracked files are the approved pair and are accepted delivery paths. All product behavior, exclusions, units, assurance and validation remain unchanged. This complete effective PLAN revision is authorized by the explicit user override and the active implement amendment procedure. Final evidence requires remote/upstream equality and a clean invoking checkout.

## Execution evidence — 2026-11-01

- PKG-01 implemented package metadata, text-read fallback version, strict tag helpers, temporary source build, credential-free artifact/provenance validation and regression tests. CI-01 implemented Python 3.10/3.13 branch/PR CI and Python 3.13 exact-event tag publication with secret-scoped direct Twine upload. No runtime/domain/protocol changes.
- Independent CODE and CONTRACT reviews found overlapping dependency-prefix validation defects; CODE also demonstrated metadata description/header confusion. Accepted consolidated correction: parse email headers separately from description and parse exact unconditional dependency requirements. Added negative version/name/marker and description-body regressions. Added offline execution of the workflow upload command with a failing duplicate-upload stub, proving nonzero failure propagation without registry access. SECURITY completed with no findings under the approved maintainer-tag/workflow trust boundary.
- Final independent QA completed after corrections: 54 tests pass; both fallback 0.1.0 and tagged 1.2.3b1 pairs pass metadata validation and Twine checks; rebuilt sdist wheel passes Twine and retains 1.2.3b1 outside Git; installed wheel console and module help pass. Native dependencies were deliberately not installed for the --no-deps smoke check. Compileall, wrapper shell syntax and git diff --check pass.
- Commands: python3 -m compileall cc1101_transceiver cc1101_connection_test.py; python3 -m unittest discover -s tests -p 'test_*.py'; bash -n run.sh; bash -n run_cc1101_connection_test.sh; git diff --check. Disposable /tmp/cc1101-release-tools installed pinned requirements-dev tools; python -m build validated fallback, scripts/package_artifacts.py --tag v1.2.3-beta1 --commit 9032aa8824c3502da37d96906cbabe705c23683f built a beta pair in /tmp; python -m twine check validated each distribution; scripts/publish_forgejo.py independently checked provenance. Extracted beta sdist rebuilt with python -m build --wheel outside Git. Fresh /tmp/cc1101-smoke venv installed wheel --no-deps; both help commands ran from /tmp.
- actionlint unavailable: parsed both workflow YAML files and checked read-only permissions, full-length action pins, ordinary pull_request and secret references exclusively on the direct upload step. This is static structural evidence, not actionlint or hosted success.
- Action pins verified directly with git ls-remote against https://github.com/actions/{checkout,setup-python,upload-artifact,download-artifact}.git: checkout v7.0.1 3d3c42e5aac5ba805825da76410c181273ba90b1; setup-python v7.0.0 5fda3b95a4ea91299a34e894583c3862153e4b97; upload-artifact v7.0.2 cf430e030ddbb5b0abf93d22962f4752f3646cd9; download-artifact v7.0.0 37930b1c2abaa49bbe596cd826c3c89aef350131. Tool versions build 1.6.1, packaging 26.3 and twine 7.0.0 verified against PyPI before pinning.
- Actual publication, tag push, registry/proxy connectivity, hosted runners/secrets/protection controls, native dependency installation, Docker operation and hardware/RF acceptance were not performed and are outside implementation acceptance. No new execution authority is implied by these checks.
- A1 is the sole implementation amendment, authorized by the originating user's explicit checkout/branch override. Review and QA covered that effective revision; earlier artifact content/status and product scope remain preserved.
- DOC-01 writer synchronized README publication, registry/Docker consumption and trust/acceptance limits. Parent checked it against source and added exact distribution filenames. Final stable 1.2.3 build from the documented source passed Twine and provenance preflight; tracked fallback remains 0.1.0. Full local Definition of Done is satisfied; authorized same-branch commit/push verification follows this receipt. No claim of hosted publication is made.
