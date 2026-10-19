# Export and replay

## Archive contents

| Path | Contents |
|---|---|
| `raw/` | Uploaded files, unchanged |
| `measurement/` | Raw-sample plot, numerical source and plot checks |
| `figure.*` | Comparison plot in PDF, SVG, PNG and TIFF |
| `processed/` | Data used in the comparison plot |
| `analysis/` | Processed scans and peak tables for all samples and references |
| `report.md`, `report.json` | Selected sample report |
| `reports/` | Reports for all samples |
| `comparisons.json` | Reference rankings and peak pairs |
| `manifest.json` | Sources, processing settings, software environment and display offsets |
| `checksums.sha256` | File hashes |

## Repeat the analysis

Extract the archive into a separate directory. Activate an environment with the project and the dependency versions recorded in the manifest, then run:

```bash
python reproduce_analysis.py
```

The script reads the raw files, applies the recorded processing settings, repeats matching and regenerates both plots and the reports. It compares the results with the archived numerical data and reports. PDF timestamps and library differences may prevent byte-identical plot files.

To redraw the figures without repeating analysis:

```bash
python reproduce.py
```

This reads `processed/` for the comparison plot and `measurement/source.csv` for the raw-sample plot.

## Plot settings and checks

The UI offers widths of 88, 120 and 180 mm. PDF and SVG preserve vector paths and editable text; PNG and TIFF use 600 dpi. Comparison plots record any vertical display offset. Matching offsets are not applied to plotted angles.

Each export checks PDF text size, text overlap and page bounds with PyMuPDF. These checks do not cover every curve/label collision. Inspect figures at their final print size, especially after changing labels or layout.

For additional checks with an installed Nature Figure package, set:

```bash
export NATURE_FIGURE_SKILL=/absolute/path/to/nature-figure
xrd-workbench ui
```

The exporter then runs source, PDF-text and collision checks and saves their logs in the archive. A failed check blocks export. The external package and its dependencies must be installed separately.

## Sharing

The archive contains the uploaded source files. Check their sharing permissions before distributing it. The software licence does not change the rights attached to uploaded data. Included demonstration data are described in [DATA.md](DATA.md).
