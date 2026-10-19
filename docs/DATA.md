# Data and source availability

The repository contains source code, an original tutorial, and synthetic demonstration data. Experimental files and third-party reference libraries are not included.

| Files | Origin | Units and purpose |
|---|---|---|
| `examples/Synthetic sample.csv` | Generated profile combining invented A/B peaks, background and seeded noise | 2θ in degrees; arbitrary input intensity; software demonstration |
| `examples/Synthetic Phase A.csv` | Invented Gaussian peaks | 2θ in degrees; arbitrary intensity; synthetic reference |
| `examples/Synthetic Phase B.csv` | Invented Gaussian peaks | 2θ in degrees; arbitrary intensity; synthetic reference |
| `docs/demo-figure.png`, `docs/demo-figure.pdf` | Plot of those synthetic profiles | Visual example, not experimental evidence |

The generator is `src/xrd_workbench/demo.py`; `python scripts/generate_demo.py` writes the example files. Seed: 20261018. All three profiles have 3,001 points spanning 5–65°. The demonstration declares 1.5406 Å, but the profiles are not calculated from crystal structures. The coefficient used to combine synthetic profiles is not a measured phase fraction.

Original code, documentation and synthetic examples are distributed under AGPL-3.0-or-later. Dependencies retain their own licences. User-supplied data retain their source rights; exporting a ZIP does not make them public or change their licence.

Analysis archives contain unchanged uploaded files, processed data, figure source data, parameters, dependency versions, reports, checksums and replay scripts. Check every file before sharing such an archive. Use the source repository for software distribution rather than uploading a private analysis archive.

For reproducible citation, record the software version and commit identifier together with the analysis archive.
