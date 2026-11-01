# Tagged downloadable Python releases

Status: Proposed
Date: 2026-11-01

## Purpose and authority

The user requested GitHub workflows similar to the other Python projects so a tag produces a downloadable Python package suitable for installation in a Docker image. This SPEC defines new release behavior; it does not authorize creating a tag or publishing a release during implementation.

Research base: feature/cc1101-connection-test at 9032aa8824c3502da37d96906cbabe705c23683f. Existing setup.py fixes the version at 0.1.0, has no console entry point, and omits rpi-lgpio from installation dependencies. No GitHub workflow exists.

## Relationship to previous specifications

Preserve specs/spec-cc1101-somfy-rts-transceiver.md, specs/spec-gdo0-backed-pulse-capture.md and specs/spec-gdo0-backed-somfy-rts-emitter.md unchanged. Extend distribution and installation only. Preserve protocol, GPIO/SPI defaults, receive/transmit semantics, capture/profile formats and the standalone connection diagnostic. This work does not repair or establish live transmission acceptance.

## Release behavior

1. Pushing a stable tag X.Y.Z or beta tag X.Y.Z-betaN triggers validation, package build and GitHub Release publication for that exact tagged commit. Also accept an optional leading v. X, Y and Z are nonnegative integers without redundant leading zeros; N is a positive integer. Other tags do not publish packages. A malformed release candidate selected by a broad trigger must fail clearly before publication.
2. Convert the tag to the corresponding PEP 440 package version: 1.2.3 or 1.2.3b1, stripping an optional v. The built wheel and source archive metadata must agree with the tag; do not change tracked source versions or create commits during release.
3. Produce one platform-independent wheel for this Python package and one source archive. Native dependencies remain separately installed dependencies; this wheel does not bundle native libraries or claim to be a complete offline installation.
4. Publish both distributions and a SHA256SUMS file as assets of the GitHub Release named for the original tag. Beta tags produce prereleases; stable tags produce ordinary releases. Publish only after all required validation succeeds. Build from the tagged commit, never a mutable branch head. Avoid overwriting an existing published release or its assets; a duplicate publication fails clearly.
5. Run validation and build checks for pull requests and branch pushes without publishing. Grant release write permission only to the publishing job. No PyPI credentials or publication are required.

## Installed package behavior

- Preserve distribution name rpi-cc1101-transciever and import name cc1101_transceiver, Python >=3.10, and cc1101==3.0.0. Declare the existing runtime dependencies spidev and rpi-lgpio so package installation includes the dependencies presently provided by requirements.txt.
- Provide a cc1101-transceiver console command equivalent to python -m cc1101_transceiver. Preserve the module entry point and existing repository wrappers.
- Include package sources, README and license in the distributions, with a declared modern build backend. The source archive must rebuild into a wheel with the same release version without a Git checkout or network-based version lookup.
- An untagged local checkout remains buildable using the existing fallback version 0.1.0; release versions must not silently fall back when tag parsing fails.

## Documentation and Docker consumption

Document tag formats, pushing an example tag, workflow/release location, expected asset names and a tag-specific GitHub release download URL. Include a Dockerfile installation snippet using the wheel URL and python -m cc1101_transceiver --help, with a pinned release version. Explain that live hardware use additionally needs compatible Raspberry Pi system dependencies and SPI/GPIO device access. Do not add a Docker image build, container deployment, hardware permission automation, or claim container hardware operation was validated.

## Acceptance and validation

- Required repository checks pass: compileall, unittest discovery, bash syntax checks for both wrappers, git diff --check.
- Stable, optional-v and beta tag version parsing is checked; malformed tags are rejected without publication. Verify metadata inside both built distributions agrees with the requested version.
- Build an sdist and wheel with python -m build, validate distribution metadata, rebuild a wheel from an extracted sdist without .git, and verify matching versions.
- Install the built wheel in an isolated environment and verify console and module --help from outside the checkout. Hardware-free verification may use --no-deps where native dependency installation is unavailable; disclose that limitation separately from metadata/dependency checks.
- Statically validate workflow triggers, job dependencies, permissions, artifact selection, failure behavior and exact-tag checkout. No receive/transmit hardware testing is required for this packaging-only change.
- Actual hosted execution and release asset download remain unverified until an explicitly authorized tag is pushed. Local success must not be represented as a published release.

## Evidence and conventions

