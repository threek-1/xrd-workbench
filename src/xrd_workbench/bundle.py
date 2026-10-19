"""Archive raw inputs, processed data, figures and replay scripts."""
from __future__ import annotations
from io import BytesIO, StringIO
from hashlib import sha256
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
import matplotlib.pyplot as plt
from . import __version__
from .figures import make_figure, export_figure, audit_pdf
from .core import detect_peaks
from .matching import MatchOptions
from .report import build_report


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def csv_bytes(pattern):
    out = StringIO()
    np.savetxt(out, np.column_stack((pattern.x, pattern.y)), delimiter=",",
               header="two_theta_deg,intensity", comments="", fmt="%.12g")
    return out.getvalue().encode()


def table_bytes(rows):
    if not rows:
        return b""
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def nature_audit(fig, pdf_bytes):
    """Run external figure checks when NATURE_FIGURE_SKILL is configured."""
    root = os.environ.get("NATURE_FIGURE_SKILL")
    if not root:
        return {}, {"status": "not_run", "reason": "NATURE_FIGURE_SKILL is not configured"}
    root = Path(root).resolve()
    scripts = root / "scripts"
    if not all((scripts / f).is_file() for f in ("audit_panel_alignment.py", "audit_pdf_text.py",
                                               "audit_figure_collisions.py", "validate_figure.py")):
        raise ValueError("Configured Nature Figure skill is incomplete.")
    files = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pdf = tmp / "figure.pdf"
        pdf.write_bytes(pdf_bytes)
        # Single panel by construction, record measured plot rectangle.
        fig.canvas.draw()
        rect = fig.axes[0].get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        files["qa/alignment.json"] = json_bytes({"status": "not_applicable", "axes_count": 1,
                         "plot_rectangle_inches": list(rect.bounds)})
        jobs = [("source", [str(scripts/"validate_figure.py"), str(Path(__file__).with_name("figures.py")), "--json"]),
                ("pdf_text", [str(scripts/"audit_pdf_text.py"), str(pdf), "--min-pt", "5", "--json"]),
                ("collision", [str(scripts/"audit_figure_collisions.py"), str(pdf),
                               "--json-out", str(tmp/"collision.json")])]
        status = []
        for name, args in jobs:
            run = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=90)
            # Avoid private temporary/source paths in public export archives.
            output = run.stdout.replace(str(tmp), "EXPORT").replace(str(Path(__file__).parent), "PACKAGE")
            files[f"qa/nature_{name}.txt"] = output.encode()
            status.append({"check": name, "returncode": run.returncode})
            if run.returncode != 0:
                raise ValueError(f"Nature {name} audit did not pass (exit {run.returncode}). Review layout/dependencies.")
        if (tmp/"collision.json").exists():
            raw = (tmp/"collision.json").read_text().replace(str(tmp), "EXPORT")
            files["qa/nature_collision.json"] = raw.encode()
    return files, {"status": "automated_checks_completed", "checks": status, "visual_review": "required"}


