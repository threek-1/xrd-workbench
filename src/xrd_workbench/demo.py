"""Generate synthetic Gaussian profiles with seeded noise."""
import numpy as np
from .bundle import csv_bytes
from .core import Pattern


def demo_inputs():
    x = np.linspace(5, 65, 3001)
    def curve(positions, intensities, width=.13):
        return sum(a*np.exp(-.5*((x-p)/width)**2) for p, a in zip(positions, intensities))
    a = curve([12.4, 18.2, 24.8, 31.3, 42.1, 53.6], [1, .55, .8, .35, .6, .3])
    b = curve([10.8, 20.6, 28.1, 36.7, 45.9, 59.2], [.7, 1, .55, .4, .65, .3])
    rng = np.random.default_rng(20261018)
    sample = 1200*(a+.22*b)+60+.5*x+rng.normal(0, 4, len(x))
    records = [("Synthetic sample.csv", sample), ("Synthetic Phase A.csv", a), ("Synthetic Phase B.csv", b)]
    return [(name, b"# SYNTHETIC DEMONSTRATION; not measured data; seed=20261018\n" +
             csv_bytes(Pattern(name, x, y, 1.5406, "synthetic"))) for name, y in records]
