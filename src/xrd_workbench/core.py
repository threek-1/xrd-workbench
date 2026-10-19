"""Scan data, text parsing and processing operations."""
from __future__ import annotations

from dataclasses import dataclass, field, replace, asdict
from hashlib import sha256
from pathlib import Path
import re

import numpy as np
from scipy import sparse
from scipy.integrate import trapezoid
from scipy.sparse.linalg import spsolve
from scipy.signal import savgol_filter, find_peaks, peak_widths

MAX_BYTES = 20 * 1024 * 1024
MAX_POINTS = 200_000


@dataclass(frozen=True)
class Pattern:
    name: str
    x: np.ndarray
    y: np.ndarray
    wavelength: float | None = None
    kind: str = "measured"
    metadata: dict = field(default_factory=dict)
    history: tuple = ()

    def __post_init__(self):
        x, y = np.array(self.x, dtype=float, copy=True), np.array(self.y, dtype=float, copy=True)
        if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 5:
            raise ValueError("A pattern needs at least 5 paired angle/intensity points.")
        if len(x) > MAX_POINTS:
            raise ValueError(f"At most {MAX_POINTS:,} points per pattern are supported.")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("NaN/Inf values are not accepted; repair the source explicitly.")
        if np.any(np.diff(x) <= 0):
            raise ValueError("Angles must be unique and strictly increasing; duplicate angles are not silently merged.")
        if x[0] < 0 or x[-1] > 180:
            raise ValueError("The angle axis must be 2θ in degrees within [0, 180].")
        if self.wavelength is not None and (not np.isfinite(self.wavelength) or self.wavelength <= 0):
            raise ValueError("Wavelength must be positive, in angstroms.")
        x.flags.writeable = y.flags.writeable = False
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)

    @property
    def uniform(self):
        steps = np.diff(self.x)
        return bool(np.allclose(steps, np.median(steps), rtol=0.01, atol=1e-7))

    def info(self):
        return {"name": self.name, "kind": self.kind, "points": len(self.x),
                "two_theta_range_deg": [float(self.x[0]), float(self.x[-1])],
                "wavelength_angstrom": self.wavelength, "metadata": self.metadata,
                "history": list(self.history)}


