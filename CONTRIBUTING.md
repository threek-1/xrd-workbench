# Contributing

Install `python -m pip install -e ".[dev]"`, then run `python -m pytest -q`.

Keep parsing, numerical processing, matching, plotting and UI separate. Changes to scientific behavior must include an independently justified regression case and update `docs/METHODS.md`. Do not add arbitrary smoothing, clipping, automatic shift, point removal, uncalibrated probabilities or phase-fraction claims.

Do not commit user experimental files, credentials, commercial reference libraries or data without permission. Prefer minimal, explicitly synthetic format fixtures. Include source, units, radiation and reuse rights for contributed real data. Error reports should include package versions, a sanitized file, parameters, expected behavior and exact failure.

For plotting changes, run the installed Nature Figure workflow where available and inspect outputs at final physical size. Update QA notes honestly. A successful source check is not a visual or scientific validation.

The project is licensed AGPL-3.0-or-later. Contributions are submitted under the same licence unless explicitly agreed otherwise.
