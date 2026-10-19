# Verification record

Local verification: 2026-10-19, Python 3.12, macOS arm64.

## Software checks

- 47 automated tests passed. Coverage includes delimiter/header handling, paired sorting, malformed-data rejection, immutable arrays, processing replay, peak detection, one-to-one matching, wavelength checks, report metadata, ambiguous assignments, export hashes and the Streamlit interface.
- Source and wheel distributions built. An isolated wheel installation exported both figures, reports and replay scripts.
- Raw-input replay reproduced stored numerical arrays and report data. Figure files may differ byte-for-byte because PDF timestamps and dependency versions vary.
- Browser checks covered file uploads, measurement/comparison/report tabs and ZIP download. Archive CRC and SHA-256 checks passed.

## Figure checks

The three-trace synthetic example and a private numerical-file pair were checked using the installed Nature Figure workflow. Source validation and exported-PDF text audits passed. Collision audits reported PASS with zero failures and warnings. Portable text-size, overlap and page-bound checks also passed.

Rendered plots were inspected for missing labels, clipping and curve/label overlap. Each figure has one axis, so panel alignment checks do not apply. New data or labels require new checks.

## Input compatibility

A private instrument text file with trailing commas (1,733 points) and a numerical TSV (2,251 points) were parsed without changing numerical values or original bytes. Synthetic regression fixtures cover the supported format. Private files and screenshots are not distributed.

## Limits of verification

These checks establish software behavior and compatibility with the tested inputs. They do not establish phase-identification accuracy on a labelled experimental benchmark. Windows installation has not been manually verified. The CI workflow tests Python 3.11–3.13 on Linux; use the actual Actions result for its current status.

The dependency snapshot is in `tested-environment.txt`. It describes the local test environment rather than a cross-platform lockfile.
