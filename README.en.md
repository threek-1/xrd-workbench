# XRD Workbench

A local tool for powder XRD scan processing, reference comparison, plotting and reports.

[中文](README.md) · [Chinese tutorial](docs/TUTORIAL.zh-CN.md) · [Methods](docs/METHODS.md) · [Export and replay](docs/REPRODUCIBILITY.md)

![Synthetic comparison example](docs/demo-figure.png)

The example profiles are synthetic and do not represent real compounds.

## Features

- TXT, CSV, XY, DAT and TSV continuous scans with column selection.
- Angle cropping, normalization, optional AsLS background subtraction and Savitzky–Golay smoothing.
- Peak detection, d-spacing for known wavelengths and one-to-one reference matching.
- Separate raw-sample and comparison plots in PDF, SVG and 600 dpi PNG/TIFF.
- Reference metadata, peak assignments and per-sample reports.
- Raw files, processed arrays, parameters and replay scripts in one export.

All computation runs locally. Users supply the reference library; no phase database is bundled.

## Install

Python 3.11–3.13:

```bash
git clone https://github.com/threek-1/xrd-workbench.git
cd xrd-workbench
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
xrd-workbench ui
```

Open <http://127.0.0.1:8501>. The interface uses Chinese labels. On Windows, run `.venv\Scripts\python.exe` and `.venv\Scripts\xrd-workbench.exe` directly after creating the environment. Installation downloads dependencies; subsequent analysis runs locally.

## Input and interpretation

Input must be a continuous 2θ (degrees) / intensity scan. Duplicate angles, missing values and non-finite numbers are rejected. Extra columns and numeric instrument headers require explicit settings. CIF, proprietary RAW, XRDML, images and discrete peak lists are not supported.

The raw-sample plot retains all imported points. Comparison plots and reports use the selected processing parameters. Reference names and structures are user-supplied metadata. Scores rank the supplied references; they are not probabilities or phase fractions. The program does not perform structure solution, Rietveld refinement or quantitative phase analysis. See [Methods](docs/METHODS.md).

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

See [Contributing](CONTRIBUTING.md) for changes and bug reports.

## Licence

[AGPL-3.0-or-later](LICENSE) covers the source, tutorial and synthetic examples. User data retain their original rights. See [data provenance](docs/DATA.md).
