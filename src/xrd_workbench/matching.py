"""Reference-library screening, not chemical identification or phase quantification."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from scipy.optimize import linear_sum_assignment
from .core import Pattern, detect_peaks


@dataclass(frozen=True)
class MatchOptions:
    tolerance_deg: float = 0.2
    prominence: float = 0.04
    min_peak_distance_deg: float = 0.15
    max_shift_deg: float = 0.0
    min_overlap_fraction: float = 0.5

    def validate(self):
        if not 0 < self.tolerance_deg <= 2:
            raise ValueError("Peak tolerance must be in (0, 2] degrees.")
        if not 0 <= self.max_shift_deg <= 1:
            raise ValueError("Exploratory reference shift must be in [0, 1] degrees.")
        if not 0 < self.min_overlap_fraction <= 1:
            raise ValueError("Minimum overlap must be in (0, 1].")
        if not 0 < self.prominence <= 1 or not 0 < self.min_peak_distance_deg <= 10:
            raise ValueError("Invalid peak selection parameters.")


def _pair(observed, expected, tolerance):
    if not len(observed) or not len(expected):
        return []
    delta = np.abs(np.subtract.outer(observed, expected))
    # Invalid matches cost more than every valid distance combined. This first
    # maximizes cardinality, then minimizes total angular error.
    cost = np.where(delta <= tolerance, delta, (max(delta.shape)+1)*(tolerance+1))
    rows, cols = linear_sum_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(rows, cols) if delta[i, j] <= tolerance]


def _evaluate(sample, reference, sp, rp, options, shift):
    lo, hi = max(sample.x[0], reference.x[0]+shift), min(sample.x[-1], reference.x[-1]+shift)
    fraction = max(0., float((hi-lo)/(sample.x[-1]-sample.x[0])))
    if hi <= lo or fraction < options.min_overlap_fraction:
        return None
    sm = (sample.x >= lo) & (sample.x <= hi)
    rm = (reference.x+shift >= lo) & (reference.x+shift <= hi)
    if sm.sum() < 5 or rm.sum() < 5:
        return None
    observed = [p for p in sp if lo <= p["two_theta_deg"] <= hi]
    expected = [p for p in rp if lo <= p["two_theta_deg"]+shift <= hi]
    sx = np.array([p["two_theta_deg"] for p in observed])
    rx = np.array([p["two_theta_deg"]+shift for p in expected])
    pairs = _pair(sx, rx, options.tolerance_deg)
    precision = len(pairs)/len(observed) if observed else 0.
    recall = len(pairs)/len(expected) if expected else 0.
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.
    # Scoring grid is distinct from export data; limited by the coarser spacing.
    step = max(np.median(np.diff(sample.x)), np.median(np.diff(reference.x)))
    n = min(200_000, max(5, int((hi-lo)/step)+1))
    grid = np.linspace(lo, hi, n)
    a = np.interp(grid, sample.x, sample.y)
    b = np.interp(grid, reference.x+shift, reference.y)
    a, b = a-a.min(), b-b.min()
    norm = np.linalg.norm(a)*np.linalg.norm(b)
    cosine = float(np.clip(np.dot(a, b)/norm, 0, 1)) if norm else 0.
    # Flat or peak-free spectra cannot become a candidate on correlation alone.
    score = float((0.65*f1+0.35*cosine)*fraction) if observed and expected else 0.
    oi, ri = {i for i, _ in pairs}, {j for _, j in pairs}
    errors = [float(sx[i]-rx[j]) for i, j in pairs]
    return {"reference": reference.name, "score": score, "peak_f1": f1,
            "observed_peak_coverage": precision, "reference_peak_recall": recall,
            "profile_cosine": cosine, "overlap_fraction": fraction,
            "overlap_range_deg": [float(lo), float(hi)], "comparison_grid_points": n,
            "reference_shift_deg": float(shift), "matched_count": len(pairs),
            "mean_abs_peak_error_deg": float(np.mean(np.abs(errors))) if errors else None,
            "matched_peaks": [{"observed_deg": float(sx[i]),
                "reference_original_deg": float(rx[j]-shift), "reference_shifted_deg": float(rx[j]),
                "delta_deg": float(sx[i]-rx[j])} for i, j in pairs],
            "unmatched_observed_deg": [float(x) for i, x in enumerate(sx) if i not in oi],
            "missing_reference_deg": [float(x) for j, x in enumerate(rx) if j not in ri],
            "outside_overlap_observed_deg": [p["two_theta_deg"] for p in sp
                                               if not lo <= p["two_theta_deg"] <= hi]}


def compare(sample: Pattern, reference: Pattern, options=MatchOptions()):
    options.validate()
    warnings = []
    if sample.wavelength is not None and reference.wavelength is not None:
        if not np.isclose(sample.wavelength, reference.wavelength, rtol=1e-4):
            raise ValueError("Different wavelengths: angle-space matching is invalid. Supply compatible reference data.")
    else:
        warnings.append("Wavelength unknown for one or both scans; physical comparability is unverified.")
    sp = detect_peaks(sample, options.prominence, options.min_peak_distance_deg)
    rp = detect_peaks(reference, options.prominence, options.min_peak_distance_deg)
    if max(len(sp), len(rp)) > 2000:
        raise ValueError("More than 2000 selected peaks; increase prominence/separation explicitly before matching.")
    base = _evaluate(sample, reference, sp, rp, options, 0.)
    shifts = [0.]
    if options.max_shift_deg:
        shifts = np.unique(np.r_[0., np.linspace(-options.max_shift_deg, options.max_shift_deg, 41)])
        warnings.append("Reference shift was optimized for screening; it is not instrument calibration or lattice refinement.")
    candidates = [_evaluate(sample, reference, sp, rp, options, s) for s in shifts]
    candidates = [c for c in candidates if c is not None]
    if not candidates:
        raise ValueError("Insufficient shared scan range or fewer than 5 shared points.")
    result = max(candidates, key=lambda c: (c["score"], -abs(c["reference_shift_deg"])))
    result["unshifted_score"] = base["score"] if base is not None else None
    if not sp or not rp:
        warnings.append("No selected peaks in at least one scan. No phase inference is possible.")
    if result["matched_count"] < 3:
        warnings.append("Fewer than three matched peaks: evidence is particularly weak.")
    if result["overlap_fraction"] < 0.95:
        warnings.append("Reference covers only part of the sample scan; score includes an overlap penalty.")
    result.update({"warnings": warnings, "status": "candidate_only" if result["matched_count"] else "no_peak_support",
                   "options": asdict(options), "score_is_probability": False})
    return result


def rank_references(sample, references, options=MatchOptions()):
    results, rejected = [], []
    for ref in references:
        try:
            results.append(compare(sample, ref, options))
        except ValueError as exc:
            rejected.append({"reference": ref.name, "reason": str(exc)})
    return sorted(results, key=lambda r: -r["score"]), rejected
