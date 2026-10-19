# XRD Workbench

A local powder X-ray diffraction workbench for numerical scan parsing, traceable processing, reference-library screening and publication-oriented figures.

[中文](README.md) · [Chinese tutorial](docs/TUTORIAL.zh-CN.md) · [Methods](docs/METHODS.md) · [Reproducibility](docs/REPRODUCIBILITY.md)

## Run

Python 3.11–3.13:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
xrd-workbench ui
```

Open <http://127.0.0.1:8501>. A deterministic, explicitly synthetic demonstration is included. The interface currently uses Chinese labels; the Python API and CLI use English. The launcher binds to localhost and disables Streamlit usage statistics. Installation downloads dependencies; analysis requires no remote API.

## Features

- TXT/CSV/XY/DAT/TSV continuous scans, explicit column mapping and strict invalid-row checks.
- Immutable angle/intensity arrays, raw-file hashes and processing history.
- Cropping, max/area normalization, optional asymmetric least-squares background correction and Savitzky–Golay smoothing.
- One-to-one peak matching, profile cosine similarity, overlap penalty, unmatched/missing peaks and optional exploratory reference shift.
- Separate full raw-measurement and processed comparison figures.
- Optional user-declared compound, formula, structure, CIF origin and source fields.
- On-page Markdown/JSON reports with major peak candidates, ambiguous matches and qualified structure hypotheses; no model API, AI account or API key is needed. Unknown identities stay unknown.
- Editable vector PDF/SVG and 600 dpi PNG/TIFF, stacked or overlaid at physical print dimensions.
- Raw inputs, all processed scans and peak tables, candidate evidence, parameters, checksums and replay scripts in one ZIP.
- Shared scientific core for the local web app and CLI.

## Boundaries

Inputs must be continuous **2θ (degrees) / intensity** scans. No proprietary RAW, XRDML, CIF, image digitization or two-dimensional detector support is implemented in v0.2. Declaring a CIF origin records provenance only; no CIF is parsed or independently verified. A reference filename labels a supplied candidate; it is not a verified chemical identity. The library is supplied by the user; no proprietary diffraction database is bundled.

Scores are heuristic rankings, not calibrated probabilities, purity measurements or phase fractions. The algorithm has not been validated on a real labelled experimental benchmark. It does not perform Rietveld refinement, structure solution, quantitative mixture fitting or crystallite-size estimation. Widths are measured at half prominence, not instrument-corrected FWHM.

Data are never shifted horizontally in the figure by the matching optimizer. Any vertical display translations are recorded. Negative processed values are retained. Unknown wavelengths remain unknown, while incompatible declared wavelengths block angle-space comparisons.

## Test and build

```bash
python -m pytest -q
python -m build
```

See [QA](docs/QA.md) for checks actually executed. Generic PDF text checks are included. Full Nature Skills auditing is an optional external developer integration; those skills are not bundled. Final-size human review remains necessary.

## Licence and data

AGPL-3.0-or-later. See [LICENSE](LICENSE). Original synthetic examples are distributed under the same terms. User and third-party datasets retain their original rights. See [data provenance](docs/DATA.md) for the included examples and excluded private inputs.
