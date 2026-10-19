"""Render scan plots and check exported PDF text."""
from __future__ import annotations
from io import BytesIO
import textwrap
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pymupdf as fitz

PALETTE = ["#246B81", "#BC6B36", "#727981", "#7B6698", "#557B5A", "#A85C73"]


def make_figure(patterns, *, mode="stacked", width_mm=180, height_mm=None, labels=None):
    if not 1 <= len(patterns) <= 8:
        raise ValueError("Select between 1 and 8 patterns per figure.")
    if mode not in ("stacked", "overlay") or not 88 <= width_mm <= 240:
        raise ValueError("Use stacked/overlay and a width between 88 and 240 mm.")
    wavelengths = [p.wavelength for p in patterns if p.wavelength is not None]
    if wavelengths and not np.allclose(wavelengths, wavelengths[0], rtol=1e-4):
        raise ValueError("Figure contains different wavelengths; provide compatible references before angle-space comparison.")
    labels = labels or [p.name for p in patterns]
    if len(labels) != len(patterns):
        raise ValueError("Each pattern needs one label.")
    # Store full labels separately from the shortened display labels.
    display = [textwrap.shorten(str(s).replace("_", " "), width=35 if width_mm >= 150 else 22,
                                placeholder="…") for s in labels]
    display = [f"{i+1}. {label}" for i, label in enumerate(display)]
    h = height_mm or max(80, 31*len(patterns)+26)
    if not 60 <= h <= 320:
        raise ValueError("Figure height must be between 60 and 320 mm.")
    style = {"font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
             "font.size": 9, "axes.labelsize": 10, "xtick.labelsize": 8,
             "ytick.labelsize": 8, "legend.fontsize": 8,
             "svg.fonttype": "none", "pdf.fonttype": 42, "axes.linewidth": .8,
             "axes.spines.top": False, "axes.spines.right": False,
             "xtick.direction": "out", "ytick.direction": "out", "text.usetex": False}
    with matplotlib.rc_context(style):
        fig, ax = plt.subplots(figsize=(width_mm/25.4, h/25.4))
        fig.subplots_adjust(left=.16 if width_mm < 120 else .11, right=.97,
                            bottom=15/h, top=1-9/h)
        span = max(float(np.ptp(p.y)) for p in patterns)
        span = span if span > 0 else 1.
        offset_records = []
        lower, upper = [], []
        for i, (p, label) in enumerate(zip(patterns, display)):
            color = PALETTE[i % len(PALETTE)]
            offset = (len(patterns)-1-i)*1.65*span - float(p.y.min()) if mode == "stacked" and len(patterns) > 1 else 0.
            # Translate each trace vertically for stacked display.
            y = p.y + offset
            ax.plot(p.x, y, color=color, lw=.85, label=label)
            lower.append(float(y.min()))
            upper.append(float(y.max()))
            if mode == "stacked":
                ax.text(.015, float(y.max())+.16*span, label,
                        transform=ax.get_yaxis_transform(), color=color,
                        fontsize=9, va="bottom")
                upper[-1] += .48*span
            offset_records.append({"label": labels[i], "display_label": label, "offset": offset})
        if mode == "overlay":
            ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), borderaxespad=0.,
                      frameon=False, ncol=1)
            # Reserve space above the axes for the legend.
            fig.subplots_adjust(top=1-(9+5*len(patterns))/h)
        ax.set_ylim(min(lower)-.08*span, max(upper)+.06*span)
        ax.set_xlim(min(p.x[0] for p in patterns), max(p.x[-1] for p in patterns))
        ax.set_xlabel("2θ (°)")
        methods = [next((h["method"] for h in reversed(p.history) if h["operation"] == "normalize"), "none")
                   for p in patterns]
        unit = "Normalized intensity" if all(m != "none" for m in methods) else "Intensity (input units)"
        ax.set_ylabel(unit + (" + offset" if mode == "stacked" and len(patterns) > 1 else ""))
        if mode == "stacked" and len(patterns) > 1:
            ax.set_yticks([])
        fig.canvas.draw()
        metadata = {"backend": "matplotlib", "mode": mode, "width_mm": width_mm, "height_mm": h,
                    "single_panel_alignment": "not_applicable", "traces": offset_records,
                    "normalization_methods": methods, "negative_values": "retained",
                    "automatic_peak_labels": False}
        return fig, metadata


def export_figure(fig):
    outputs = {}
    with matplotlib.rc_context({"svg.fonttype": "none", "pdf.fonttype": 42}):
        for filename in ("figure.pdf", "figure.svg", "figure.png", "figure.tiff"):
            fmt = filename.rsplit(".", 1)[1]
            out = BytesIO()
            out.name = filename
            with warnings.catch_warnings(record=True) as seen:
                warnings.simplefilter("always")
                fig.savefig(out, format=fmt, dpi=600, facecolor="white")
                if any("Glyph" in str(w.message) and "missing" in str(w.message) for w in seen):
                    raise ValueError("A figure label contains unsupported glyphs. Use short Latin labels for export.")
            outputs[fmt] = out.getvalue()
    return outputs


def audit_pdf(pdf_bytes):
    """Check PDF text size, overlap and page bounds."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    problems, min_font = [], float("inf")
    for page in doc:
        spans = [s for b in page.get_text("dict")["blocks"] if "lines" in b
                 for line in b["lines"] for s in line["spans"] if s["text"].strip()]
        for s in spans:
            min_font = min(min_font, s["size"])
            rect = fitz.Rect(s["bbox"])
            if not page.rect.contains(rect):
                problems.append({"kind": "text_page_clipping", "text": s["text"]})
            if s["size"] < 5:
                problems.append({"kind": "font_below_5pt", "text": s["text"]})
        for i, a in enumerate(spans):
            for b in spans[i+1:]:
                intersection = fitz.Rect(a["bbox"]) & fitz.Rect(b["bbox"])
                if not intersection.is_empty and intersection.width > 1 and intersection.height > 1:
                    problems.append({"kind": "text_overlap", "texts": [a["text"], b["text"]]})
    doc.close()
    return {"status": "pass" if not problems else "fail", "problems": problems,
            "minimum_font_pt": min_font if np.isfinite(min_font) else None,
            "scope": "PDF text sizes, text overlaps and page bounds only",
            "visual_review": "required", "stroke_collision_audit": "not_performed_by_portable_check"}
