# Roadmap

## Available in v0.2

- Local numerical scan UI + CLI + standalone scientific core.
- Strict two-column text parser and explicit multi-column UI/API choices.
- Documented processing recipes, reference screening, peak evidence, vector/high-DPI figures and replay exports.
- Synthetic fixtures, numerical regression tests and UI integration test.

- Separate raw-measurement and comparison figures; reference metadata and per-sample reports.

## Next: broaden instrument and phase validation

1. Obtain permission-cleared representative files from different instruments and several known phases/mixtures, including background-only and low-quality scans.
2. Confirm units, radiation treatment (Kα1 vs weighted/doublet), scan modes and file headers.
3. Add versioned fixtures and expected outcomes reviewed by a diffraction specialist. Measure candidate ranking behavior without claiming probabilities from synthetic demonstrations.
4. Add user-reported parsing issues as focused regression tests.

## Later, separately scoped

- CIF-derived reference sticks and configurable instrumental broadening; preserve structure provenance and wavelength model.
- Explicit peak-list input format, kept distinct from continuous profiles.
- Additional instrument importers (XRDML and vendor RAW only with verified specifications/files).
- Larger user-managed reference library with metadata and licensing checks; optional element constraints.
- Validated instrument calibration, peak fitting, uncertainty propagation and GSAS-II integration.
- Quantitative multiphase refinement with instrument and structure models, not heuristic score percentages.
- Image/PDF digitization with calibration and uncertainty; never treated as original numerical measurements.
- UI translations, session recipe import, richer styling and dedicated per-sample batch figure export.

No timeline or implemented capability is implied by this list.
