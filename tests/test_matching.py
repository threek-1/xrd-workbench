import numpy as np
import pytest
from xrd_workbench.core import Pattern
from xrd_workbench.matching import compare, MatchOptions, rank_references, _pair


def make(name="ref", positions=(12,20,32), shift=0, wavelength=1.5406):
    x=np.linspace(5,45,2001)
    y=sum(np.exp(-.5*((x-p-shift)/.12)**2) for p in positions)
    return Pattern(name,x,y,wavelength)


def test_identity_and_wrong_candidate():
    sample=make()
    r=compare(sample,sample)
    assert r["score"] == pytest.approx(1)
    assert r["matched_count"] == 3
    ranks,_=rank_references(sample,[make("wrong",(15,25,35)),make("correct")])
    assert ranks[0]["reference"] == "correct"
    assert ranks[1]["matched_count"] == 0


def test_wavelength_mismatch_and_unknown():
    with pytest.raises(ValueError,match="wavelength"):
        compare(make(),make(wavelength=1.79))
    assert any("unknown" in w for w in compare(make(),make(wavelength=None))["warnings"])


def test_range_rejection():
    p=Pattern("far",np.linspace(60,80,101),np.ones(101),1.5406)
    with pytest.raises(ValueError,match="range"):
        compare(make(),p)


def test_single_reference_peak_cannot_match_twice():
    pairs=_pair(np.array([20,20.1]),np.array([20.05]),.2)
    assert len(pairs)==1


def test_optimal_assignment_maximizes_valid_pairs():
    pairs=_pair(np.array([1.,1.18]),np.array([1.1,.85]),.2)
    assert len(pairs)==2


def test_shift_is_exploratory_and_originals_unchanged():
    sample,ref=make(shift=.3),make()
    x=ref.x.copy()
    r=compare(sample,ref,MatchOptions(max_shift_deg=.5,tolerance_deg=.1))
    assert r["reference_shift_deg"] == pytest.approx(.3)
    assert r["unshifted_score"] < r["score"]
    np.testing.assert_array_equal(x,ref.x)


def test_flat_spectrum_does_not_identify():
    p=make()
    flat=Pattern("flat",p.x,np.ones_like(p.x),p.wavelength)
    result=compare(flat,flat)
    assert result["score"] == 0 and result["status"] == "no_peak_support"


def test_extra_and_missing_peaks_preserved():
    r=compare(make(positions=(12,20,32,40)),make(positions=(12,20,28)))
    assert r["matched_count"]==2
    assert r["missing_reference_deg"] == pytest.approx([28])
    assert r["unmatched_observed_deg"] == pytest.approx([32,40])
