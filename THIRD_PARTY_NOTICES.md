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

## Python backend dependencies

`apps/backend/pyproject.toml` declares the direct dependencies and `apps/backend/uv.lock`
pins the resolved versions. Licenses below were read from the installed packages'
`*.dist-info` metadata (`License` / `License-Expression` / classifiers) and the bundled
`licenses/` texts; the full provenance table with per-package evidence lives in
`docs/08-data-and-license-log.md`.

Runtime dependencies are distributed as part of the local backend runtime:
alembic 1.18.5 (MIT), fastapi 0.139.0 (MIT), pydantic 2.13.4 (MIT), psycopg[binary] 3.3.4
(LGPL-3.0-only; used unmodified via the official wheel — review LGPL-3.0 obligations before
any redistribution), python-dotenv 1.2.2 (BSD-3-Clause), SQLAlchemy 2.0.51 (MIT),
uvicorn[standard] 0.51.0 (BSD-3-Clause), and pwdlib[argon2] 0.3.0 (MIT).

Development dependencies (httpx, pytest, pytest-asyncio, ruff) are not distributed with any
runtime or release artifact.

The optional dependency groups `vision` (opencv-python, mediapipe) and `llm` (openai) are
declared and locked but are NOT installed, NOT enabled, and NOT distributed by this
repository. Before enabling or distributing any of them, verify the installed wheel's
license evidence and update `docs/08-data-and-license-log.md` and this file.

### pwdlib

pwdlib 0.3.0 is MIT licensed. Its installed metadata declares the license only through
`Classifier: License :: OSI Approved :: MIT License`; the `License` and
`License-Expression` metadata fields are undeclared. The license text bundled as
`pwdlib-0.3.0.dist-info/licenses/LICENSE` is reproduced below.

```text
MIT License

Copyright (c) 2024, François Voron

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
