# Third-party notices

## TheMasterplan workflow materials

The workflow rule files `core/`, `profiles/`, `adapters/generic.md`, `docs/release-channels.md`,
and the client skill entry `.reasonix/skills/themasterplan/` are adopted from
[TheMasterplan](https://github.com/OasisSaber/TheMasterplan) `v3.0.0`, commit
`6e49aeeaa2eeaa8ce9be2d81a2fa8f5ba88bef18`, as a full-template adoption. The project
verification entry was mapped to this repository's real entry (`bash scripts/validate.sh`
via Git Bash on Windows); no non-existent validation entry is referenced.

## AgenticWonderwall workflow materials

The pull-request-body validator, Markdown-link validator, and their tests in `scripts/validate_pr_body.py`, `scripts/test_validate_pr_body.py`, `scripts/validate_markdown_links.py`, and `scripts/test_validate_markdown_links.py` are adapted from [OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall), commit `689d4edb8aacc1fc7a277da89efed05199b75edb`.

The complex-task Issue Form, selected Jujutsu lifecycle guidance, pull-request validation hardening, and CI hardening were selectively synchronized from the same project at commit `794b083e816e84f271e991aed84a5a5f4e9c74fc`. They were adapted to preserve this repository's HMI-specific authority, validation command, and platform evidence. TheMasterplan is the successor brand and version of the same workflow line.

Those derived materials are provided under the source project's MIT License. This notice does not grant a license for the Supersonic project as a whole; see [README.md](README.md) for this repository's license boundary.

## Ultralytics / YOLO (reserved optional dependency; not adopted)

Ultralytics/YOLO has been removed from the `vision` optional dependency group in
`apps/backend/pyproject.toml` and from `apps/backend/uv.lock`. The current source tree does
not import or call Ultralytics/YOLO, contains no Ultralytics model weights, and does not
distribute a runtime or release artifact that includes it.

Before adding the dependency, YOLO code or models, or distributing a build that contains
them, record the exact package/model versions, provenance, license text and permission
evidence in `docs/08-data-and-license-log.md`. The official licensing route
must be chosen and documented first: AGPL-3.0 with the corresponding whole-project source
obligations, or an applicable Ultralytics Enterprise/R&D license. See the
[Ultralytics licensing page](https://www.ultralytics.com/license). This repository's
current no-license-grant statement does not resolve that future decision.
