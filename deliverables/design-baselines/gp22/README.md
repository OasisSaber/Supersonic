# GP22 Design Asset Baseline

- Verdict: `GP22_ASSET_BASELINE_READY`
- Intake date: 2026-08-24
- Issue: [#67](https://github.com/OasisSaber/Supersonic/issues/67)
- Repository baseline: `main@7e1ea06e52964b09c8368943236847525a7deccc`
- Canonical index: [`../../../docs/design/GP22_SOURCE_MANIFEST.md`](../../../docs/design/GP22_SOURCE_MANIFEST.md)

This directory is the repository-safe evidence layer for the approved GP22 design baseline. It records stable source identities, externally held source-container fingerprints, source-derived screen renders, a normalized design-spec snapshot, and integrity hashes. It does not copy Figma Make code into production or change runtime behavior.

## Source model

1. Figma Make `Visual-Design-Specification-Plan` is the primary editable design-generation source.
2. Figma Design `GP22` is the canonical inspectable canvas used for node-level verification and exports.
3. The published Figma Site is a presentation preview, not a substitute for either source file.
4. Local `.make` and `.fig` containers remain outside Git; their approved fingerprints are recorded here.
5. React/FastAPI runtime code is implementation evidence, not a design-source replacement.

## Archived content

- [`screenshots/`](screenshots/): six PNG renders exported from named GP22 Figma Design nodes.
- [`tokens/gp22-design-spec.json`](tokens/gp22-design-spec.json): normalized machine-readable snapshot of the visible Extended Design Spec.
- [`external-sources/figma-make-resource-index.json`](external-sources/figma-make-resource-index.json): names-only inventory of the current Make resource set; no temporary URLs or source contents.
- [`SOURCE_INVENTORY.csv`](SOURCE_INVENTORY.csv): classification, provenance, external fingerprints, archive paths, hashes, and privacy/licensing decisions.
- [`PROVENANCE.md`](PROVENANCE.md): verification method, evidence, exclusions, and limitations.
- [`MANIFEST.sha256`](MANIFEST.sha256): SHA-256 for every committed file in this directory except the manifest itself.

## Boundaries

- These files are design evidence, not production React code.
- The token snapshot is derived from visible Figma text. The Figma file has no local Variables or reusable styles, so it must not be described as a Variables export.
- Screenshot dimensions are render dimensions of the selected Figma frames, not the logical endpoint resolutions printed inside the mockups.
- No `.make`, `.fig`, AI conversation, Make source code, font binary, private path, access token, temporary signed URL, or unreviewed raw image is committed.
- `gp05.v1` remains the runtime protocol name.

## Integrity check

From the repository root:

```bash
cd deliverables/design-baselines/gp22
sha256sum -c MANIFEST.sha256
```

The repository-wide gate remains:

```bash
bash scripts/validate.sh
```