def parse_bytes(data: bytes, name: str, wavelength=None, columns=None, skip_rows=0) -> Pattern:
    """Parse whitespace/tab/comma/semicolon 2-column spectra; fail on corrupt rows.

    Extra columns require an explicit zero-based (x, y) selection. Header lines
    before the first numeric row are retained as metadata. Internal invalid rows
    and numeric footers are never silently discarded.
    """
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds the 20 MB limit.")
    if b"\x00" in data:
        raise ValueError("Binary/UTF-16 input is not supported. Export UTF-8 TXT/CSV/XY first.")
    text = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Cannot decode text; export UTF-8 text from the instrument software.")
    if skip_rows < 0:
        raise ValueError("skip_rows must be nonnegative.")
    if columns is not None and (len(columns) != 2 or min(columns) < 0 or columns[0] == columns[1]):
        raise ValueError("Select two distinct nonnegative column indices.")
    rows, headers, comments = [], [], 0
    terminal_delimiter_rows = []
    for line_no, original in enumerate(text.splitlines(), 1):
        if line_no <= skip_rows:
            headers.append(original)
            continue
        line = original.strip()
        if not line:
            continue
        if line.startswith(("#", "!", "//")):
            comments += 1
            continue
        line = line.split("#", 1)[0].strip()
        tokens = re.split(r"[;,\t]", line) if any(c in line for c in ";,\t") else line.split()
        tokens = [t.strip().strip('"') for t in tokens]
        # Some instrument exports terminate every complete record with a comma
        # or semicolon. Accept one empty terminal field only after at least two
        # nonempty fields; never erase an empty angle/intensity or interior cell.
        terminal_delimiter = (len(tokens) >= 3 and tokens[-1] == ""
                              and all(tokens[:-1]))
        if terminal_delimiter:
            tokens = tokens[:-1]
        try:
            values = [float(t.replace("D", "E").replace("d", "e")) for t in tokens]
        except ValueError:
            if rows:
                raise ValueError(f"Invalid data row {line_no}: {original[:90]}. No rows were dropped.") from None
            # A partly numeric line is more likely a broken first data row.
            if tokens and re.match(r"^[+-]?(?:\d|\.\d)", tokens[0]):
                raise ValueError(f"Ambiguous numeric header/data at line {line_no}; set header rows explicitly.")
            headers.append(original)
            continue
        if columns is None and len(values) != 2:
            raise ValueError(f"Line {line_no} has {len(values)} columns. Choose angle/intensity columns explicitly.")
        xi, yi = columns or (0, 1)
        if max(xi, yi) >= len(values):
            raise ValueError(f"Missing selected column at line {line_no}.")
        rows.append((values[xi], values[yi]))
        if terminal_delimiter:
            terminal_delimiter_rows.append(line_no)
        if len(rows) > MAX_POINTS:
            raise ValueError(f"Input exceeds {MAX_POINTS:,} points.")
    if len(rows) < 5:
        raise ValueError("No usable scan found (at least 5 rows required). Peak lists are not continuous scans.")
    arr = np.array(rows)
    order = np.argsort(arr[:, 0], kind="stable")
    sorted_input = not np.array_equal(order, np.arange(len(arr)))
    arr = arr[order]
    history = ({"operation": "sort_angle_ascending", "rows": len(arr)},) if sorted_input else ()
    kind = "synthetic" if "# SYNTHETIC DEMONSTRATION;" in text[:500] else "user_supplied"
    return Pattern(Path(name).name, arr[:, 0], arr[:, 1], wavelength, kind=kind, metadata={
        "sha256": sha256(data).hexdigest(), "source_filename": Path(name).name,
        "encoding": encoding, "header_lines": headers, "comment_lines": comments,
        "terminal_delimiter_rows": terminal_delimiter_rows,
        "columns_zero_based": list(columns or (0, 1)), "skip_rows": skip_rows,
        "angle_unit": "degree_2theta", "intensity_unit": "input_units",
        "wavelength_source": "user_declared" if wavelength is not None else "unknown",
    }, history=history)


@dataclass(frozen=True)
class Recipe:
    lower: float | None = None
    upper: float | None = None
    baseline: bool = False
    baseline_lambda: float = 1e6
    baseline_p: float = 0.01
    baseline_iterations: int = 10
    smooth_window: int = 0
    smooth_order: int = 3
    normalization: str = "max"

    def validate(self):
        if self.normalization not in ("none", "max", "area"):
            raise ValueError("Normalization must be none, max or area.")
        for bound in (self.lower, self.upper):
            if bound is not None and (not np.isfinite(bound) or not 0 <= bound <= 180):
                raise ValueError("Crop bounds must be finite degrees in [0, 180].")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ValueError("Lower angle must be below upper angle.")
        if not np.isfinite(self.baseline_lambda) or self.baseline_lambda <= 0 or not 0 < self.baseline_p < 1:
            raise ValueError("Invalid asymmetric least-squares baseline parameters.")
        if not 1 <= self.baseline_iterations <= 100:
            raise ValueError("Baseline iterations must be in [1, 100].")
        if self.smooth_order < 0 or self.smooth_window < 0 or (self.smooth_window and
                (self.smooth_window % 2 != 1 or self.smooth_window <= self.smooth_order)):
            raise ValueError("Smoothing window must be odd and exceed polynomial order.")


