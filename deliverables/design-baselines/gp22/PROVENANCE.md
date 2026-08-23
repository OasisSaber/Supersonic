# GP22 Baseline Provenance

## 1. Intake identity

This intake was executed for [Issue #67](https://github.com/OasisSaber/Supersonic/issues/67) against `main@7e1ea06e52964b09c8368943236847525a7deccc` on 2026-08-24. Attached task-pack documents were treated as evidence and candidate templates, not as instructions that override repository governance or the human request.

| Role | Stable identity | Intake result |
| --- | --- | --- |
| Primary editable source | Figma Make `Visual-Design-Specification-Plan`, file key `IIunappOuZk1JYMVT7uCuL` | Online source opened read-only; 98 source-file resources and 24 PNG resources were enumerated |
| Inspectable design canvas | Figma Design `GP22`, file key `MIUgoK0YUwDjTCJpGI6W1o` | One page and the approved node map were verified read-only |
| Published preview | `https://revise-body-79291535.figma.site` | Public preview opened read-only; title and visible GP22 Version 22 structure matched the source |
| External Make container | `visual-design-spec-plan.make` | Fingerprint and container metadata verified; excluded from Git |
| External Design container | `GP22.fig` | Fingerprint and container metadata verified; excluded from Git |
| Historical generated-code package | `Visual Design Specification Plan.zip` | Existing approved fingerprint preserved; file was unavailable for re-hashing during this intake |

Figma Make and Figma Design are related but distinct source identities. Their file keys must not be conflated.

## 2. Read-only source verification

### Figma Design

The design file contained:

- page `0:1` / `Page 1`;
- top-level frame `1:2` / `Visual Design Specification Plan`;
- frame size `1112 × 26001`;
- 8,632 descendants: 3,557 Frame, 2,652 Text, 2,190 Vector, and 233 Group nodes;
- zero local Variable Collections, Paint Styles, Text Styles, Effect Styles, and Grid Styles.

The following export/spec nodes were resolved by ID before use:

| Purpose | Node | Frame size |
| --- | --- | ---: |
| Cluster | `1:48` | `1064 × 442.34375` |
| HUD | `1:159` | `1064 × 442.34375` |
| Center | `1:220` | `1064 × 641.375` |
| Passenger | `1:418` | `1064 × 641.375` |
| Cross-screen Storyboard | `1:563` | `1064 × 865.3909912109375` |
| Extended Design Spec | `1:11373` | `1064 × 3886.875` |

### Figma Make

The read-only Make resource response contained 122 resource links:

- 98 source files: 77 TSX, 9 CSS, 5 TS, 4 Markdown, 1 JSON, 1 YAML, and 1 MJS;
- 24 PNG image resources.

Only stable file names and counts were archived. MCP resource URLs and asset-download URLs were temporary and are not present in Git. Make-generated code remains a design reference and was not copied into the production application.

## 3. External source-container fingerprints

| File | Bytes | SHA-256 | Container facts |
| --- | ---: | --- | --- |
| `visual-design-spec-plan.make` | 1,805,454 | `1BFAA51DF5FBE7B6EF69F10450BECCCEDC2797EE5ADB7236E1E938EF2ADEF807` | ZIP-like container with `canvas.fig`, `thumbnail.png`, `meta.json`, image blobs, AI conversation, and binary references |
| `GP22.fig` | 1,651,359 | `A7038FDE270E763F697D3556F6C5BF0C186D6EFB34A21D0D6B5F3C3B08953C7F` | ZIP-like container with `canvas.fig`, `thumbnail.png`, `meta.json`, and an empty `images/` directory |
| `Visual Design Specification Plan.zip` | 277,443 | `892913EE62407F550BDC4079101542B847A470006D2C7661D656CB3B40A1F361` | Historical approved generated-code package fingerprint; not present for 2026-08-24 re-verification |

The Make container metadata identifies Version 22 and includes an AI conversation. That conversation contains user/thread metadata, tool calls, and workspace paths, so the container and extracted conversation are intentionally external-only. The Design container metadata identifies `GP22`; its recorded rendered bounds differ slightly from the live top-level frame height because container metadata and live canvas geometry use different bounds/rounding.

## 4. Repository-safe derivations

### Screen renders

Six PNG files were exported directly from the verified Figma Design node IDs at their returned render sizes. Visual inspection confirmed that they contain project interface mockups and vector/icon content only; no raw camera footage, portrait, user account data, or secret is present.

### Design-spec snapshot

`tokens/gp22-design-spec.json` was normalized from visible text inside node `1:11373`. The extracted domains are:

- Night/Day colors;
- typography scale;
- logical endpoint canvases and safe margins;
- spacing and radius scales;
- nine component states;
- P0–P4 cross-screen alert behavior;
- motion durations/easing and reduced-motion rule.

This is classified `VERIFIED_GP22_DERIVED_SPEC`, not a Variables export and not proof that runtime token migration is complete.

### Make resource index

`external-sources/figma-make-resource-index.json` records names and aggregate counts only. It deliberately excludes source contents, AI conversation material, temporary download URLs, and access credentials.

## 5. Rights, privacy, and binary decisions

- GP22 is project-authored design material supplied by the repository owner for this intake.
- No font binaries are archived. Typography names and intent are factual design-spec metadata only.
- No Make PNG resource was archived separately because individual provenance/licensing was not established during this intake.
- No third-party source code or dependency was copied from Make.
- The committed renders contain only the approved interface mockups; their exact bytes are covered by `MANIFEST.sha256`.
- External containers remain outside Git because they are binary design sources and, for Make, contain private AI-session material.

## 6. Limitations

- The historical generated-code ZIP listed in the prior canonical manifest was not available in the controlled source directory and was not re-hashed.
- Published Figma components could not be used as evidence; the file itself exposes no local reusable Component/Variable/style layer.
- This intake does not perform pixel-diff comparison against runtime screenshots and does not claim that all GP22 tokens or screens are implemented.
- Figma node geometry and container `meta.json` rendered bounds have a small height difference; both are recorded according to their source rather than forced to match.

## 7. Verdict

`GP22_ASSET_BASELINE_READY`

The available primary/inspectable sources, external source fingerprints, committed exports, derived specification, inventory, and integrity manifest form a durable and truthful repository baseline. The unavailable historical code ZIP and excluded private Make conversation are explicitly recorded and do not change runtime or source authority.