Sibling references inspected read-only: RpiEPaper/AGENTS.md and scripts/release_version.py; rpi-groove-ir-emitter/scripts/publish_forgejo.py. These use X.Y.Z and X.Y.Z-betaN with PEP 440 beta normalization, but target Forgejo rather than GitHub releases.

Primary references: https://packaging.python.org/en/latest/discussions/setup-py-deprecated/ ; https://packaging.python.org/en/latest/flow/ ; https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases ; https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases .

## Amendment 1 — 2026-11-01 — Match sibling Forgejo package publication

- Amendment ID: SPEC-tagged-python-releases-A1
- Previous version: original Proposed body above
- Approval: Approved for the complete effective specification
- Request and purpose: The user clarified Forgejo as the package destination and selected "same as sibling projects" after presentation of GitHub Actions publishing to Forgejo versus native Forgejo Actions. No release implementation or publication is authorized by this proposed amendment.

### Changes against the previous version

| Section / requirement | Before | After | Reason |
| --- | --- | --- | --- |
| Purpose and authority | Downloadable GitHub Release assets | GitHub Actions builds packages on GitHub tag pushes and publishes them to the Forgejo PyPI package registry, matching the sibling projects | Explicit user selection |
| Release behavior 1 | Tag pushes trigger GitHub Release publication | Tag pushes to GitHub trigger validation, package build and Forgejo PyPI publication; pushing a tag only to Forgejo does not trigger this workflow | Match sibling workflow execution |
| Release behavior 4 | Distributions and SHA256SUMS attached to a GitHub Release; prerelease flag for beta | Publish exactly the validated wheel and source archive to https://forgejo.alexlab.nl/api/packages/public/pypi, using canonical PEP 440 versions. No GitHub or Forgejo repository Release, release attachments, or checksum asset is required. Beta identity is encoded in the package version. Preserve existing published versions; duplicate publication must fail rather than overwrite | Match sibling package registry destination |
| Release behavior 5 | Release write permission for publishing job, no PyPI credentials | Use GitHub Actions with minimal read-only repository permissions. Publishing job receives only the configured FORGEJO_PACKAGE_USERNAME and FORGEJO_PACKAGE_TOKEN secrets after successful validation/build. No GitHub write permission, public PyPI publication or credentials are required. PR and branch validation must not publish or require these secrets | Match sibling authentication while limiting effects |
| Documentation and Docker consumption | GitHub release download URL and wheel URL in Dockerfile | Document the Forgejo registry and exact-version pip installation using its /simple index, suitable for a Dockerfile; show supported stable and beta tags, the GitHub tag-push trigger, expected distribution names, secret names, and local authenticated configuration where required. Never embed credentials in examples or Docker image layers | Install the package in the same way as siblings |
| Hosted acceptance | Release-asset download after authorized tag push | Package availability and installation from the Forgejo registry remain unverified until a separately authorized tag push executes the hosted workflow | Truthful publication boundary |
| Evidence correction | Earlier research stated no sibling GitHub release workflows | RpiEPaper/.github/workflows/publish.yml and rpi-groove-ir-emitter/.github/workflows/publish.yml do exist and run on GitHub tag pushes to publish into Forgejo. Earlier absence conclusion was incorrect | Subsequent direct inspection corrected the evidence |

### Preserved behavior and impact

All unmodified original requirements remain effective: supported stable/beta tags and optional v prefix; strict tag/version validation; matching wheel/sdist metadata; one platform-independent wheel and one sdist; deterministic sdist rebuild without Git; existing package/import names and Python compatibility; runtime dependency alignment; console and module entry points; repository wrappers and diagnostic; validation without RF actions; no Docker image build or deployment. No tag, remote change, package upload or credential creation is authorized during implementation. Earlier project SPEC/PLAN artifacts stay unchanged. This amendment supersedes every original reference to release creation, release assets, release write permission and tag-specific release URLs.

Local build and installation checks plus static workflow validation establish implementation evidence. Hosted registry availability, secrets, credentials, runner operation and actual publication must be reported separately; never infer those from local success. Registry consumption examples must explain native dependency and hardware access prerequisites. No PLAN exists yet.

Primary platform references: https://forgejo.org/docs/latest/user/packages/pypi/ ; https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows . Sibling scripts and workflows are local convention evidence, not proof of currently successful hosted execution.

### Approval record

Approved by the user on 2026-11-01 with "approve", in response to the revised specification approval presentation. Approval covers the original specification as modified by SPEC-tagged-python-releases-A1. Document-level Status remains Proposed to preserve the original body; this amendment records the effective approval.