def process(pattern: Pattern, recipe: Recipe) -> Pattern:
    recipe.validate()
    keep = np.ones(len(pattern.x), dtype=bool)
    if recipe.lower is not None:
        keep &= pattern.x >= recipe.lower
    if recipe.upper is not None:
        keep &= pattern.x <= recipe.upper
    x, y = pattern.x[keep], pattern.y[keep].copy()
    if len(x) < 5:
        raise ValueError("Crop retains fewer than 5 points.")
    history = list(pattern.history)
    if len(x) != len(pattern.x):
        history.append({"operation": "crop", "lower": recipe.lower, "upper": recipe.upper,
                        "rows_before": len(pattern.x), "rows_after": len(x)})
    regular = np.allclose(np.diff(x), np.median(np.diff(x)), rtol=0.01, atol=1e-7)
    if (recipe.baseline or recipe.smooth_window) and not regular:
        raise ValueError("Baseline/smoothing requires a uniform grid; nonuniform scans are not silently resampled.")
    if recipe.baseline:
        d = sparse.diags([1., -2., 1.], [0, 1, 2], shape=(len(y)-2, len(y)), format="csc")
        penalty = recipe.baseline_lambda * (d.T @ d)
        weights = np.ones(len(y))
        for _ in range(recipe.baseline_iterations):
            z = spsolve(sparse.diags(weights, format="csc") + penalty, weights*y)
            weights = np.where(y > z, recipe.baseline_p, 1-recipe.baseline_p)
        y -= z
        history.append({"operation": "asymmetric_least_squares", "lambda": recipe.baseline_lambda,
                        "p": recipe.baseline_p, "iterations": recipe.baseline_iterations,
                        "negative_values": "retained"})
    if recipe.smooth_window:
        if recipe.smooth_window > len(y):
            raise ValueError("Smoothing window exceeds retained points.")
        y = savgol_filter(y, recipe.smooth_window, recipe.smooth_order, mode="interp")
        history.append({"operation": "savitzky_golay", "window_points": recipe.smooth_window,
                        "polynomial_order": recipe.smooth_order})
    if recipe.normalization != "none":
        factor = float(np.max(y) if recipe.normalization == "max" else trapezoid(y, x))
        if factor <= 0 or not np.isfinite(factor):
            raise ValueError("Normalization requires a positive maximum/integral.")
        y = y / factor
        history.append({"operation": "normalize", "method": recipe.normalization, "divisor": factor,
                        "scope": "retained_range_after_other_processing"})
    return replace(pattern, x=x, y=y, history=tuple(history))


def detect_peaks(pattern: Pattern, prominence=0.04, min_distance=0.15):
    """Prominence relative to range; separation in degrees, widths at half prominence."""
    if not 0 < prominence <= 1 or not np.isfinite(min_distance) or min_distance <= 0:
        raise ValueError("Peak prominence must be in (0, 1]; separation must be positive.")
    span = float(np.ptp(pattern.y))
    if span <= 0:
        return []
    idx, props = find_peaks(pattern.y, prominence=span*prominence)
    selected = []
    for k in np.argsort(-props["prominences"], kind="stable"):
        if all(abs(pattern.x[idx[k]] - pattern.x[idx[j]]) >= min_distance for j in selected):
            selected.append(int(k))
    selected.sort(key=lambda k: idx[k])
    if not selected:
        return []
    chosen = idx[selected]
    _, _, left, right = peak_widths(pattern.y, chosen, rel_height=0.5)
    grid = np.arange(len(pattern.x))
    widths = np.interp(right, grid, pattern.x)-np.interp(left, grid, pattern.x)
    result = []
    for n, k in enumerate(selected):
        angle = float(pattern.x[idx[k]])
        d_spacing = (float(pattern.wavelength/(2*np.sin(np.deg2rad(angle/2))))
                     if pattern.wavelength and angle > 0 else None)
        result.append({"two_theta_deg": angle, "intensity": float(pattern.y[idx[k]]),
                       "prominence": float(props["prominences"][k]),
                       "width_half_prominence_deg": float(widths[n]), "d_angstrom": d_spacing})
    return result