def make_bundle(patterns, originals, *, recipe, comparisons, peaks, mode="stacked", width_mm=180, labels=None, analysis_patterns=None, measurement_pattern=None, reference_info=None):
    """originals is [(filename, bytes)]; numbering prevents name/path collisions."""
    fig, figure_meta = make_figure(patterns, mode=mode, width_mm=width_mm, labels=labels)
    try:
        plots = export_figure(fig)
        qa = audit_pdf(plots["pdf"])
        if qa["status"] != "pass":
            raise ValueError("Figure text audit failed; increase figure size or shorten labels: " + str(qa["problems"]))
        nature_files, nature_status = nature_audit(fig, plots["pdf"])
    finally:
        plt.close(fig)
    files = {f"figure.{ext}": content for ext, content in plots.items()}
    files.update(nature_files)
    measurement_pattern = measurement_pattern or patterns[0]
    measurement_label = labels[0] if labels else "Sample"
    measurement_fig, measurement_meta = make_figure([measurement_pattern], mode="overlay",
                                                    width_mm=width_mm, labels=[measurement_label])
    try:
        measurement_plots = export_figure(measurement_fig)
        measurement_qa = audit_pdf(measurement_plots["pdf"])
        if measurement_qa["status"] != "pass":
            raise ValueError("Measurement figure text audit failed: " + str(measurement_qa["problems"]))
        measurement_nature_files, measurement_nature = nature_audit(measurement_fig, measurement_plots["pdf"])
    finally:
        plt.close(measurement_fig)
    files.update({f"measurement/figure.{ext}": data for ext, data in measurement_plots.items()})
    files["measurement/source.csv"] = csv_bytes(measurement_pattern)
    files.update({f"measurement/{name}": data for name, data in measurement_nature_files.items()})
    reference_info = reference_info or {}
    recipe = {**recipe, "reference_info": reference_info}
    sources = []
    for i, (name, data) in enumerate(originals, 1):
        safe_name = Path(name.replace("\\", "/")).name
        archive_name = f"raw/{i:02d}_{safe_name}"
        files[archive_name] = data
        sources.append({"file": archive_name, "original_name": safe_name, "sha256": sha256(data).hexdigest()})
    for i, p in enumerate(patterns, 1):
        files[f"processed/{i:02d}.csv"] = csv_bytes(p)
    analysis_patterns = analysis_patterns or patterns
    matching = recipe.get("matching", {})
    for i, p in enumerate(analysis_patterns, 1):
        files[f"analysis/{i:02d}_profile.csv"] = csv_bytes(p)
        files[f"analysis/{i:02d}_peaks.csv"] = table_bytes(detect_peaks(p,
            matching.get("prominence", .04), matching.get("min_peak_distance_deg", .15)))
    files["comparisons.json"] = json_bytes(comparisons)
    files["peaks.csv"] = table_bytes(peaks)
    sample_names = [r["name"] for r in recipe.get("all_sample_records", [])] or [patterns[0].name]
    report_options = MatchOptions(**matching)
    reports = {}
    for name in sample_names:
        sample = next(p for p in analysis_patterns if p.name == name)
        original_count = (len(measurement_pattern.x) if name == measurement_pattern.name else
                          next((h["rows_before"] for h in sample.history if h["operation"] == "crop"), len(sample.x)))
        reports[name] = build_report(sample, comparisons.get(name, {}), report_options,
                                     reference_info, original_count)
    for i, name in enumerate(sample_names, 1):
        files[f"reports/{i:02d}.md"] = reports[name]["markdown"].encode("utf-8")
        files[f"reports/{i:02d}.json"] = json_bytes(reports[name]["data"])
    primary_report = reports[patterns[0].name]
    files["report.md"] = primary_report["markdown"].encode("utf-8")
    files["report.json"] = json_bytes(primary_report["data"])
    meta = {"schema_version": 2, "software": "xrd-workbench", "version": __version__,
            "dependencies": {p: importlib.metadata.version(p) for p in ("numpy", "scipy", "matplotlib", "pymupdf")},
            "sources": sources, "recipe": recipe, "patterns": [p.info() for p in patterns],
            "figure": figure_meta, "portable_qa": qa, "nature_qa": nature_status,
            "analysis_patterns": [p.info() for p in analysis_patterns],
            "measurement": {"pattern": measurement_pattern.info(), "figure": measurement_meta,
                            "portable_qa": measurement_qa, "nature_qa": measurement_nature},
            "reports": reports,
            "claims": {"phase_identity": "candidate_library_screening_only", "score_is_probability": False,
                       "quantitative_phase_fractions": "not_estimated"}}
    files["manifest.json"] = json_bytes(meta)
    if "all_sample_records" in recipe:
        files["reproduce_analysis.py"] = Path(__file__).with_name("reproduce_template.py.txt").read_bytes()
    files["reproduce.py"] = Path(__file__).with_name("redraw_template.py.txt").read_bytes()
    files["README.txt"] = ("XRD Workbench export\n\n"
        "measurement/ contains the original measured single-scan figure and its source data; figure.* is the comparison.\n"
        "report.md/report.json and reports/ contain local deterministic reports; reference identities are user declarations.\n"
        "raw/ contains unchanged user inputs; processed/ maps in order to manifest.patterns.\n"
        "manifest.json records units, wavelength declarations, hashes, processing, display offsets and versions.\n"
        "recipe contains processing and matching parameters; comparisons.json contains complete peak evidence.\n"
        "reproduce_analysis.py repeats analysis from raw files when a complete recipe is present.\n"
        "reproduce.py redraws from figure source data without repeating processing. analysis/ includes every processed scan and peak table.\n"
        "Scores are heuristic candidate rankings, not probabilities, phase purity or composition fractions.\n"
        "Reference names identify supplied files, not a verified chemical assignment.\n"
        "All profiles remain unshifted in figures; optimized shifts exist only in comparison records.\n"
        "Review the figure at its final physical size. Portable QA does not check every text/curve collision.\n"
        "Third-party raw data retain their original ownership and access restrictions.\n").encode()
    files["checksums.sha256"] = "".join(f"{sha256(v).hexdigest()}  {k}\n" for k, v in sorted(files.items())).encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    plots["measurement"] = measurement_plots
    return out.getvalue(), meta, plots
