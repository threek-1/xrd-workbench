"""Write the synthetic example scans to examples/."""
from pathlib import Path
from xrd_workbench.demo import demo_inputs
root = Path(__file__).resolve().parents[1] / "examples"
root.mkdir(exist_ok=True)
for name, content in demo_inputs():
    (root / name).write_bytes(content)
print(f"Wrote {len(demo_inputs())} explicitly synthetic profiles.")
