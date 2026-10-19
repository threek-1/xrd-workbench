# Methods and evidence boundaries

## Data model and parsing

Each Pattern contains a monotonically increasing, unique 2θ axis in degrees, paired finite intensities, optional wavelength in Å, kind, metadata and history. Every row is retained except an explicitly requested crop. Descending or unordered rows are sorted together and logged. Duplicate angles, non-finite values and malformed data rows fail rather than being silently repaired. Numeric header rows require an explicit skip count; extra columns require explicit selection.

No conversion from θ, q, d-spacing or detector coordinates is inferred. Intensity units are those of the input until normalization. The user declares wavelength; the filename does not establish it. The parser preserves the exact uploaded bytes separately from arrays. There are at least 5 and at most 200,000 scan points; the format is for continuous profiles, not peak sticks.

## Ordered processing

1. Crop to the requested 2θ interval (inclusive); record before/after point counts.
2. Optional asymmetric least-squares baseline on a uniform grid: minimize weighted residuals plus λ times squared second differences. Default λ = 10⁶, p = 0.01, 10 iterations; residuals above the current baseline receive p, others 1−p. These are editable algorithm parameters, not instrument-calibrated values. λ depends on sample spacing.
3. Optional Savitzky–Golay filtering with explicit odd window and polynomial order 3. The window is in points. Baseline/smoothing reject nonuniform grids (1% step tolerance) instead of resampling invisibly.
4. Optional maximum or signed-integral normalization over the retained range after earlier operations. A nonpositive divisor is rejected; negative values are retained. Area uses trapezoidal integration in degrees.

Reference scans receive the same crop/normalization but no baseline or smoothing in the UI/CLI. Background correction and smoothing are off by default. Preprocessed reference files can be used if their provenance is documented. Filtering can alter peak detection/width and must be reviewed against raw data.

## Peak detection

SciPy `find_peaks` selects local maxima with prominence ≥ p × (maximum−minimum) intensity. A descending-prominence selection imposes minimum angular separation in degrees, independent of sample count; ties are deterministic. Scan endpoints cannot be confirmed as local peaks, so peaks at the scan boundary may be missed. Thresholds are user controlled.

Widths are obtained from `peak_widths(..., rel_height=0.5)` and linearly mapped from fractional indices into degrees. They are **widths at half prominence**, not an instrument-corrected fitted FWHM. No Scherrer calculation is performed. d = λ / [2 sin(θ)] is reported only with a declared wavelength and θ > 0. These values are calculations, not additional measurements.

Source: [SciPy find_peaks](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html), [peak_widths](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.peak_widths.html), [Savitzky–Golay](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.savgol_filter.html).

## Reference comparison

Known wavelengths must agree within relative tolerance 10⁻⁴. Unknown wavelengths generate a warning and do not imply physical compatibility. Pairwise comparisons operate only on common angle coverage, with at least 5 original points from each scan and a default overlap of at least half the sample's retained span.

Peak matching is one-to-one. A linear assignment cost penalizes invalid pairs beyond tolerance more than all valid distances combined: maximize valid pair count, then minimize angular error. No experimental peak can explain multiple reference peaks in this simple model. More than 2,000 selected peaks in either scan rejects matching; adjust detection parameters explicitly rather than silently subsampling.

Let P be matched / observed peaks, R be matched / reference peaks, F1 = 2PR/(P+R) (zero if denominator is zero). Profile similarity C is cosine similarity after subtracting the minimum of each interpolated profile over the common interval. This removes only a constant for scoring; it is not a scientific background correction. Scoring uses linear interpolation on a common grid based on the coarser median input step, up to 200,000 points. It does not replace stored data. Large gaps/nonuniform sampling can make interpolation inappropriate; inspect inputs.

The heuristic score is:

`score = (0.65 × peak F1 + 0.35 × profile cosine) × sample angle-span coverage`

No peaks in either common-range set forces score = 0. A zero matched count is labelled `no_peak_support` even if some profile similarity exists. Coverage is an angular-span fraction, not a point-count fraction. Outside-range experimental peaks are separately reported. Candidate score weights are chosen heuristics, not trained or calibrated. No confidence interval, p value, classification accuracy or phase probability is reported.

Optional shifts evaluate 41 equally spaced offsets over ±max_shift plus exactly zero. The reported sign is added to the reference angle. The best score is retained; equal-score ties favor smaller absolute shifts. The original zero-shift score is always recorded if comparable. This is exploratory search and may overfit. It neither calibrates an instrument nor measures lattice parameters; plots remain unshifted.

## Scientific interpretation

The analysis unit is one supplied scan, not thousands of independent experimental replicates. No inferential statistical tests are performed. Simulated data are labelled synthetic. Processing output, matching metrics and d-spacings are calculated quantities. Candidate assignments are hypotheses limited to the uploaded reference library. Mixtures, texture, size/strain broadening, missing references, fluorescence and preparation artifacts can affect rankings.

High similarity does not establish a pure phase. Unmatched peaks are unexplained features, not automatically an impurity. Low similarity does not independently prove absence. Quantitative phase analysis, instrument calibration, chemistry/element constraints and real benchmark validation are not implemented.
