"""CLI and local UI launcher."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import sys
from .core import parse_bytes, process, Recipe, detect_peaks
from .matching import MatchOptions, rank_references
from .bundle import make_bundle


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Local numerical XRD workbench")
    sub = parser.add_subparsers(dest="command", required=True)
    ui = sub.add_parser("ui", help="Start the local web application")
    ui.add_argument("--port", type=int, default=8501)
    analyze = sub.add_parser("analyze", help="Process a sample and screen user references")
    analyze.add_argument("sample", type=Path)
    analyze.add_argument("--reference", action="append", type=Path, default=[])
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--wavelength", type=float, help="User-confirmed common wavelength in angstroms")
    analyze.add_argument("--lower", type=float)
    analyze.add_argument("--upper", type=float)
    analyze.add_argument("--baseline", action="store_true")
    analyze.add_argument("--smooth-window", type=int, default=0)
    analyze.add_argument("--normalization", choices=["none", "max", "area"], default="max")
    analyze.add_argument("--tolerance", type=float, default=.2)
    analyze.add_argument("--prominence", type=float, default=.04)
    analyze.add_argument("--max-shift", type=float, default=0.)
    args = parser.parse_args()
    if args.command == "ui":
        env = dict(os.environ, STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
        raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run",
                         str(Path(__file__).with_name("ui.py")), "--server.address", "127.0.0.1",
                         "--server.port", str(args.port), "--server.headless", "true",
                         "--theme.primaryColor", "#246b81", "--server.maxUploadSize", "20"], env=env))
    try:
        paths = [args.sample]+args.reference
        if len(paths) > 8:
            raise ValueError("CLI figure supports one sample and at most 7 references.")
        if len({p.name for p in paths}) != len(paths):
            raise ValueError("Sample and reference filenames must be unique.")
        originals = [(p.name, p.read_bytes()) for p in paths]
        parsed = [parse_bytes(data, name, args.wavelength) for name, data in originals]
        recipe = Recipe(lower=args.lower, upper=args.upper, baseline=args.baseline,
                        smooth_window=args.smooth_window, normalization=args.normalization)
        ref_recipe = Recipe(lower=args.lower, upper=args.upper, normalization=args.normalization)
        sample = process(parsed[0], recipe)
        refs = [process(p, ref_recipe) for p in parsed[1:]]
        options = MatchOptions(tolerance_deg=args.tolerance, prominence=args.prominence, max_shift_deg=args.max_shift)
        ranked, rejected = rank_references(sample, refs, options)
        bundle, _, _ = make_bundle([sample]+refs, originals,
                      recipe={"sample":asdict(recipe), "reference":asdict(ref_recipe), "matching":asdict(options),
                              "all_sample_records":[sample.info()], "all_reference_records":[p.info() for p in refs]},
                      comparisons={sample.name:{"ranked":ranked,"rejected":rejected}},
                      peaks=detect_peaks(sample, args.prominence), measurement_pattern=parsed[0],
                      labels=[Path(p.name).stem if Path(p.name).stem.isascii() else
                              ("Sample" if i == 0 else f"Reference {i}")
                              for i, p in enumerate([sample]+refs)])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(bundle)
        print(f"Exported {args.output}; {len(ranked)} candidate references; {len(rejected)} rejected.")
        for row in ranked:
            print(f"  {row['reference']}: score={row['score']:.4f}; matched_peaks={row['matched_count']}")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
