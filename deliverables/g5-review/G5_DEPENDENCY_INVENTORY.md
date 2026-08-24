# G5 Dependency Inventory

Inventory for [Issue #65](https://github.com/OasisSaber/Supersonic/issues/65), baseline
`main@7e1ea06e52964b09c8368943236847525a7deccc`.

Versions are taken from `apps/backend/uv.lock`, `pnpm-lock.yaml`, and installed package
metadata where applicable. No absolute install paths are recorded.

## Python direct dependencies

| Package | Declared range | Locked | Purpose | License / provenance status | Lifecycle |
| --- | --- | ---: | --- | --- | --- |
| alembic | `>=1.18.5,<1.19` | 1.18.5 | PostgreSQL migrations | MIT; declared and locked | runtime |
| fastapi | `>=0.116.0,<1.0` | 0.139.0 | HTTP/WebSocket API | MIT; declared and locked | runtime |
| pydantic | `>=2.11.0,<3.0` | 2.13.4 | Contract/model validation | MIT; declared and locked | runtime |
| psycopg[binary] | `>=3.3.4,<3.4` | 3.3.4 | PostgreSQL driver | LGPL-3.0-only; declared and locked | runtime |
| python-dotenv | `>=1.1.0,<2.0` | 1.2.2 | Environment loading | BSD-3-Clause; declared and locked | runtime |
| sqlalchemy | `>=2.0.51,<2.1` | 2.0.51 | Persistence/UoW ORM | MIT; declared and locked | runtime |
| uvicorn[standard] | `>=0.35.0,<1.0` | 0.51.0 | ASGI server | BSD-3-Clause; declared and locked | runtime |
| pwdlib[argon2] | `>=0.3,<1.0` | 0.3.0 | Password hashing | MIT (bundled `LICENSE`); installed metadata License/License-Expression fields undeclared; notice review required | runtime |
| mediapipe | `>=0.10.21,<1.0` | 0.10.35 | Optional vision | Declared and locked; license log/notice incomplete per G5-LIC-001; not currently distributed | optional |
| openai | `>=1.93.0,<2.0` | 1.109.1 | Optional LLM integration | Declared and locked; license log/notice incomplete per G5-LIC-001; not currently distributed | optional |
| opencv-python | `>=4.11.0,<5.0` | 4.13.0.92 | Optional vision | Declared and locked; license log/notice incomplete per G5-LIC-001; not currently distributed | optional |
| httpx | `>=0.28.0,<1.0` | 0.28.1 | HTTP test client | BSD-3-Clause; declared and locked | dev |
| pytest | `>=8.4.0,<9.0` | 8.4.2 | Python test runner | MIT; declared and locked | dev |
| pytest-asyncio | `>=1.0.0,<2.0` | 1.4.0 | Async pytest support | Apache-2.0; declared and locked | dev |
| ruff | `>=0.12.0,<1.0` | 0.15.21 | Python linting | MIT; declared and locked | dev |

Sources: `apps/backend/pyproject.toml`, `apps/backend/uv.lock`,
`THIRD_PARTY_NOTICES.md`, `docs/08-data-and-license-log.md`.

## Node direct dependencies

The root `concurrently` entry and every `apps/frontend/package.json` direct entry are listed
individually. Licenses are from installed package metadata and the lockfile provides resolved
versions/integrity.

| Package | Declared range | Locked / installed | Purpose | License / provenance status | Lifecycle |
| --- | --- | ---: | --- | --- | --- |
| concurrently | `^9.2.0` | 9.2.4 | Run backend/frontend together | MIT; package metadata + lock | dev |
| @react-three/drei | `^10.7.7` | 10.7.7 | 3D React helpers | MIT; package metadata + lock | runtime |
| @react-three/fiber | `^9.6.1` | 9.6.1 | React 3D renderer | MIT; package metadata + lock | runtime |
| @vitejs/plugin-react | `^4.6.0` | 4.7.0 | Vite React transform | MIT; package metadata + lock | runtime |
| echarts | `^5.6.0` | 5.6.0 | Charts/visualization | Apache-2.0; package metadata + lock | runtime |
| framer-motion | `^12.23.0` | 12.42.2 | UI motion | MIT; package metadata + lock | runtime |
| lucide-react | `^0.525.0` | 0.525.0 | UI icons | ISC; package metadata + lock | runtime |
| react | `^19.1.0` | 19.2.7 | UI runtime | MIT; package metadata + lock | runtime |
| react-dom | `^19.1.0` | 19.2.7 | DOM renderer | MIT; package metadata + lock | runtime |
| three | `^0.185.1` | 0.185.1 | 3D primitives | MIT; package metadata + lock | runtime |
| zustand | `^5.0.6` | 5.0.14 | Client UI store | MIT; package metadata + lock | runtime |
| @eslint/js | `^9.31.0` | 9.39.5 | ESLint config | MIT; package metadata + lock | dev |
| @testing-library/jest-dom | `^6.6.3` | 6.9.1 | DOM assertions | MIT; package metadata + lock | dev |
| @testing-library/react | `^16.3.0` | 16.3.2 | React component tests | MIT; package metadata + lock | dev |
| @types/react | `^19.1.8` | 19.2.17 | React TypeScript types | MIT; package metadata + lock | dev |
| @types/react-dom | `^19.1.6` | 19.2.3 | DOM TypeScript types | MIT; package metadata + lock | dev |
| autoprefixer | `^10.4.21` | 10.5.2 | CSS post-processing | MIT; package metadata + lock | dev |
| eslint | `^9.31.0` | 9.39.5 | JS/TS linting | MIT; package metadata + lock | dev |
| eslint-plugin-react-hooks | `^5.2.0` | 5.2.0 | React hooks linting | MIT; package metadata + lock | dev |
| eslint-plugin-react-refresh | `^0.4.20` | 0.4.26 | React refresh linting | MIT; package metadata + lock | dev |
| globals | `^16.3.0` | 16.5.0 | ESLint globals | MIT; package metadata + lock | dev |
| jsdom | `^26.1.0` | 26.1.0 | Browser test environment | MIT; package metadata + lock | dev |
| postcss | `^8.5.6` | 8.5.19 | CSS transformation | MIT; package metadata + lock | dev |
| tailwindcss | `^3.4.17` | 3.4.19 | CSS utilities | MIT; package metadata + lock | dev |
| typescript | `~5.8.3` | 5.8.3 | Type checking | Apache-2.0; package metadata + lock | dev |
| typescript-eslint | `^8.38.0` | 8.64.0 | TypeScript ESLint tooling | MIT; package metadata + lock | dev |
| vite | `^7.0.4` | 7.3.6 | Frontend build/dev server | MIT; package metadata + lock | dev |
| vitest | `^3.2.4` | 3.2.7 | Frontend test runner | MIT; package metadata + lock | dev |

Sources: `package.json`, `apps/frontend/package.json`, `pnpm-lock.yaml`, and installed direct
package metadata. The manifests and lockfile are aligned for these direct entries.

## Boundary checks

- No `ultralytics` dependency is present in `apps/backend/pyproject.toml`, `apps/backend/uv.lock`, `package.json`, `apps/frontend/package.json`, or `pnpm-lock.yaml`.
- No CDN or runtime-injected package was identified in the reviewed manifests or frontend source.
- Optional Python vision/LLM packages are declared and locked but are not currently distributed;
  their incomplete notice/log provenance remains G5-LIC-001 and is not an accepted limitation.
- `pwdlib` remains flagged for undeclared installed-metadata License/License-Expression fields
  despite its bundled MIT `LICENSE`; this inventory does not silently convert that gap into a pass.

Current verdict remains `CHANGES_REQUIRED`; no accepted limitation is granted.
